import os
import sys
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import httpx
import json

# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

FRONT_DIR = os.path.dirname(__file__)
SPA_DIST = os.path.join(FRONT_DIR, 'web', 'dist', 'spa')
ASSETS_DIST = os.path.join(SPA_DIST, 'assets')

if os.path.exists(ASSETS_DIST):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIST), name="assets")

BACKEND_URL = "back:9000"

@app.api_route("/api/{path:path}", methods=["GET", "POST", "DELETE"])
async def proxy_api(request: Request, path: str):
    url = f"http://{BACKEND_URL}/api/{path}"
    headers = {key: value for key, value in request.headers.items() if key.lower() not in ('host', 'user-agent', 'content-length')}

    async with httpx.AsyncClient() as client:
        if request.method == "GET":
            response = await client.get(url, headers=headers)
        elif request.method == "POST":
            content_type = request.headers.get('content-type')
            if content_type and 'application/json' in content_type:
                data = await request.json()
                response = await client.post(url, json=data, headers=headers)
            else:
                response = await client.post(url, headers=headers)
        elif request.method == "DELETE":
            response = await client.delete(url, headers=headers)
        else:
            return Response(status_code=405)

    response_headers = {key: value for key, value in response.headers.items() if key.lower() not in ('content-encoding', 'transfer-encoding')}
    return Response(content=response.content, status_code=response.status_code, headers=response_headers)



@app.get("/favicon.ico")
def favicon():
    favicon_path = os.path.join(SPA_DIST, "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    raise HTTPException(status_code=404, detail="Favicon not found")

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

@app.get("/hanyang_logo.png")
def hanyang_logo():
    logo_path = os.path.join(SPA_DIST, "hanyang_logo.png")
    if os.path.exists(logo_path):
        return FileResponse(logo_path)
    logo_path = os.path.join(FRONT_DIR, 'web', 'client', 'public', 'hanyang_logo.png')
    if os.path.exists(logo_path):
        return FileResponse(logo_path)
    raise HTTPException(status_code=404, detail="hanyang_logo.png not found")

@app.get("/", response_class=HTMLResponse)
@app.get("/admin/login", response_class=HTMLResponse)
@app.get("/admin/dashboard", response_class=HTMLResponse)
@app.get("/admin/change-password", response_class=HTMLResponse)
@app.get("/success", response_class=HTMLResponse)
def serve_spa_routes(request: Request):
    index_path = os.path.join(SPA_DIST, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html not found")

@app.get("/{full_path:path}", response_class=HTMLResponse)
def catch_all(full_path: str):
    index_path = os.path.join(SPA_DIST, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="index.html not found")
