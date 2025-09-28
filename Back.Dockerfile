FROM python:3.11-slim

WORKDIR /app

# 의존성 설치
COPY back/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스코드 복사
COPY back/main.py .
COPY utils /app/utils

# 데이터 및 로그 디렉토리 생성 및 권한 설정
RUN mkdir -p /app/data /app/logs && \
    chown -R 1000:1000 /app/data /app/logs

# 포트 노출
EXPOSE 8001

# 서버 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
