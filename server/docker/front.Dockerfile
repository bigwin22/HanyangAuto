# Stage 1: Build the React app
FROM node:18-slim AS builder

WORKDIR /app

COPY front/web/ ./

RUN npm ci
RUN npm run build:client

# Stage 2: Serve the frontend with FastAPI
FROM python:3.12-slim

WORKDIR /app

# Install dependencies for frontend server
COPY front/requirements.txt ./
RUN pip install --no-cache-dir -r ./requirements.txt

COPY front/main.py ./
COPY --from=builder /app/dist/spa ./web/dist/spa
COPY front/web/client/public ./web/client/public
COPY utils/ ./utils/

RUN useradd -m -u 1000 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
