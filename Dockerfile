FROM python:3.11-slim

WORKDIR /app

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sab files copy
COPY . .

# Data folder (JSON files ke liye)
RUN mkdir -p data

EXPOSE 10000

CMD ["python", "main.py"]
