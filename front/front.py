from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
import os


app = FastAPI(
    docs_url=None,  # /docs 비활성화
    redoc_url=None,  # /redoc 비활성화
    openapi_url=None  # /openapi.json 비활성화
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


# app.add_middleware(SecurityHeadersMiddleware)


# Path to the built React app
SPA_DIST = os.path.join(os.path.dirname(__file__), 'web', 'dist', 'spa')
ASSETS_DIST = os.path.join(SPA_DIST, 'assets')

# Serve static assets (JS, CSS, images)
app.mount("/assets", StaticFiles(directory=ASSETS_DIST), name="assets")


# Allowed frontend routes (SPA)
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


"""프론트 전용 서버: 정적 파일과 SPA 라우트만 응답"""

# Catch-all for all other routes: return SPA index or 404 for api/*
@app.get("/{full_path:path}", response_class=HTMLResponse)
def catch_all(full_path: str):
    print(f"Catch-all received path: {full_path}")  # Add this line for debugging
    # API 경로는 404 반환 (이 서버는 API를 제공하지 않음)
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Page not found")
    # 그 외 모든 경로는 SPA index.html 반환
    index_path = os.path.join(SPA_DIST, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html not found")