import os
import sys
from fastapi import FastAPI, Request, HTTPException, status, Depends, Path
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
import httpx

# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import utils.database as db
from utils.logger import HanyangLogger
from utils.database import decrypt_password
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

app = FastAPI()
db.init_db()

# def __init__():
#     # data 폴더에 '암호화 키.key'가 없다면 base64로 인코딩된 32비트 난수 키를 생성
#     key_file_path = os.path.join(os.path.dirname(__file__), '..', 'data', '암호화 키.key')
#     if not os.path.exists(key_file_path):
#         os.makedirs(os.path.dirname(key_file_path), exist_ok=True)
#         random_key = os.urandom(32)
#         b64_key = base64.b64encode(random_key)
#         with open(key_file_path, 'wb') as f:
#             f.write(b64_key)
# __init__()

SESSION_KEY_FILE_PATH = os.path.join(os.path.dirname(__file__),'data', 'session_key.key')
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

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Receive server URL for automation triggers
RECEIVE_SERVER_URL = os.getenv("RECEIVE_SERVER_URL", "http://automation:7000")

async def trigger_user_automation(user_id: str):
    """
    Trigger automation for a user by calling the receive_server.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{RECEIVE_SERVER_URL}/on-user-registered",
                json={"userId": user_id},
                timeout=10.0
            )
            if response.status_code == 200:
                logger = HanyangLogger('system')
                logger.info('automation', f'Successfully triggered automation for user: {user_id}')
            else:
                logger = HanyangLogger('system')
                logger.error('automation', f'Failed to trigger automation for user {user_id}: {response.status_code}')
    except Exception as e:
        logger = HanyangLogger('system')
        logger.error('automation', f'Error triggering automation for user {user_id}: {e}')

cors_origins = os.getenv("CORS_ALLOW_ORIGINS")
if cors_origins:
    allow_origins = [o.strip() for o in cors_origins.split(',') if o.strip()]
else:
    allow_origins = ["http://localhost:8080", "http://127.0.0.1:8080"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

class UserLoginRequest(BaseModel):
    userId: str
    password: str
class AdminLoginRequest(BaseModel):
    adminId: str
    adminPassword: str

def get_current_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return True

@app.get("/api/admin/users", dependencies=[Depends(get_current_admin)])
def get_admin_users():
    users = []
    for row in db.get_all_users():
        users.append({
            "id": row[0],
            "userId": row[1],
            "registeredDate": row[3],
            "status": row[4],  # DB의 Status 컬럼 값 사용
            "courses": db.get_learned_lectures(row[0]),
        })
    return users

@app.post("/api/user/login")
async def user_login(req: UserLoginRequest):
    logger = HanyangLogger('system')
    user_logger = HanyangLogger('user', user_id=req.userId)
    
    import asyncio
    loop = asyncio.get_running_loop()

    user = await loop.run_in_executor(None, db.get_user_by_id, req.userId)
    is_new_user = False
    
    if not user:
        await loop.run_in_executor(None, db.add_user, req.userId, req.password)
        user = await loop.run_in_executor(None, db.get_user_by_id, req.userId)
        logger.info('user', f'신규 유저 등록: {req.userId}')
        user_logger.info('user', '신규 유저 등록')
        is_new_user = True
    else:
        await loop.run_in_executor(None, db.update_user_pwd, req.userId, req.password)
        logger.info('user', f'기존 유저 비밀번호 업데이트: {req.userId}')
        user_logger.info('user', '기존 유저 비밀번호 업데이트')
    
    logger.info('user', f'유저 로그인: {req.userId}')
    user_logger.info('user', '유저 로그인')
    
    # Trigger automation for the user (both new and existing users)
    await trigger_user_automation(req.userId)
    
    return {"success": True, "userId": req.userId}

@app.post("/api/admin/login")
def admin_login(req: AdminLoginRequest, request: Request):
    admin = db.get_admin()
    if not admin or admin[1] != req.adminId or decrypt_password(admin[2]) != req.adminPassword:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "로그인 실패"})

    if req.adminId == 'admin' and req.adminPassword == 'admin':
        request.session["admin_logged_in"] = True
        return JSONResponse(status_code=200, content={"success": True, "adminId": req.adminId, "change_password": True})

    request.session["admin_logged_in"] = True
    return {"success": True, "adminId": req.adminId}

@app.get("/api/admin/check-auth")
def check_admin_auth(request: Request):
    if not request.session.get("admin_logged_in"):
        raise HTTPException(status_code=401, detail="로그인 필요")
    return {"success": True}

@app.delete("/api/admin/user/{user_id}", dependencies=[Depends(get_current_admin)])
def delete_user(user_id: int = Path(...)):
    db.delete_learned_lectures(user_id)
    db.delete_user_by_num(user_id)
    return {"success": True, "deleted": user_id}

@app.post("/api/admin/logout")
def admin_logout(request: Request):
    request.session.pop("admin_logged_in", None)
    return {"success": True, "message": "로그아웃 되었습니다."}

class AdminChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str

@app.post("/api/admin/change-password", dependencies=[Depends(get_current_admin)])
def admin_change_password(req: AdminChangePasswordRequest, request: Request):
    admin = db.get_admin()
    if not admin or decrypt_password(admin[2]) != req.currentPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 비밀번호가 일치하지 않습니다.",
        )
    db.update_admin_pwd(admin[1], req.newPassword)
    request.session["admin_logged_in"] = None
    return {"success": True, "message": "비밀번호가 성공적으로 변경되었습니다."}

def _get_logs_sync(user_id: str):
    import glob
    from datetime import datetime

    today = datetime.now().strftime("%Y%m%d")
    logs_base_dir = os.path.join("logs")
    user_log_dir = os.path.join(logs_base_dir, today, "user", user_id)
    if not os.path.isdir(user_log_dir):
        return None, "path_not_found"
    
    log_files = sorted(glob.glob(os.path.join(user_log_dir, "log*.log")))
    if not log_files:
        return None, "file_not_found"
        
    latest_log_file = log_files[-1]
    with open(latest_log_file, "r", encoding="utf-8") as f:
        log_content = f.read()
    return log_content, "success"

@app.get("/api/admin/user/{user_id}/logs", dependencies=[Depends(get_current_admin)])
async def get_user_logs(user_id: str):
    import asyncio
    loop = asyncio.get_running_loop()
    log_content, status = await loop.run_in_executor(None, _get_logs_sync, user_id)

    if status == "path_not_found":
        return JSONResponse(status_code=404, content={"message": "로그 파일 경로 없음"})
    if status == "file_not_found":
        return JSONResponse(status_code=404, content={"message": "오늘 날짜 로그 파일 없음"})
    
    return JSONResponse(content=log_content)

@app.post("/api/admin/trigger-all", dependencies=[Depends(get_current_admin)])
async def trigger_all_users():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{RECEIVE_SERVER_URL}/trigger-daily",
                timeout=10.0
            )
            if response.status_code == 200:
                pass
            else:
               pass
    except Exception as e:
        pass