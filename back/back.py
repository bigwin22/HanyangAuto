from fastapi import FastAPI, Request, HTTPException, status, Depends, Path
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
import os
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict
import glob

import sys
import os

# 상위 디렉토리를 sys.path에 추가
sys.path.append(os.path.abspath(".."))
from utils.logger import HanyangLogger
from utils.database import decrypt_password
import utils.database as db



app = FastAPI(
    docs_url=None,  # /docs 비활성화
    redoc_url=None,  # /redoc 비활성화
    openapi_url=None  # /openapi.json 비활성화
)

db.init_db()

# 세션 미들웨어 추가 (유지시간 5분). 환경변수 우선 사용
SESSION_KEY_FILE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'session_key.key')


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
        key = os.urandom(32)  # 32 bytes for a strong session key
        with open(SESSION_KEY_FILE_PATH, 'wb') as f:
            f.write(key)
    return key


app.add_middleware(
    SessionMiddleware,
    secret_key=load_or_generate_session_key(),
    max_age=300,
)


# 보안 헤더 미들웨어
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


# CORS 허용: 환경변수 CORS_ALLOW_ORIGINS(콤마 구분) 우선
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


# --- DB 연동 API ---
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
def user_login(req: UserLoginRequest):
    logger = HanyangLogger('system')
    user_logger = HanyangLogger('user', user_id=req.userId)
    user = db.get_user_by_id(req.userId)
    if not user:
        db.add_user(req.userId, req.password)
        user = db.get_user_by_id(req.userId)
        logger.info('user', f'신규 유저 등록: {req.userId}')
        user_logger.info('user', '신규 유저 등록')
        logger.info('user', f'유저 로그인: {req.userId}')
        user_logger.info('user', '유저 로그인')
    else:
        db.update_user_pwd(req.userId, req.password)
        logger.info('user', f'기존 유저 비밀번호 업데이트: {req.userId}')
        user_logger.info('user', '기존 유저 비밀번호 업데이트')
        logger.info('user', f'유저 로그인: {req.userId}')
        user_logger.info('user', '유저 로그인')
    return {"success": True, "userId": req.userId}


@app.post("/api/admin/login")
def admin_login(req: AdminLoginRequest, request: Request):
    admin = db.get_admin()
    if not admin or admin[1] != req.adminId or decrypt_password(admin[2]) != req.adminPassword:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "로그인 실패"})

    # 초기 비밀번호 확인
    if req.adminId == 'admin' and req.adminPassword == 'admin':
        request.session["admin_logged_in"] = True
        return JSONResponse(status_code=200, content={"success": True, "adminId": req.adminId, "change_password": True})

    # 세션에 로그인 정보 저장
    request.session["admin_logged_in"] = True
    return {"success": True, "adminId": req.adminId}


@app.get("/api/admin/check-auth")
def check_admin_auth(request: Request):
    if not request.session.get("admin_logged_in"):
        raise HTTPException(status_code=401, detail="로그인 필요")
    return {"success": True}


@app.delete("/api/admin/user/{user_id}", dependencies=[Depends(get_current_admin)])
def delete_user(user_id: int = Path(...)):
    logger = HanyangLogger('system')
    db.delete_learned_lectures(user_id)
    db.delete_user_by_num(user_id)
    logger.info('user', f'유저 삭제: {user_id}')
    return {"success": True, "deleted": user_id}


@app.get("/api/admin/user/{userId}/logs", dependencies=[Depends(get_current_admin)])
def get_user_logs(userId: str):
    from datetime import datetime
    logs_base = os.path.join(os.path.dirname(__file__), 'logs')
    today = datetime.now().strftime('%Y%m%d')
    user_log_dir = os.path.join(logs_base, today, 'user', str(userId))
    if not os.path.exists(user_log_dir):
        return PlainTextResponse("로그 파일 없음", status_code=404)
    log_files = sorted(glob.glob(os.path.join(user_log_dir, 'log*.log')))
    if not log_files:
        return PlainTextResponse("로그 파일 없음", status_code=404)
    with open(log_files[-1], encoding='utf-8') as f:
        content = f.read()
    return PlainTextResponse(content)


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
    return {"success": True, "message": "비밀번호가 성공적으로 변경되었습니다."}

