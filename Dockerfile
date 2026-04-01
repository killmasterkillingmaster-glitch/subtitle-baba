FROM python:3.10.8-slim-buster

# Set working directory
WORKDIR /app

# Copy all files from GitHub to /app folder in Docker
COPY . /app

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Port for Render Free Tier (Very Important)
EXPOSE 10000

# Run the bot
CMD ["python", "main.py"]
