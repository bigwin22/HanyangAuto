# Stage 1: Build the React app
FROM node:18-slim as builder

WORKDIR /app

# Copy the rest of the web app source
COPY front/web/ ./

RUN npm install
RUN npm run build:client # only build client

# Stage 2: Serve the frontend with FastAPI
FROM python:3.12-slim

WORKDIR /app

# Install dependencies for frontend server
COPY front/requirements.txt ./
RUN pip install --no-cache-dir -r ./requirements.txt

# Copy application code
COPY front/main.py ./

# Copy built React app from builder stage
COPY --from=builder /app/ ./web/
COPY utils/ ./utils/

# Non-root user
RUN useradd -m -u 1000 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
