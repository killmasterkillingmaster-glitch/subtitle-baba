FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all files
COPY . .

# Data folder for JSON files
RUN mkdir -p data

# Render port
EXPOSE 10000

CMD ["python", "main.py"]
