from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import os

from tasks import run_user_automation
import utils.database as db
from utils.logger import HanyangLogger
from utils.database import decrypt_password

app = FastAPI()

class AutomationRequest(BaseModel):
    user_id: str

def db_add_learned(user_id, lecture_id):
    user = db.get_user_by_id(user_id)
    if user:
        db.add_learned_lecture(user[0], lecture_id)

def run_automation_task(user_id: str):
    system_logger = HanyangLogger('system')
    user_logger = HanyangLogger('user', user_id=user_id)
    
    user = db.get_user_by_id(user_id)
    if not user:
        system_logger.error('automation', f'자동화 실패: 유저 없음 {user_id}')
        return

    try:
        pwd = decrypt_password(user[2])
        learned = db.get_learned_lectures(user[0])
        
        system_logger.info('automation', f'자동화 시작: {user_id}')
        user_logger.info('automation', '자동화 시작')
        
        result = run_user_automation(user_id, pwd, learned, db_add_learned)
        
        if result['success']:
            system_logger.info('automation', f'자동화 완료: {user_id} ({result["msg"]})')
            user_logger.info('automation', f'자동화 완료: {result["msg"]}')
        else:
            system_logger.error('automation', f'자동화 실패: {user_id} ({result["msg"]})')
            user_logger.error('automation', f'자동화 실패: {result["msg"]}')
            
    except Exception as e:
        system_logger.error('automation', f'자동화 중 예외 발생: {user_id}, {e}')
        user_logger.error('automation', f'자동화 중 예외 발생: {e}')

@app.post("/run-automation")
def trigger_automation(req: AutomationRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_automation_task, req.user_id)
    return {"success": True, "message": f"Automation scheduled for {req.user_id}"}

HanyangLogger('system').info('system', '자동화 서비스가 시작되었습니다.')
