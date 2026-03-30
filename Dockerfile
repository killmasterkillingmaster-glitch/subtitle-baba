FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg libsm6 libxext6 build-essential && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy all files
COPY . /app

# Upgrade pip and install dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir pyrogram==2.0.34 tgcrypto aiohttp flask

# Expose PORT for Flask (optional)
EXPOSE 10000

# Run bot
CMD ["python", "main.py"]
