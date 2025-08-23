FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install system dependencies
RUN apt-get update && apt-get install -y \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py ping_monitor.py ./
COPY index.html ./
COPY Templates/ ./Templates/
COPY static/ ./static/

# Create user and group
RUN groupadd -g 1000 monitor && \
    useradd -u 1000 -g monitor -d /app monitor && \
    chown -R monitor:monitor /app

# Create data directory
RUN mkdir -p /app/data && chown -R monitor:monitor /app/data

USER monitor

VOLUME /app/data

# Run both services
CMD ["sh", "-c", "python ping_monitor.py & python app.py"]
