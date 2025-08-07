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

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
