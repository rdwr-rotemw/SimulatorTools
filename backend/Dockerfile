FROM rockylinux:9

# Set working directory
WORKDIR /app

# Install system dependencies using dnf (Rocky Linux)
RUN dnf install -y \
    python3.11 \
    python3.11-pip \
    snmp \
    curl \
    java-17-openjdk-headless \
    && dnf clean all

# Verify Java is available
RUN java -version

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire backend directory structure
# This creates /app/backend/app/ inside the container
COPY . /app/backend/

# Create __init__.py for backend package
RUN touch /app/backend/__init__.py

# Add /app to PYTHONPATH so "from backend.app..." imports work
ENV PYTHONPATH=/app

# Expose the port
EXPOSE 8000

# Run uvicorn with the correct module path
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
