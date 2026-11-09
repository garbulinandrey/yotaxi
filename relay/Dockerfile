FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN mkdir /data && chown 10001:10001 /data
COPY --chown=10001:10001 app.py inspect_counts.py ./
COPY --chown=10001:10001 tests ./tests
USER 10001:10001
CMD ["python", "app.py"]
