# SLIM image use NAHI karni hai. Full image pre-compiled wheels ko support karti hai.
FROM python:3.10

# Sirf FFmpeg CLI tool chahiye, koi C-compilation libraries (gcc, dev) nahi.
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file first
COPY requirements.txt .

# Pip upgrade karein
RUN pip install --no-cache-dir --upgrade pip

# Dependencies install karein (Ab yeh compile nahi karega, direct binary download karega!)
RUN pip install --no-cache-dir -r requirements.txt

# Baaki saare files copy karein
COPY . .

# Render ke liye port expose karein
EXPOSE 8080

# Bot start command
CMD ["python", "main.py"]
