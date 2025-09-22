FROM node:20-alpine AS builder

WORKDIR /app/web

COPY front/web/package.json front/web/package-lock.json ./
COPY front/web/ ./

RUN npm install
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

# 필요한 파일 및 디렉토리만 명시적으로 복사합니다.
COPY front/front.py .
COPY front/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY utils/ ./utils/
COPY --from=builder /app/web/dist/spa /app/web/dist/spa

# 애플리케이션을 비루트 사용자로 실행하도록 설정합니다.
RUN groupadd -g 1000 app \
    && useradd -m -u 1000 -g 1000 app \
    && mkdir -p /app/data /app/logs \
    && chown -R app:app /app

USER app

# Informational expose; actual runtime port is controlled by $PORT
EXPOSE 8000 8001

CMD ["sh", "-c", "uvicorn front:app --host 0.0.0.0 --port ${PORT:-8000}"]