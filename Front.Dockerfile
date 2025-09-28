FROM python:3.11-slim

WORKDIR /app

# 필요한 파일만 복사
COPY front/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY front/main.py .
COPY utils /app/utils
COPY web/dist/spa /app/web/dist/spa

# 포트 노출
EXPOSE 8000

# 서버 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
