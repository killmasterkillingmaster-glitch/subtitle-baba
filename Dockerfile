# ---------------- BASE IMAGE ----------------
FROM python:3.11-slim

# ---------------- ENV SETUP ----------------
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=10000

# ---------------- WORKDIR ----------------
WORKDIR /app

# ---------------- COPY FILES ----------------
COPY . /app

# ---------------- SYSTEM DEPENDENCIES ----------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libssl-dev \
        python3-dev \
        curl \
        ffmpeg \
        && rm -rf /var/lib/apt/lists/*

# ---------------- PYTHON DEPENDENCIES ----------------
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# ---------------- EXPOSE PORT ----------------
EXPOSE ${PORT}

# ---------------- RUN BOT ----------------
CMD ["python", "bot.py"]
