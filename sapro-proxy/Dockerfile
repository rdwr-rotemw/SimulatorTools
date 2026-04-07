FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY proxy/ /app/proxy/

EXPOSE 8888

CMD ["python", "-m", "proxy.server", "--port", "8888", "--driver-dir", "/app/device_drivers"]
