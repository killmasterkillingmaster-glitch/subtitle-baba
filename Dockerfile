# Use official Python slim image
FROM python:3.11-slim

# --- ENVIRONMENT VARIABLES ---
ENV PYTHONUNBUFFERED=1 \
    PORT=10000

# --- SYSTEM DEPENDENCIES ---
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    libsndfile1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# --- WORKDIR ---
WORKDIR /app

# --- COPY REQUIREMENTS ---
COPY requirements.txt .

# --- INSTALL PYTHON DEPENDENCIES ---
RUN pip install --no-cache-dir -r requirements.txt

# --- COPY BOT CODE ---
COPY . .

# --- EXPOSE PORT FOR WEB SERVER ---
EXPOSE 10000

# --- ENTRYPOINT ---
CMD ["python", "main.py"]
