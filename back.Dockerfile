

FROM python:3.12-slim

WORKDIR /app

# 필요한 파일 및 디렉토리만 명시적으로 복사합니다.
COPY back/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY back/back.py .
COPY utils ./utils/

USER app

# API 서버 포트 설정
EXPOSE 9001

# Xvfb를 시작하고 애플리케이션 실행
CMD ["sh", "-c", "uvicorn back:app --host 0.0.0.0 --port 8001"]
