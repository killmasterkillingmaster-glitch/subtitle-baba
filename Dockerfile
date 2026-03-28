# Use Debian Bullseye (Contains FFmpeg 4.3 which is compatible with PyAV)
FROM python:3.10-slim-bullseye

# Set working directory
WORKDIR /app

# Install FFmpeg and the exact development tools needed for Python to compile AV
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    pkg-config \
    build-essential \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file
COPY requirements.txt .

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Now install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot script
COPY main.py .

# Expose port for Render web service binding
EXPOSE 8080

# Command to run the bot
CMD ["python", "main.py"]
