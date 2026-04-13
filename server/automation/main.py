import asyncio
import hmac
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from zoneinfo import ZoneInfo

from .playwright_automation import run_user_automation, verify_user_login
from utils.database import (
    add_learned_lecture,
    decrypt_password,
    get_all_users,
    get_learned_lectures,
    get_user_by_id,
    update_user_status,
)
from utils.logger import HanyangLogger
from utils.security import SlidingWindowRateLimiter, get_client_ip, mask_sensitive_text


server_logger = HanyangLogger("server", user_id="receive_server")
executor = ThreadPoolExecutor(max_workers=5)
scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Seoul"))
verify_login_limiter = SlidingWindowRateLimiter()

INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "").strip()
VERIFY_LOGIN_IP_LIMIT = int(os.getenv("VERIFY_LOGIN_IP_LIMIT", "30"))
VERIFY_LOGIN_ACCOUNT_LIMIT = int(os.getenv("VERIFY_LOGIN_ACCOUNT_LIMIT", "10"))
VERIFY_LOGIN_WINDOW_SEC = int(os.getenv("VERIFY_LOGIN_WINDOW_SEC", "300"))
AUTOMATION_CORS_ALLOW_ORIGINS = os.getenv("AUTOMATION_CORS_ALLOW_ORIGINS", "").strip()

if not INTERNAL_API_TOKEN:
    raise ValueError("INTERNAL_API_TOKEN must be set.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    scheduler.add_job(run_daily_automation, CronTrigger(hour=7, minute=0), id="daily_automation")
    server_logger.info("server", "Scheduler started with daily automation at 7:00 AM KST")
    try:
        yield
    finally:
        server_logger.info("server", "Server is shutting down. Waiting for all running jobs to complete.")
        scheduler.shutdown(wait=True)
        executor.shutdown(wait=True)


app = FastAPI(lifespan=lifespan)

if AUTOMATION_CORS_ALLOW_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in AUTOMATION_CORS_ALLOW_ORIGINS.split(",") if origin.strip()],
        allow_credentials=True,
        allow_methods=["POST"],
        allow_headers=["Content-Type", "X-Internal-Token"],
    )


class AutomationRequest(BaseModel):
    userId: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=2048)
    userNum: int
    learnedLectures: list


class UserRegistered(BaseModel):
    userId: str = Field(..., min_length=1, max_length=128)


class CredentialVerificationRequest(BaseModel):
    userId: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


def require_internal_request(request: Request):
    received_token = request.headers.get("x-internal-token", "")
    if not received_token or not hmac.compare_digest(received_token, INTERNAL_API_TOKEN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return True


def _rate_limit_response(retry_after: int) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"message": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요."},
        headers={"Retry-After": str(retry_after)},
    )


def _check_verify_login_rate_limit(request: Request, user_id: str) -> int:
    client_ip = get_client_ip(request)
    checks = (
        (f"verify:ip:{client_ip}", VERIFY_LOGIN_IP_LIMIT),
        (f"verify:account:{user_id.lower()}", VERIFY_LOGIN_ACCOUNT_LIMIT),
    )
    for key, limit in checks:
        allowed, retry_after = verify_login_limiter.allow(key, limit, VERIFY_LOGIN_WINDOW_SEC)
        if not allowed:
            return retry_after
    return 0


def _reset_verify_login_account_rate_limit(user_id: str) -> None:
    verify_login_limiter.reset(f"verify:account:{user_id.lower()}")


def automation_task_wrapper(user_id: str, encrypted_pwd: str, user_num: int, learned_lectures: list):
    run_id = HanyangLogger.new_run_id("automation")
    user_logger = HanyangLogger("user", user_id=str(user_id), default_fields={"run_id": run_id})
    user_logger.event("automation", "automation_task_enqueued", "automation task started", user_num=user_num)

    try:
        plain_pwd = decrypt_password(encrypted_pwd)
    except Exception as exc:
        user_logger.error("automation", f"Password decryption failed: {mask_sensitive_text(exc)}", event="password_decryption_failed", user_num=user_num)
        update_user_status(user_id, "error")
        return

    try:
        def db_add_learned_callback(_user_id_from_automation, lecture_id):
            add_learned_lecture(user_num, lecture_id)

        run_user_automation(
            user_id=user_id,
            pwd=plain_pwd,
            learned_lectures=learned_lectures,
            db_add_learned=db_add_learned_callback,
            run_id=run_id,
        )
    except Exception as exc:
        user_logger.error("automation", f"Unexpected automation error: {mask_sensitive_text(exc)}", event="automation_task_unexpected_error", user_num=user_num)
        try:
            update_user_status(user_id, "error")
        except Exception as db_exc:
            user_logger.error("automation", f"Failed to update status to error: {mask_sensitive_text(db_exc)}", event="automation_status_update_failed", user_num=user_num)


def schedule_user_from_db(user_row):
    user_num, user_id, enc_pwd = user_row[0], user_row[1], user_row[2]
    learned = get_learned_lectures(user_num)
    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        executor,
        automation_task_wrapper,
        user_id,
        enc_pwd,
        user_num,
        learned,
    )


async def run_daily_automation():
    server_logger.info("scheduler", "Starting daily automation for all users")
    loop = asyncio.get_running_loop()
    users = await loop.run_in_executor(None, get_all_users)
    server_logger.info("scheduler", f"Found {len(users)} users for daily automation")

    for index, user in enumerate(users):
        try:
            schedule_user_from_db(user)
            server_logger.info("scheduler", f"Scheduled automation for user: {user[1]}")
            if (index + 1) < len(users):
                await asyncio.sleep(15)
        except Exception as exc:
            server_logger.error("scheduler", f"Failed to schedule automation for user {user[1]}: {mask_sensitive_text(exc)}")

    server_logger.info("scheduler", "Daily automation scheduling completed")


@app.post("/start-automation", dependencies=[Depends(require_internal_request)])
async def start_automation(req: AutomationRequest):
    try:
        server_logger.info("request", f"Automation request received for user: {req.userId}")
        loop = asyncio.get_running_loop()
        loop.run_in_executor(
            executor,
            automation_task_wrapper,
            req.userId,
            req.password,
            req.userNum,
            req.learnedLectures,
        )
        return {"status": "accepted", "message": f"Automation for user {req.userId} has been scheduled."}
    except Exception as exc:
        server_logger.error("request", f"Failed to schedule automation for user {req.userId}: {mask_sensitive_text(exc)}")
        raise HTTPException(status_code=500, detail=f"Failed to schedule automation for user {req.userId}") from exc


@app.post("/on-user-registered", dependencies=[Depends(require_internal_request)])
async def on_user_registered(req: UserRegistered):
    try:
        server_logger.info("request", f"User registration trigger received for: {req.userId}")
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_user_by_id, req.userId)
        if not user:
            server_logger.error("request", f"User not found in database: {req.userId}")
            raise HTTPException(status_code=404, detail="User not found")

        schedule_user_from_db(user)
        server_logger.info("request", f"Automation scheduled for newly registered user: {req.userId}")
        return {"status": "accepted", "message": f"Automation scheduled for user {req.userId}"}
    except HTTPException:
        raise
    except Exception as exc:
        server_logger.error(
            "request",
            f"Failed to schedule automation for newly registered user {req.userId}: {mask_sensitive_text(exc)}",
        )
        raise HTTPException(status_code=500, detail=f"Failed to schedule automation for user {req.userId}") from exc


@app.post("/verify-login", dependencies=[Depends(require_internal_request)])
async def verify_login(req: CredentialVerificationRequest, request: Request):
    retry_after = _check_verify_login_rate_limit(request, req.userId)
    if retry_after:
        server_logger.warn("request", f"verify-login rate limit exceeded for user: {req.userId}")
        return _rate_limit_response(retry_after)

    try:
        server_logger.info("request", f"Login verification requested for: {req.userId}")
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(executor, verify_user_login, req.userId, req.password)
        status_code = 200 if result.get("success") else 401
        if result.get("success"):
            _reset_verify_login_account_rate_limit(req.userId)
        return JSONResponse(status_code=status_code, content=result)
    except Exception as exc:
        server_logger.error("request", f"Login verification failed for {req.userId}: {mask_sensitive_text(exc)}")
        raise HTTPException(status_code=500, detail="Login verification failed") from exc


@app.post("/trigger-daily", dependencies=[Depends(require_internal_request)])
async def trigger_daily():
    try:
        server_logger.info("request", "Manual daily automation trigger received")
        await run_daily_automation()
        return {"status": "accepted", "message": "Daily automation triggered for all users"}
    except Exception as exc:
        server_logger.error("request", f"Failed to trigger daily automation: {mask_sensitive_text(exc)}")
        raise HTTPException(status_code=500, detail="Failed to trigger daily automation") from exc
