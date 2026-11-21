FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FINTRACK_HOST=0.0.0.0 FINTRACK_PORT=8020
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt && useradd -m -u 10001 fintrack && mkdir -p /data && chown -R fintrack:fintrack /data
COPY --chown=fintrack:fintrack . .
USER fintrack
EXPOSE 8020
CMD ["python","manage.py"]
