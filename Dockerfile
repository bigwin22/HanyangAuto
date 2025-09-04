FROM node:18-slim as builder

WORKDIR /app/web

COPY web/package.json web/package-lock.json ./
COPY web/ ./

RUN npm install
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

# 크롬 실행에 필요한 라이브러리들을 설치합니다.
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    # --- Xvfb 가상 디스플레이 설치 ---
    xvfb \
    x11-utils \
    x11-xserver-utils \
    # --- 크롬 의존성 라이브러리 추가 ---
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libexpat1 \
    libgbm1 \
    libasound2 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libu2f-udev \
    libxcb1 \
    fonts-liberation \
    libappindicator3-1 \
    # --- ---
    && rm -rf /var/lib/apt/lists/*

# 크롬과 크롬 드라이버를 설치합니다.
RUN STABLE=$(wget -q -O - https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE) && \
    wget -q https://storage.googleapis.com/chrome-for-testing-public/${STABLE}/linux64/chrome-linux64.zip -O /tmp/chrome.zip && \
    wget -q https://storage.googleapis.com/chrome-for-testing-public/${STABLE}/linux64/chromedriver-linux64.zip -O /tmp/chromedriver.zip && \
    unzip /tmp/chrome.zip -d /opt/ && \
    unzip /tmp/chromedriver.zip -d /opt/ && \
    rm /tmp/chrome.zip /tmp/chromedriver.zip && \
    mv /opt/chrome-linux64 /opt/chrome && \
    mv /opt/chromedriver-linux64 /opt/chromedriver && \
    ln -s /opt/chrome/chrome /usr/bin/chrome && \
    ln -s /opt/chromedriver/chromedriver /usr/bin/chromedriver

# 필요한 파일 및 디렉토리만 명시적으로 복사합니다.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY main.py .
COPY automation.py .
COPY utils/ ./utils/
COPY shFILES/ ./shFILES/

# 빌드된 프론트엔드 파일 복사
COPY --from=builder /app/web/dist/spa /app/web/dist/spa

# 애플리케이션을 비루트 사용자로 실행하도록 설정합니다.
RUN groupadd -g 1000 app \
    && useradd -m -u 1000 -g 1000 app \
    && mkdir -p /app/data /app/logs \
    && chown -R app:app /app

# Xvfb 시작 스크립트 생성
RUN echo '#!/bin/bash\n\
# Xvfb 가상 디스플레이 시작\n\
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &\n\
export DISPLAY=:99\n\
# 애플리케이션 시작\n\
exec "$@"' > /app/start.sh && chmod +x /app/start.sh

# 모든 프로세스/셸에서 DISPLAY 기본값 설정
ENV DISPLAY=:99

USER app

# Informational expose; actual runtime port is controlled by $PORT
EXPOSE 8000 8001

# Xvfb를 시작하고 애플리케이션 실행
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-2}"]
