FROM python:3.11-slim

WORKDIR /app

# Install basic system tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    coreutils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV PYTHONUNBUFFERED=1
# Force psutil to use host proc filesystem
ENV PROCFS_PATH=/host/proc

CMD ["python", "src/main.py"]
