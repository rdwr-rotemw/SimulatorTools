FROM python:3.11-slim

WORKDIR /app

# Install system dependencies - ONLY ADD default-jre-headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    snmp \
    curl \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend directory structure
COPY . /app/backend/

# Create __init__.py for backend package
RUN touch /app/backend/__init__.py

# Add /app to PYTHONPATH
ENV PYTHONPATH=/app

# Expose the port
EXPOSE 8000

# Run uvicorn with the correct module path
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
