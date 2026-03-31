# Base image
FROM python:3.10-slim

# Set Working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all the remaining files to container
COPY . .

# Run the python script
CMD ["python", "main.py"]
