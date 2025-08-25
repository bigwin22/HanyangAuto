import os
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional
from logging.handlers import RotatingFileHandler

# 서울 시간대
KST = ZoneInfo('Asia/Seoul')

def kst_time_converter(seconds: Optional[float] = None) -> time.struct_time:
    if seconds is None:
        seconds = time.time()
    return datetime.fromtimestamp(seconds, KST).timetuple()

LOG_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')

# 로그 종류
LOG_LEVELS = {
    'INFO': logging.INFO,
    'WARN': logging.WARNING,
    'ERROR': logging.ERROR,
    'DEBUG': logging.DEBUG,
}

MAX_LOG_SIZE = 5 * 1024 * 1024  # 5MB
BACKUP_COUNT = 10  # log1~log10까지 유지

import re

def sanitize_filename(filename):
    """파일 이름으로 사용하기에 안전하지 않은 문자를 제거합니다."""
    return re.sub(r'[^a-zA-Z0-9_.-]', '', filename)

def get_log_path(log_type: str = 'system', user_id: Optional[str] = None):
    today = datetime.now(KST).strftime('%Y%m%d')
    base = os.path.join(LOG_BASE, today)
    if log_type == 'system':
        path = os.path.join(base, 'system')
    elif log_type == 'users':
        path = os.path.join(base, 'user', 'users')
    elif user_id:
        safe_user_id = sanitize_filename(user_id)
        path = os.path.join(base, 'user', safe_user_id)
    else:
        path = os.path.join(base, 'system')
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, f'log1.log')

class HanyangLogger:
    def __init__(self, log_type: str = 'system', user_id: Optional[str] = None):
        self.log_type = log_type
        self.user_id = user_id
        self.current_date = None
        self.logger = logging.getLogger(f'{log_type}_{user_id or "system"}')
        self.logger.setLevel(logging.DEBUG)
        self.file_handler = None
        self._setup_logger()

    def _setup_logger(self):
        """로거 설정을 초기화하거나 업데이트합니다."""
        # 기존 핸들러 제거
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        self.logger.propagate = False
        
        # 현재 날짜 확인
        current_date = datetime.now(KST).strftime('%Y%m%d')
        
        # 날짜가 바뀌었거나 처음 설정하는 경우
        if self.current_date != current_date:
            self.current_date = current_date
            self.log_path = get_log_path(self.log_type, self.user_id)
            
            # File handler
            self.file_handler = RotatingFileHandler(
                self.log_path, maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT, encoding='utf-8'
            )
            formatter = logging.Formatter('[%(asctime)s][%(subject)s][%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            # 로거의 asctime을 KST로 강제
            formatter.converter = kst_time_converter
            self.file_handler.setFormatter(formatter)
            self.logger.addHandler(self.file_handler)
            
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

    def _check_date_change(self):
        """날짜가 바뀌었는지 확인하고 필요시 로거를 재설정합니다."""
        current_date = datetime.now(KST).strftime('%Y%m%d')
        if self.current_date != current_date:
            self._setup_logger()

    def log(self, level, subject, message):
        self._check_date_change()  # 날짜 변경 확인
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