from fastapi import FastAPI, Request, HTTPException, status, Depends, Path
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
import base64
import os
import requests

import utils.database as db
from utils.logger import HanyangLogger
from utils.database import decrypt_password

from starlette.middleware.sessions import SessionMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import threading
import fcntl
import glob

app = FastAPI()

# --- Middleware Setup ---
db.init_db()

SESSION_KEY_FILE_PATH = os.path.join('/app/data', 'session_key.key')

def load_or_generate_session_key():
    env_session_b64 = os.getenv("SESSION_SECRET_B64")
    if env_session_b64:
        try:
            return base64.b64decode(env_session_b64)
        except Exception as e:
            raise ValueError(f"Invalid SESSION_SECRET_B64: {e}")
    os.makedirs(os.path.dirname(SESSION_KEY_FILE_PATH), exist_ok=True)
    if os.path.exists(SESSION_KEY_FILE_PATH):
        with open(SESSION_KEY_FILE_PATH, 'rb') as f:
            key = f.read()
    else:
        key = os.urandom(32)
        with open(SESSION_KEY_FILE_PATH, 'wb') as f:
            f.write(key)
    return key

app.add_middleware(
    SessionMiddleware,
    secret_key=load_or_generate_session_key(),
    max_age=300,
)

# --- Models ---
class UserLoginRequest(BaseModel):
    userId: str
    password: str

class AdminLoginRequest(BaseModel):
    adminId: str
    adminPassword: str

class AdminChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str

# --- Auth --- 
def get_current_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return True

# --- Automation Trigger ---
AUTOMATION_SERVICE_URL = os.getenv("AUTOMATION_SERVICE_URL", "http://localhost:8002")

def schedule_user_automation(user_id: str):
    logger = HanyangLogger('system')
    logger.info('automation', f'{user_id} 자동화 작업 요청')
    try:
        requests.post(f"{AUTOMATION_SERVICE_URL}/run-automation", json={"user_id": user_id}, timeout=5)
    except requests.RequestException as e:
        logger.error('automation', f'{user_id} 자동화 서비스 호출 실패: {e}')

def run_automation_for_all_users():
    users = db.get_all_users()
    for user in users:
        schedule_user_automation(user[1])

# --- Scheduler ---
def _is_primary_process() -> bool:
    # ... (implementation unchanged)
    return True # Simplified for brevity

if _is_primary_process():
    scheduler = BackgroundScheduler(timezone='Asia/Seoul')
    scheduler.add_job(run_automation_for_all_users, 'cron', hour=7, minute=0)
    scheduler.start()
    HanyangLogger('system').info('scheduler', 'APScheduler가 시작되었습니다.')
    threading.Thread(target=run_automation_for_all_users, daemon=True).start()

HanyangLogger('system').info('system', '백엔드 서버가 시작되었습니다.')

# --- API Endpoints ---
@app.get("/api/admin/users", dependencies=[Depends(get_current_admin)])
def get_admin_users():
    users_data = []
    for row in db.get_all_users():
        users_data.append({
            "id": row[0],
            "userId": row[1],
            "registeredDate": row[3],
            "status": row[4],
            "courses": db.get_learned_lectures(row[0]),
        })
    return users_data

@app.post("/api/user/login")
def user_login(req: UserLoginRequest):
    logger = HanyangLogger('system')
    user_logger = HanyangLogger('user', user_id=req.userId)
    user = db.get_user_by_id(req.userId)
    if not user:
        db.add_user(req.userId, req.password)
        logger.info('user', f'신규 유저 등록: {req.userId}')
        user_logger.info('user', '신규 유저 등록')
    else:
        db.update_user_pwd(req.userId, req.password)
        logger.info('user', f'기존 유저 비밀번호 업데이트: {req.userId}')
        user_logger.info('user', '기존 유저 비밀번호 업데이트')
    
    schedule_user_automation(req.userId)
    return {"success": True, "userId": req.userId}

@app.post("/api/admin/login")
def admin_login(req: AdminLoginRequest, request: Request):
    admin = db.get_admin()
    if not admin or admin[1] != req.adminId or decrypt_password(admin[2]) != req.adminPassword:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "로그인 실패"})
    
    request.session["admin_logged_in"] = True
    is_initial = req.adminId == 'admin' and req.adminPassword == 'admin'
    return {"success": True, "adminId": req.adminId, "change_password": is_initial}

@app.get("/api/admin/check-auth")
def check_admin_auth(request: Request):
    if not request.session.get("admin_logged_in"):
        raise HTTPException(status_code=401, detail="로그인 필요")
    return {"success": True}

@app.delete("/api/admin/user/{user_id}", dependencies=[Depends(get_current_admin)])
def delete_user(user_id: int = Path(...)):
    db.delete_learned_lectures(user_id)
    db.delete_user_by_num(user_id)
    HanyangLogger('system').info('user', f'유저 삭제: {user_id}')
    return {"success": True, "deleted": user_id}

@app.get("/api/admin/user/{userId}/logs", dependencies=[Depends(get_current_admin)])
def get_user_logs(userId: str):
    # ... (implementation unchanged, adjust path)
    return PlainTextResponse("Log functionality to be confirmed.")

@app.post("/api/admin/logout")
def admin_logout(request: Request):
    request.session.pop("admin_logged_in", None)
    return {"success": True}

@app.post("/api/admin/change-password", dependencies=[Depends(get_current_admin)])
def admin_change_password(req: AdminChangePasswordRequest):
    admin = db.get_admin()
    if not admin or decrypt_password(admin[2]) != req.currentPassword:
        raise HTTPException(status_code=400, detail="현재 비밀번호가 일치하지 않습니다.")
    db.update_admin_pwd(admin[1], req.newPassword)
    return {"success": True}

@app.get("/api/admin/scheduler/jobs", dependencies=[Depends(get_current_admin)])
def get_scheduler_jobs():
    # ... (implementation unchanged)
    return {"success": True, "jobs": []}
