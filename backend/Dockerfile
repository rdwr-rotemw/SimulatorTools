FROM rockylinux:9

# Enable EPEL and PowerTools repos for python3.11 and java
RUN dnf install -y epel-release && \
    dnf config-manager --set-enabled crb && \
    dnf install -y \
    python3.11 \
    python3.11-pip \
    snmp \
    curl \
    java-17-openjdk-headless \
    && dnf clean all

# Set python3.11 as default
RUN alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.11 1

# Set working directory
WORKDIR /app

# Install system dependencies verified: Java
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
