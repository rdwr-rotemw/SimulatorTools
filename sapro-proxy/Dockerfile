FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl openssl snmp \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pymongo

WORKDIR /app

COPY proxy/ /app/proxy/

RUN mkdir -p /app/certs

CMD ["python", "-m", "proxy.server", "--driver-dir", "/app/backend/app/resources/device_drivers"]
