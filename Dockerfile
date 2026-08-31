FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PORT=5001

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY app.py grabber.py entrypoint.sh ./
COPY templates ./templates
RUN chmod +x entrypoint.sh && mkdir -p downloads

EXPOSE 5001

ENTRYPOINT ["/app/entrypoint.sh"]
