FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && apt-get install -y \
    iputils-ping \
    gcc \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ping_monitor.py ./
COPY Templates/ ./Templates/

RUN groupadd -g 1000 monitor && \
    useradd -u 1000 -g monitor -d /app monitor && \
    chown -R monitor:monitor /app

RUN mkdir -p /app/data && chown -R monitor:monitor /app/data

USER monitor

VOLUME /app/data

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

CMD ["sh", "-c", "python ping_monitor.py & python app.py"]
