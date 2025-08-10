from fastapi import FastAPI, Request, HTTPException, status, Depends, Path
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import utils.database as db
from automation import run_user_automation
from apscheduler.schedulers.background import BackgroundScheduler
from concurrent.futures import ThreadPoolExecutor
import threading
import glob
from utils.logger import HanyangLogger
from utils.database import decrypt_password
from utils import config as app_config
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp
from typing import Callable, Dict, List, Tuple
import time


app = FastAPI()
db.init_db()
"""보안 설정: 세션/호스트/헤더/레이트리미팅/CSRF"""

# 세션 미들웨어 추가 (10분 유지)
SESSION_KEY_FILE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'session_key.key')

def load_or_generate_session_key():
    os.makedirs(os.path.dirname(SESSION_KEY_FILE_PATH), exist_ok=True)
    # 환경변수 우선: SESSION_SECRET_KEY_BASE64 (base64-encoded bytes)
    env_key_b64 = os.getenv("SESSION_SECRET_KEY_BASE64")
    if env_key_b64:
        try:
            import base64
            return base64.b64decode(env_key_b64)
        except Exception:
            pass
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
    max_age=600,
    same_site="lax",
    https_only=True,
    session_cookie="sessionid",
)

# 신뢰 가능한 호스트 제한
cfg = app_config.load_config()
ALLOWED_HOSTS = [h.strip() for h in cfg.get("allowed_hosts", [])]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                def _set(name: str, value: str):
                    headers[name.lower().encode()] = value.encode()

                _set("x-frame-options", "DENY")
                _set("x-content-type-options", "nosniff")
                _set("referrer-policy", "no-referrer")
                _set("permissions-policy", "geolocation=(), microphone=(), camera=()")
                _set("strict-transport-security", "max-age=31536000; includeSubDomains; preload")
                # CSP: 빌드된 SPA와 API만 허용 (필요 시 조정)
                _set(
                    "content-security-policy",
                    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'",
                )
                message["headers"] = list(headers.items())
            await send(message)

        await self.app(scope, receive, send_wrapper)


app.add_middleware(SecurityHeadersMiddleware)

# CORS: 운영은 동일 오리진 서빙으로 제한. 필요 시 환경변수로 허용.
allowed_origins = [o.strip() for o in cfg.get("allowed_origins", []) if o.strip()]
if allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

# Path to the built React app
SPA_DIST = os.path.join(os.path.dirname(__file__), 'web', 'dist', 'spa')
ASSETS_DIST = os.path.join(SPA_DIST, 'assets')

# Serve static assets (JS, CSS, images)
app.mount("/assets", StaticFiles(directory=ASSETS_DIST), name="assets")

# Serve favicon
@app.get("/favicon.ico")
def favicon():
    favicon_path = os.path.join(SPA_DIST, "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    raise HTTPException(status_code=404, detail="Favicon not found")

# Serve robots.txt and placeholder.svg if needed
@app.get("/robots.txt")
def robots():
    robots_path = os.path.join(SPA_DIST, "robots.txt")
    if os.path.exists(robots_path):
        return FileResponse(robots_path)
    raise HTTPException(status_code=404, detail="robots.txt not found")

@app.get("/placeholder.svg")
def placeholder():
    svg_path = os.path.join(SPA_DIST, "placeholder.svg")
    if os.path.exists(svg_path):
        return FileResponse(svg_path)
    raise HTTPException(status_code=404, detail="placeholder.svg not found")

# Serve hanyang_logo.png for /hanyang_logo.png
@app.get("/hanyang_logo.png")
def hanyang_logo():
    # Try dist/spa first (in case it was copied during build)
    logo_path = os.path.join(SPA_DIST, "hanyang_logo.png")
    if os.path.exists(logo_path):
        return FileResponse(logo_path)
    # Fallback to vite publicDir (web/client/public)
    logo_path = os.path.join(os.path.dirname(__file__), 'web', 'client', 'public', 'hanyang_logo.png')
    if os.path.exists(logo_path):
        return FileResponse(logo_path)
    raise HTTPException(status_code=404, detail="hanyang_logo.png not found")

# Allowed frontend routes
ALLOWED_ROUTES = [
    "/",
    "/admin/login",
    "/admin/dashboard",
    "/admin/change-password",
    "/success",
]

@app.get("/", response_class=HTMLResponse)
@app.get("/admin/login", response_class=HTMLResponse)
@app.get("/admin/dashboard", response_class=HTMLResponse)
@app.get("/admin/change-password", response_class=HTMLResponse)
@app.get("/success", response_class=HTMLResponse)
def serve_spa(request: Request):
    index_path = os.path.join(SPA_DIST, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html not found")

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


# --- 간단 CSRF 보호 (Double Submit Token 유사) ---
def generate_csrf_token() -> str:
    return os.urandom(16).hex()

def get_csrf_from_request(request: Request) -> str:
    return request.headers.get("x-csrf-token", "")

def require_csrf(request: Request):
    session_token = request.session.get("csrf_token")
    header_token = get_csrf_from_request(request)
    if not session_token or not header_token or session_token != header_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token invalid")


# --- 간단 레이트리밋 (메모리) ---
RATE_LIMIT_STORE: Dict[Tuple[str, str], List[float]] = {}

def rate_limit(request: Request, limit: int, window_seconds: int):
    now = time.time()
    ip = request.client.host if request.client else "unknown"
    key = (request.url.path, ip)
    bucket = RATE_LIMIT_STORE.get(key, [])
    bucket = [ts for ts in bucket if now - ts < window_seconds]
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="Too Many Requests")
    bucket.append(now)
    RATE_LIMIT_STORE[key] = bucket

def db_add_learned(user_id, lecture_id):
    user = db.get_user_by_id(user_id)
    if user:
        db.add_learned_lecture(user[0], lecture_id)

# 유저 자동화 실행 (비동기)
def run_automation_for_user(user_id, pwd):
    system_logger = HanyangLogger('system')
    user_logger = HanyangLogger('user', user_id=str(user_id))
    learned = db.get_learned_lectures(db.get_user_by_id(user_id)[0])
    # DB에서 비밀번호 복호화
    user = db.get_user_by_id(user_id)
    if user:
        pwd = decrypt_password(user[2])
    system_logger.info('automation', f'자동화 시작: {user_id}')
    user_logger.info('automation', '자동화 시작')
    system_logger.info('automation', f'강의 목록 조회 시작: {user_id}')
    user_logger.info('automation', '강의 목록 조회 시작')
    result = run_user_automation(user_id, pwd, learned, db_add_learned)
    if result['success']:
        system_logger.info('automation', f'자동화 완료: {user_id} ({result["msg"]})')
        user_logger.info('automation', f'자동화 완료: {result["msg"]}')
    else:
        system_logger.error('automation', f'자동화 실패: {user_id} ({result["msg"]})')
        user_logger.error('automation', f'자동화 실패: {result["msg"]}')

# 전체 유저 자동화 (병렬)
def run_automation_for_all_users():
    users = db.get_all_users()
    with ThreadPoolExecutor(max_workers=5) as executor:
        for user in users:
            executor.submit(run_automation_for_user, user[1], user[2])

# APScheduler로 매일 7시, 서버 시작 시 자동화
scheduler = BackgroundScheduler(timezone='Asia/Seoul')
scheduler.add_job(run_automation_for_all_users, 'cron', hour=7, minute=0)
scheduler.start()

# 서버 시작 시 자동화
threading.Thread(target=run_automation_for_all_users, daemon=True).start()

# 서버 시작 시 로그 기록 (폴더 자동 생성)
HanyangLogger('system').info('system', '서버가 시작되었습니다.')

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
def user_login(req: UserLoginRequest, request: Request):
    # 레이트 리미팅: 1분당 10회/IP
    rate_limit(request, limit=10, window_seconds=60)
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
        logger.info('automation', f'자동화 준비 시작: {req.userId}')
        user_logger.info('automation', '자동화 준비 시작')
        threading.Thread(target=run_automation_for_user, args=(req.userId, req.password), daemon=True).start()
    else:
        db.update_user_pwd(req.userId, req.password)
        logger.info('user', f'기존 유저 비밀번호 업데이트: {req.userId}')
        user_logger.info('user', '기존 유저 비밀번호 업데이트')
        logger.info('user', f'유저 로그인: {req.userId}')
        user_logger.info('user', '유저 로그인')
        logger.info('automation', f'자동화 준비 시작: {req.userId}')
        user_logger.info('automation', '자동화 준비 시작')
        threading.Thread(target=run_automation_for_user, args=(req.userId, req.password), daemon=True).start()
    return {"success": True, "userId": req.userId}

@app.post("/api/admin/login")
def admin_login(req: AdminLoginRequest, request: Request):
    # 레이트 리미팅: 1분당 5회/IP
    rate_limit(request, limit=5, window_seconds=60)
    admin = db.get_admin()
    if not admin or admin[1] != req.adminId or decrypt_password(admin[2]) != req.adminPassword:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "로그인 실패"})

    # 초기 비밀번호 확인
    if req.adminId == 'admin' and req.adminPassword == 'admin':
        request.session["admin_logged_in"] = True
        # CSRF 토큰 발급
        csrf_token = generate_csrf_token()
        request.session["csrf_token"] = csrf_token
        return JSONResponse(status_code=200, content={"success": True, "adminId": req.adminId, "change_password": True, "csrf_token": csrf_token})

    # 세션에 로그인 정보 저장
    request.session["admin_logged_in"] = True
    csrf_token = generate_csrf_token()
    request.session["csrf_token"] = csrf_token
    return {"success": True, "adminId": req.adminId, "csrf_token": csrf_token}

@app.get("/api/admin/check-auth")
def check_admin_auth(request: Request):
    if not request.session.get("admin_logged_in"):
        raise HTTPException(status_code=401, detail="로그인 필요")
    return {"success": True}

# 제거: 인증 없이 사용자 정보를 노출하는 엔드포인트는 보안상 위험하므로 차단합니다.
# @app.get("/api/user/me")
# def user_me():
#     raise HTTPException(status_code=404, detail="Not found")

@app.delete("/api/admin/user/{user_id}", dependencies=[Depends(get_current_admin)])
def delete_user(request: Request, user_id: int = Path(...)):
    require_csrf(request)
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

# Catch-all for all other routes: return 404
@app.get("/{full_path:path}", response_class=HTMLResponse)
def catch_all(full_path: str):
    # API 경로는 404 반환
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Page not found")
    # 그 외 모든 경로는 SPA index.html 반환
    index_path = os.path.join(SPA_DIST, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html not found")

@app.post("/api/admin/logout")
def admin_logout(request: Request):
    request.session.pop("admin_logged_in", None)
    request.session.pop("csrf_token", None)
    return {"success": True, "message": "로그아웃 되었습니다."}

class AdminChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str

@app.post("/api/admin/change-password", dependencies=[Depends(get_current_admin)])
def admin_change_password(req: AdminChangePasswordRequest, request: Request):
    require_csrf(request)
    admin = db.get_admin()
    if not admin or decrypt_password(admin[2]) != req.currentPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="현재 비밀번호가 일치하지 않습니다.",
        )
    # 간단한 비밀번호 정책: 길이 8+, 영문/숫자 조합 권장
    if len(req.newPassword) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="새 비밀번호는 8자 이상이어야 합니다.",
        )
    db.update_admin_pwd(admin[1], req.newPassword)
    return {"success": True, "message": "비밀번호가 성공적으로 변경되었습니다."}

