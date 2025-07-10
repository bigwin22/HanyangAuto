import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

# 서울 시간대
KST = timezone(timedelta(hours=9))

LOG_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')

# 로그 종류
LOG_LEVELS = {
    'INFO': logging.INFO,
    'WARN': logging.WARNING,
    'ERROR': logging.ERROR,
    'DEBUG': logging.DEBUG,
}

def get_log_path(log_type: str = 'system', user_id: Optional[str] = None):
    today = datetime.now(KST).strftime('%Y%m%d')
    base = os.path.join(LOG_BASE, today)
    if log_type == 'system':
        path = os.path.join(base, 'system')
    elif log_type == 'users':
        path = os.path.join(base, 'user', 'users')
    elif user_id:
        path = os.path.join(base, 'user', user_id)
    else:
        path = os.path.join(base, 'system')
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, f'log1.log')

class HanyangLogger:
    def __init__(self, log_type: str = 'system', user_id: Optional[str] = None):
        self.log_type = log_type
        self.user_id = user_id
        self.log_path = get_log_path(log_type, user_id)
        self.logger = logging.getLogger(f'{log_type}_{user_id or "system"}')
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_path, encoding='utf-8')
            formatter = logging.Formatter('[%(asctime)s][%(subject)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log(self, level, subject, message):
        extra = {'subject': subject}
        if level not in LOG_LEVELS:
            level = 'INFO'
        self.logger.log(LOG_LEVELS[level], message, extra=extra)

    def info(self, subject, message):
        self.log('INFO', subject, message)

    def warn(self, subject, message):
        self.log('WARN', subject, message)

    def error(self, subject, message):
        self.log('ERROR', subject, message)

    def debug(self, subject, message):
        self.log('DEBUG', subject, message)

# 사용 예시:
# logger = HanyangLogger('system')
# logger.info('system', '서버가 시작되었습니다.')
# logger = HanyangLogger('user', user_id='student001')
# logger.error('user:student001', '로그인 실패') 