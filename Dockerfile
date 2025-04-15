FROM python:3.11-slim

WORKDIR /app

# Install required packages for pyserial and general dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/ .

# Create directory for data
RUN mkdir -p data

# Expose port if needed for web interface (can be added later)
# EXPOSE 8000

# Run the application
CMD ["python", "main.py"]