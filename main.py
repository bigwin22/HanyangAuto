from fastapi import FastAPI, Request, HTTPException, status, Depends, Path
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import base64
import os
import utils.database as db
from automation import run_user_automation
from apscheduler.schedulers.background import BackgroundScheduler
from concurrent.futures import ThreadPoolExecutor
import threading
import glob
from utils.logger import HanyangLogger
from utils.database import decrypt_password
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import fcntl
from typing import Dict
 


app = FastAPI()
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
    # Fallback to client/public
    logo_path = os.path.join(os.path.dirname(__file__), 'echo-world', 'client', 'public', 'hanyang_logo.png')
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

def db_add_learned(user_id, lecture_id):
    user = db.get_user_by_id(user_id)
    if user:
        db.add_learned_lecture(user[0], lecture_id)

# 유저 자동화 실행 (비동기)
# 전역 동시성 제한: 환경변수 AUTOMATION_MAX_WORKERS (기본 5)
automation_executor = ThreadPoolExecutor(max_workers=int(os.getenv("AUTOMATION_MAX_WORKERS", "5")))

# 프로세스 간 유저별 중복 실행 방지용 파일 락
user_lock_fds: Dict[str, int] = {}

def _try_acquire_user_file_lock(user_id: str) -> bool:
    lock_path = f"/tmp/hanyangauto_user_{user_id}.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        user_lock_fds[user_id] = fd
        return True
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        return False

def _release_user_file_lock(user_id: str):
    fd = user_lock_fds.pop(user_id, None)
    if fd is not None:
        try:
            os.close(fd)
        except Exception:
            pass

def schedule_user_automation(user_id: str, pwd: str):
    logger = HanyangLogger('system')
    if not _try_acquire_user_file_lock(user_id):
        logger.info('automation', f'중복 실행 방지로 {user_id} 작업 건너뜀')
        return
    def _task():
        try:
            run_automation_for_user(user_id, pwd)
        finally:
            _release_user_file_lock(user_id)
    automation_executor.submit(_task)
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
    for user in users:
        # user[1] = ID, user[2] = PWD_Encrypted
        schedule_user_automation(user[1], user[2])

# APScheduler로 매일 7시, 서버 시작 시 자동화
def _is_primary_process() -> bool:
    fd = None
    try:
        lock_path = '/tmp/hanyangauto_scheduler.lock'
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        globals()['__primary_lock_fd'] = fd  # keep FD open
        return True
    except Exception:
        if fd is not None:
            try:
                os.close(fd)
            except Exception:
                pass
        return False

if _is_primary_process():
    scheduler = BackgroundScheduler(timezone='Asia/Seoul')
    scheduler.add_job(run_automation_for_all_users, 'cron', hour=7, minute=0)
    scheduler.start()
    # 스케줄러 시작 로그
    HanyangLogger('system').info('scheduler', 'APScheduler가 시작되었습니다. (Asia/Seoul)')
    # 서버 시작 시 자동화 (초기 한 번)
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
        logger.info('automation', f'자동화 준비 시작: {req.userId}')
        user_logger.info('automation', '자동화 준비 시작')
        schedule_user_automation(req.userId, req.password)
    else:
        db.update_user_pwd(req.userId, req.password)
        logger.info('user', f'기존 유저 비밀번호 업데이트: {req.userId}')
        user_logger.info('user', '기존 유저 비밀번호 업데이트')
        logger.info('user', f'유저 로그인: {req.userId}')
        user_logger.info('user', '유저 로그인')
        logger.info('automation', f'자동화 준비 시작: {req.userId}')
        user_logger.info('automation', '자동화 준비 시작')
        schedule_user_automation(req.userId, req.password)
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

@app.get("/api/user/me")
def user_me():
    # 실제 서비스에서는 세션/토큰 등 인증 필요
    # 예시: 첫 번째 유저 반환
    user = db.get_all_users()[0] if db.get_all_users() else None
    if not user:
        return JSONResponse(status_code=404, content={"message": "사용자 없음"})
    return {"userId": user[1]}

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

# 스케줄러 잡 조회용 (관리자)
@app.get("/api/admin/scheduler/jobs", dependencies=[Depends(get_current_admin)])
def get_scheduler_jobs():
    try:
        jobs = []
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "trigger": str(job.trigger),
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            })
        return {"success": True, "jobs": jobs}
    except NameError:
        return {"success": False, "message": "스케줄러가 초기화되지 않았습니다."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

