FROM python:3.12-slim

WORKDIR /app

# 필요한 파일 및 디렉토리만 명시적으로 복사합니다.
COPY back/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY back/back.py .
COPY utils/database.py ./utils/
COPY utils/logger.py ./utils/


# 애플리케이션을 비루트 사용자로 실행하도록 설정합니다.
RUN groupadd -g 1000 app \
    && useradd -m -u 1000 -g 1000 app \
    && mkdir -p /app/data /app/logs \
    && chown -R app:app /app

USER app

# Informational expose; actual runtime port is controlled by $PORT
EXPOSE 8000 8001

# Xvfb를 시작하고 애플리케이션 실행
CMD ["sh", "-c", "uvicorn back:app --host 0.0.0.0 --port ${PORT:-8000}"]
