# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all code
COPY . .

# Expose port for Flask health check
EXPOSE 10000

# Run the bot
CMD ["python", "main.py"]
