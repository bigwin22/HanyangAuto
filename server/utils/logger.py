import os
import logging
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional
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
    def __init__(self, log_type: str = 'system', user_id: Optional[str] = None, default_fields: Optional[Dict[str, Any]] = None):
        self.log_type = log_type
        self.user_id = user_id
        self.current_date = None
        self.logger = logging.getLogger(f'{log_type}_{user_id or "system"}')
        self.logger.setLevel(logging.DEBUG)
        self.file_handler = None
        self.default_fields = default_fields.copy() if default_fields else {}
        self._setup_logger()

    def _setup_logger(self):
        """로거 설정을 초기화하거나 업데이트합니다."""
        self.close()
        
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

    def close(self):
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            try:
                handler.flush()
            except Exception:
                pass
            try:
                handler.close()
            except Exception:
                pass

    def _check_date_change(self):
        """날짜가 바뀌었는지 확인하고 필요시 로거를 재설정합니다."""
        current_date = datetime.now(KST).strftime('%Y%m%d')
        if self.current_date != current_date:
            self._setup_logger()

    @staticmethod
    def new_run_id(prefix: str = "run") -> str:
        timestamp = datetime.now(KST).strftime('%Y%m%d-%H%M%S')
        return f"{prefix}-{timestamp}-{uuid.uuid4().hex[:8]}"

    def with_context(self, **fields):
        merged = self.default_fields.copy()
        merged.update({key: value for key, value in fields.items() if value is not None})
        return HanyangLogger(self.log_type, self.user_id, default_fields=merged)

    def _stringify_value(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "-"
        if isinstance(value, float):
            return f"{value:.3f}".rstrip("0").rstrip(".")
        if isinstance(value, (list, tuple, set)):
            return "[" + ",".join(self._stringify_value(item) for item in value) + "]"
        text = str(value).replace("\n", "\\n").strip()
        if not text:
            return "-"
        if any(char.isspace() for char in text) or "|" in text or "=" in text:
            escaped = text.replace('"', '\\"')
            return f'"{escaped}"'
        return text

    def _format_fields(self, fields: Dict[str, Any]) -> str:
        merged = self.default_fields.copy()
        merged.update({key: value for key, value in fields.items() if value is not None})
        if not merged:
            return ""
        ordered = []
        if "event" in merged:
            ordered.append(("event", merged.pop("event")))
        for key in sorted(merged.keys()):
            ordered.append((key, merged[key]))
        return " | " + " ".join(f"{key}={self._stringify_value(value)}" for key, value in ordered)

    def log(self, level, subject, message, **fields):
        self._check_date_change()  # 날짜 변경 확인
        extra = {'subject': subject}
        if level not in LOG_LEVELS:
            level = 'INFO'
        rendered_message = f"{message}{self._format_fields(fields)}"
        self.logger.log(LOG_LEVELS[level], rendered_message, extra=extra)

    def event(self, subject, event, message="", level="INFO", **fields):
        payload = {"event": event}
        payload.update(fields)
        self.log(level, subject, message or event, **payload)

    def info(self, subject, message, **fields):
        self.log('INFO', subject, message, **fields)

    def warn(self, subject, message, **fields):
        self.log('WARN', subject, message, **fields)

    def error(self, subject, message, **fields):
        self.log('ERROR', subject, message, **fields)

    def debug(self, subject, message, **fields):
        self.log('DEBUG', subject, message, **fields)

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

# 사용 예시:
# logger = HanyangLogger('system')
# logger.info('system', '서버가 시작되었습니다.')
# logger = HanyangLogger('user', user_id='student001')
# logger.error('user:student001', '로그인 실패') 
