from fastapi import FastAPI, Request, HTTPException, status, Depends, Path
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import utils.database as db
from automation import run_user_automation
from apscheduler.schedulers.background import BackgroundScheduler
from concurrent.futures import ThreadPoolExecutor
import threading

app = FastAPI()
db.init_db()

# CORS 허용 (개발용, 필요시 수정)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

def db_add_learned(user_id, lecture_id):
    user = db.get_user_by_id(user_id)
    if user:
        db.add_learned_lecture(user[0], lecture_id)

# 유저 자동화 실행 (비동기)
def run_automation_for_user(user_id, pwd):
    learned = db.get_learned_lectures(db.get_user_by_id(user_id)[0])
    run_user_automation(user_id, pwd, learned, db_add_learned)

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

@app.get("/api/admin/users")
def get_admin_users():
    users = []
    for row in db.get_all_users():
        users.append({
            "id": row[0],
            "userId": row[1],
            "registeredDate": row[3],
            "status": "active",  # TODO: 실제 상태 로직으로 대체
            "courses": db.get_learned_lectures(row[0]),
        })
    return users

@app.post("/api/user/login")
def user_login(req: UserLoginRequest):
    user = db.get_user_by_id(req.userId)
    if not user:
        db.add_user(req.userId, req.password)  # TODO: 암호화 필요
        user = db.get_user_by_id(req.userId)
        # 신규 등록자: 자동화 실행
        threading.Thread(target=run_automation_for_user, args=(req.userId, req.password), daemon=True).start()
    else:
        db.update_user_pwd(req.userId, req.password)  # TODO: 암호화 필요
        # 기존 등록자: 자동화 실행
        threading.Thread(target=run_automation_for_user, args=(req.userId, req.password), daemon=True).start()
    return {"success": True, "userId": req.userId}

@app.post("/api/admin/login")
def admin_login(req: AdminLoginRequest):
    admin = db.get_admin()
    if not admin or admin[1] != req.adminId or admin[2] != req.adminPassword:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"message": "로그인 실패"})
    return {"success": True, "adminId": req.adminId}

@app.get("/api/user/me")
def user_me():
    # 실제 서비스에서는 세션/토큰 등 인증 필요
    # 예시: 첫 번째 유저 반환
    user = db.get_all_users()[0] if db.get_all_users() else None
    if not user:
        return JSONResponse(status_code=404, content={"message": "사용자 없음"})
    return {"userId": user[1]}

@app.delete("/api/admin/user/{user_id}")
def delete_user(user_id: int = Path(...)):
    db.delete_learned_lectures(user_id)
    db.delete_user_by_num(user_id)
    return {"success": True, "deleted": user_id}

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
