# /Users/kth88/Documents/CODING/HanyangAuto/automation/receive_server.py
import os
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
import asyncio
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

# Assuming the app is run from the project root, so utils and automation are importable
from automation import run_user_automation
from utils.database import add_learned_lecture, decrypt_password, update_user_status, get_all_users, get_user_by_id, get_learned_lectures
from utils.logger import HanyangLogger

# Create a logger for the server
server_logger = HanyangLogger('server', user_id='receive_server')

# Thread pool for concurrent automation tasks, limited to 5
executor = ThreadPoolExecutor(max_workers=5)

# Scheduler for daily automation
scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Seoul"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    scheduler.start()
    scheduler.add_job(run_daily_automation, CronTrigger(hour=7, minute=0), id='daily_automation')
    server_logger.info('server', 'Scheduler started with daily automation at 7:00 AM KST')
    
    try:
        yield
    finally:
        server_logger.info('server', 'Server is shutting down. Waiting for all running jobs to complete.')
        scheduler.shutdown(wait=True)
        executor.shutdown(wait=True)

app = FastAPI(lifespan=lifespan)

class AutomationRequest(BaseModel):
    userId: str
    password: str  # This is the encrypted password
    userNum: int   # This is the user's primary key (NUM)
    learnedLectures: list

class UserRegistered(BaseModel):
    userId: str

def automation_task_wrapper(userId: str, encrypted_pwd: str, userNum: int, learnedLectures: list):
    """
    A wrapper function to handle the entire automation process for a user in a separate thread.
    It includes password decryption, setting up the database callback, and running the automation.
    """
    user_logger = HanyangLogger('user', user_id=str(userId))
    user_logger.info('automation', f'Automation task started (UserNum: {userNum})')
    
    try:
        plain_pwd = decrypt_password(encrypted_pwd)
    except Exception as e:
        user_logger.error('automation', f'Password decryption failed: {e}')
        update_user_status(userId, "error")
        return  # Stop processing for this user

    try:
        # This callback will be called as `db_add_learned(user_id, lec_url)`
        # inside run_user_automation. We ignore the passed user_id and use
        # the correct integer userNum which is the primary key.
        def db_add_learned_callback(user_id_from_automation, lecture_id):
            add_learned_lecture(userNum, lecture_id)

        # This function contains its own extensive error handling and status updates.
        run_user_automation(
            user_id=userId,
            pwd=plain_pwd,
            learned_lectures=learnedLectures,
            db_add_learned=db_add_learned_callback
        )
    except Exception as e:
        # This will catch unexpected errors from within run_user_automation
        # that were not handled internally.
        user_logger.error('automation', f'An unexpected error occurred during automation: {e}')
        try:
            update_user_status(userId, "error")
        except Exception as db_e:
            user_logger.error('automation', f'Failed to update status to error: {db_e}')

def schedule_user_from_db(user_row):
    """
    Schedule automation for a user from database row data.
    """
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
    """
    Run automation for all users in the database.
    This function is called by the scheduler at 7:00 AM daily.
    """
    server_logger.info('scheduler', 'Starting daily automation for all users')
    users = get_all_users()
    server_logger.info('scheduler', f'Found {len(users)} users for daily automation')
    
    for user in users:
        try:
            schedule_user_from_db(user)
            server_logger.info('scheduler', f'Scheduled automation for user: {user[1]}')
        except Exception as e:
            server_logger.error('scheduler', f'Failed to schedule automation for user {user[1]}: {e}')
    
    server_logger.info('scheduler', 'Daily automation scheduling completed')


@app.post("/start-automation")
async def start_automation(req: AutomationRequest):
    """
    Receives an automation job from the Core API and executes it asynchronously.
    Handles up to 5 concurrent jobs.
    """
    try:
        server_logger.info('request', f'Automation request received for user: {req.userId}')
        
        loop = asyncio.get_running_loop()
        loop.run_in_executor(
            executor,
            automation_task_wrapper,
            req.userId,
            req.password,
            req.userNum,
            req.learnedLectures
        )
        
        return {"status": "accepted", "message": f"Automation for user {req.userId} has been scheduled."}
        
    except Exception as e:
        server_logger.error('request', f'Failed to schedule automation for user {req.userId}: {e}')
        raise HTTPException(status_code=500, detail=f"Failed to schedule automation for user {req.userId}: {e}")

@app.post("/on-user-registered")
async def on_user_registered(req: UserRegistered):
    """
    Trigger automation for a newly registered user.
    Called by the Core API when a user registers or logs in.
    """
    try:
        server_logger.info('request', f'User registration trigger received for: {req.userId}')
        
        user = get_user_by_id(req.userId)
        if not user:
            server_logger.error('request', f'User not found in database: {req.userId}')
            raise HTTPException(status_code=404, detail="User not found")
        
        schedule_user_from_db(user)
        server_logger.info('request', f'Automation scheduled for newly registered user: {req.userId}')
        
        return {"status": "accepted", "message": f"Automation scheduled for user {req.userId}"}
        
    except HTTPException:
        raise
    except Exception as e:
        server_logger.error('request', f'Failed to schedule automation for newly registered user {req.userId}: {e}')
        raise HTTPException(status_code=500, detail=f"Failed to schedule automation for user {req.userId}: {e}")

@app.post("/trigger-daily")
async def trigger_daily():
    """
    Manually trigger daily automation for all users.
    Useful for testing or manual execution.
    """
    try:
        server_logger.info('request', 'Manual daily automation trigger received')
        await run_daily_automation()
        return {"status": "accepted", "message": "Daily automation triggered for all users"}
        
    except Exception as e:
        server_logger.error('request', f'Failed to trigger daily automation: {e}')
        raise HTTPException(status_code=500, detail=f"Failed to trigger daily automation: {e}")

# To run this server, execute the following command from the project root directory:
# uvicorn main:app --host 0.0.0.0 --port 7000
