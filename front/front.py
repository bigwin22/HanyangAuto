from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
from starlette.middleware.base import BaseHTTPMiddleware
import httpx

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# Security Headers Middleware
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

# CORS Configuration
cors_origins = os.getenv("CORS_ALLOW_ORIGINS")
allow_origins = [o.strip() for o in cors_origins.split(',')] if cors_origins else ["http://localhost:8080", "http://127.0.0.1:8080"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)

# API Proxy Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")
client = httpx.AsyncClient(base_url=BACKEND_URL)

@app.get("/api/{path:path}")
async def api_proxy(request: Request):
    path = request.url.path
    url = httpx.URL(path=path, query=request.url.query.encode("utf-8"))
    print(url)
    try:
        # Forward request to backend service
        response = await client.request(
            request.method,
            url,
            headers=request.headers,
            content=await request.body(),
            timeout=60.0,
        )
        return HTMLResponse(content=response.content, status_code=response.status_code, headers=dict(response.headers))
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")

# Static files and SPA serving
SPA_DIST = os.path.join(os.path.dirname(__file__), 'web', 'dist', 'spa')
ASSETS_DIST = os.path.join(SPA_DIST, 'assets')

app.mount("/assets", StaticFiles(directory=ASSETS_DIST), name="assets")

@app.get("/{full_path:path}", response_class=HTMLResponse)
def serve_spa(request: Request):
    index_path = os.path.join(SPA_DIST, "index.html")
    # All non-api, non-asset paths serve the SPA
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html not found")
