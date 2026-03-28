import base64
import os
from pathlib import Path as FilePath

import httpx
from fastapi import Depends, FastAPI, HTTPException, Path, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

import utils.database as db
from utils.logger import HanyangLogger, LOG_BASE, sanitize_filename
from utils.security import SlidingWindowRateLimiter, get_client_ip, mask_sensitive_text


app = FastAPI()
db.init_db()

SESSION_KEY_FILE_PATH = os.path.join(os.path.dirname(__file__), "data", "session_key.key")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() not in {"0", "false", "no"}
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "lax")
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "").strip()

USER_LOGIN_IP_LIMIT = int(os.getenv("USER_LOGIN_IP_LIMIT", "20"))
USER_LOGIN_ACCOUNT_LIMIT = int(os.getenv("USER_LOGIN_ACCOUNT_LIMIT", "5"))
USER_LOGIN_WINDOW_SEC = int(os.getenv("USER_LOGIN_WINDOW_SEC", "300"))
ADMIN_LOGIN_IP_LIMIT = int(os.getenv("ADMIN_LOGIN_IP_LIMIT", "10"))
ADMIN_LOGIN_ACCOUNT_LIMIT = int(os.getenv("ADMIN_LOGIN_ACCOUNT_LIMIT", "5"))
ADMIN_LOGIN_WINDOW_SEC = int(os.getenv("ADMIN_LOGIN_WINDOW_SEC", "900"))

if not INTERNAL_API_TOKEN:
    raise ValueError("INTERNAL_API_TOKEN must be set.")

user_login_limiter = SlidingWindowRateLimiter()
admin_login_limiter = SlidingWindowRateLimiter()


def load_or_generate_session_key():
    env_session_b64 = os.getenv("SESSION_SECRET_B64")
    if env_session_b64:
        try:
            return base64.b64decode(env_session_b64)
        except Exception as exc:
            raise ValueError(f"Invalid SESSION_SECRET_B64: {exc}") from exc

    os.makedirs(os.path.dirname(SESSION_KEY_FILE_PATH), exist_ok=True)
    if os.path.exists(SESSION_KEY_FILE_PATH):
        with open(SESSION_KEY_FILE_PATH, "rb") as file:
            return file.read()

    key = os.urandom(32)
    with open(SESSION_KEY_FILE_PATH, "wb") as file:
        file.write(key)
    return key


app.add_middleware(
    SessionMiddleware,
    secret_key=load_or_generate_session_key(),
    max_age=300,
    https_only=SESSION_COOKIE_SECURE,
    same_site=SESSION_COOKIE_SAMESITE,
    session_cookie="hanyang_admin_session",
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Pragma", "no-cache")
        return response


app.add_middleware(SecurityHeadersMiddleware)

cors_origins = os.getenv("CORS_ALLOW_ORIGINS")
if cors_origins:
    allow_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
else:
    allow_origins = ["http://localhost:8080", "http://127.0.0.1:8080"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

RECEIVE_SERVER_URL = os.getenv("RECEIVE_SERVER_URL", "http://automation:7000")


def _internal_api_headers() -> dict[str, str]:
    return {"X-Internal-Token": INTERNAL_API_TOKEN}


def _rate_limit_response(retry_after: int) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"message": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요."},
        headers={"Retry-After": str(retry_after)},
    )


def _check_login_rate_limits(
    limiter: SlidingWindowRateLimiter,
    client_ip: str,
    account_id: str,
    ip_limit: int,
    account_limit: int,
    window_sec: int,
) -> int:
    checks = (
        (f"ip:{client_ip}", ip_limit),
        (f"account:{account_id.lower()}", account_limit),
    )
    for key, limit in checks:
        allowed, retry_after = limiter.allow(key, limit, window_sec)
        if not allowed:
            return retry_after
    return 0


def _reset_account_rate_limit(limiter: SlidingWindowRateLimiter, account_id: str) -> None:
    limiter.reset(f"account:{account_id.lower()}")


async def trigger_user_automation(user_id: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{RECEIVE_SERVER_URL}/on-user-registered",
                json={"userId": user_id},
                headers=_internal_api_headers(),
                timeout=10.0,
            )
            logger = HanyangLogger("system")
            if response.status_code == 200:
                logger.info("automation", f"Successfully triggered automation for user: {user_id}")
            else:
                logger.error("automation", f"Failed to trigger automation for user {user_id}: {response.status_code}")
    except Exception as exc:
        logger = HanyangLogger("system")
        logger.error("automation", f"Error triggering automation for user {user_id}: {mask_sensitive_text(exc)}")


async def verify_user_credentials(user_id: str, password: str):
    async with httpx.AsyncClient() as client:
        return await client.post(
            f"{RECEIVE_SERVER_URL}/verify-login",
            json={"userId": user_id, "password": password},
            headers=_internal_api_headers(),
            timeout=30.0,
        )


class UserLoginRequest(BaseModel):
    userId: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


class AdminLoginRequest(BaseModel):
    adminId: str = Field(..., min_length=1, max_length=64)
    adminPassword: str = Field(..., min_length=1, max_length=256)


class AdminChangePasswordRequest(BaseModel):
    currentPassword: str = Field(..., min_length=1, max_length=256)
    newPassword: str = Field(..., min_length=12, max_length=256)


def get_current_admin(request: Request):
    if not request.session.get("admin_logged_in"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return True


@app.get("/api/admin/users", dependencies=[Depends(get_current_admin)])
def get_admin_users():
    users = []
    for row in db.get_all_users():
        users.append(
            {
                "id": row[0],
                "userId": row[1],
                "registeredDate": row[3],
                "status": row[4],
                "courses": db.get_learned_lectures(row[0]),
            }
        )
    return users


@app.post("/api/user/login")
async def user_login(req: UserLoginRequest, request: Request):
    logger = HanyangLogger("system")
    user_id = req.userId.strip()
    password = req.password
    user_logger = HanyangLogger("user", user_id=user_id)

    client_ip = get_client_ip(request)
    retry_after = _check_login_rate_limits(
        user_login_limiter,
        client_ip,
        user_id,
        USER_LOGIN_IP_LIMIT,
        USER_LOGIN_ACCOUNT_LIMIT,
        USER_LOGIN_WINDOW_SEC,
    )
    if retry_after:
        logger.warn("user", f"User login rate limit exceeded: userId={user_id}, ip={client_ip}")
        return _rate_limit_response(retry_after)

    import asyncio

    loop = asyncio.get_running_loop()
    try:
        verification_response = await verify_user_credentials(user_id, password)
    except Exception as exc:
        safe_error = mask_sensitive_text(exc)
        logger.error("user", f"Credential verification request failed: {user_id}: {safe_error}")
        user_logger.error("user", f"Credential verification request failed: {safe_error}")
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"message": "한양 LMS 계정 확인 서버에 연결하지 못했습니다. 잠시 후 다시 시도해주세요."},
        )

    verification_payload = verification_response.json()
    if verification_response.status_code != 200:
        message = verification_payload.get("message") or "아이디 또는 비밀번호가 올바르지 않습니다."
        logger.info("user", f"Credential verification failed: {user_id}")
        user_logger.info("user", f"Credential verification failed: {message}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"message": message},
        )

    logger.info("user", f"Credential verification succeeded: {user_id}")
    user_logger.info("user", "Credential verification succeeded")
    _reset_account_rate_limit(user_login_limiter, user_id)

    user = await loop.run_in_executor(None, db.get_user_by_id, user_id)
    if not user:
        await loop.run_in_executor(None, db.add_user, user_id, password)
        logger.info("user", f"New user registered: {user_id}")
        user_logger.info("user", "신규 유저 등록")
    else:
        await loop.run_in_executor(None, db.update_user_pwd, user_id, password)
        logger.info("user", f"Existing user password updated: {user_id}")
        user_logger.info("user", "기존 유저 비밀번호 업데이트")

    logger.info("user", f"User login completed: {user_id}")
    user_logger.info("user", "유저 로그인")

    await trigger_user_automation(user_id)
    return {"success": True, "userId": user_id}


@app.post("/api/admin/login")
def admin_login(req: AdminLoginRequest, request: Request):
    admin_id = req.adminId.strip()
    client_ip = get_client_ip(request)
    retry_after = _check_login_rate_limits(
        admin_login_limiter,
        client_ip,
        admin_id,
        ADMIN_LOGIN_IP_LIMIT,
        ADMIN_LOGIN_ACCOUNT_LIMIT,
        ADMIN_LOGIN_WINDOW_SEC,
    )
    if retry_after:
        return _rate_limit_response(retry_after)

    admin = db.get_admin()
    if not admin or admin[1] != admin_id or not db.verify_admin_password(admin[2], req.adminPassword):
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "로그인 실패"})

    if db.admin_password_needs_migration(admin[2]):
        db.update_admin_pwd(admin[1], req.adminPassword)

    _reset_account_rate_limit(admin_login_limiter, admin_id)
    request.session.clear()
    request.session["admin_logged_in"] = True
    return {"success": True, "adminId": admin_id}


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
    request.session.clear()
    return {"success": True, "message": "로그아웃 되었습니다."}


@app.post("/api/admin/change-password", dependencies=[Depends(get_current_admin)])
def admin_change_password(req: AdminChangePasswordRequest, request: Request):
    admin = db.get_admin()
    if not admin or not db.verify_admin_password(admin[2], req.currentPassword):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 비밀번호가 일치하지 않습니다.",
        )

    db.update_admin_pwd(admin[1], req.newPassword)
    request.session.clear()
    return {"success": True, "message": "비밀번호가 성공적으로 변경되었습니다."}


def _get_logs_sync(user_id: str):
    import glob

    safe_user_id = sanitize_filename(user_id)
    user_log_dirs = (
        sorted(
            [
                os.path.join(LOG_BASE, day_dir, "user", safe_user_id)
                for day_dir in os.listdir(LOG_BASE)
                if os.path.isdir(os.path.join(LOG_BASE, day_dir, "user", safe_user_id))
            ],
            reverse=True,
        )
        if os.path.isdir(LOG_BASE)
        else []
    )

    if not user_log_dirs:
        return None, "path_not_found"

    latest_log_file = None
    for user_log_dir in user_log_dirs:
        log_files = sorted(
            glob.glob(os.path.join(user_log_dir, "log*.log")),
            key=os.path.getmtime,
            reverse=True,
        )
        if log_files:
            latest_log_file = log_files[0]
            break

    if not latest_log_file:
        return None, "file_not_found"

    with open(latest_log_file, "r", encoding="utf-8") as file:
        return {
            "content": file.read(),
            "path": str(FilePath(latest_log_file).resolve()),
        }, "success"


@app.get("/api/admin/user/{user_id}/logs", dependencies=[Depends(get_current_admin)])
async def get_user_logs(user_id: str):
    import asyncio

    loop = asyncio.get_running_loop()
    log_payload, result = await loop.run_in_executor(None, _get_logs_sync, user_id)

    if result == "path_not_found":
        return JSONResponse(status_code=404, content={"message": "로그 파일 경로 없음"})
    if result == "file_not_found":
        return JSONResponse(status_code=404, content={"message": "사용자 로그 파일 없음"})

    return PlainTextResponse(
        content=log_payload["content"],
        headers={"X-Log-Path": log_payload["path"]},
    )


@app.post("/api/admin/trigger-all", dependencies=[Depends(get_current_admin)])
async def trigger_all_users():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{RECEIVE_SERVER_URL}/trigger-daily",
                headers=_internal_api_headers(),
                timeout=10.0,
            )
            if response.status_code == 200:
                payload = response.json()
                return {"success": True, "message": payload.get("message", "모든 유저 자동 수강을 시작했습니다.")}
            return JSONResponse(
                status_code=response.status_code,
                content={"detail": response.text or "자동 수강 시작에 실패했습니다."},
            )
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": f"자동화 서버 호출 실패: {mask_sensitive_text(exc)}"},
        )
