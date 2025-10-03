FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies
COPY back/requirements.txt ./
RUN pip install --no-cache-dir -r ./requirements.txt

# Copy application code
COPY back/main.py ./
COPY utils/ ./utils/

# Non-root user
RUN groupadd -g 1000 app && useradd -m -u 1000 -g 1000 app
RUN mkdir -p /app/data /app/logs && chown -R app:app /app/
USER app


EXPOSE 9000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
