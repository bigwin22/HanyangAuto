FROM python:3.12-slim

WORKDIR /app
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

COPY /automation/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install --with-deps chromium

COPY automation/ ./automation/
COPY utils/ ./utils/

RUN groupadd -g 1000 app \
    && useradd -m -u 1000 -g 1000 app \
    && mkdir -p /app/data /app/logs \
    && chown -R app:app /app /ms-playwright

USER app

CMD ["uvicorn", "automation.main:app", "--host", "0.0.0.0", "--port", "7000"]
