FROM python:3.11-slim

WORKDIR /app

# Copy files
COPY main.py requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for web server
EXPOSE 8080

# Start bot
CMD ["python", "main.py"]
