from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import os

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
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

# CORS 허용
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

# 정적 파일 경로 설정
SPA_DIST = os.path.join(os.path.dirname(__file__), '..', 'web', 'dist', 'spa')
ASSETS_DIST = os.path.join(SPA_DIST, 'assets')

# 정적 에셋 제공
app.mount("/assets", StaticFiles(directory=ASSETS_DIST), name="assets")

# 특정 정적 파일 제공
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    path = os.path.join(SPA_DIST, "favicon.ico")
    return FileResponse(path) if os.path.exists(path) else HTTPException(status_code=404)

@app.get("/hanyang_logo.png", include_in_schema=False)
def hanyang_logo():
    path = os.path.join(SPA_DIST, "hanyang_logo.png")
    return FileResponse(path) if os.path.exists(path) else HTTPException(status_code=404)

# SPA 라우팅
@app.get("/{full_path:path}", response_class=HTMLResponse)
def serve_spa(request: Request, full_path: str):
    index_path = os.path.join(SPA_DIST, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=500, detail="Frontend build not found.")

    # API 요청은 백엔드로 프록시되므로 여기서는 SPA의 index.html만 반환
    if full_path.startswith("api/"):
         raise HTTPException(status_code=404, detail="API endpoint not found on frontend server.")

    return FileResponse(index_path)
