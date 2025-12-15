FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    snmp \
    curl \
    openjdk-11-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Verify Java works
RUN java -version

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY . /app/backend/

RUN touch /app/backend/__init__.py

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
