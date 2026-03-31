# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# Environment variables
ENV API_ID=123456
ENV API_HASH=abc123def456ghi789
ENV BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
ENV OWNER_ID=5351848105
ENV MONGO_URI="mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority"
ENV STORAGE_CHANNEL_ID=-1003096528862
ENV PORT=10000

EXPOSE 10000

CMD ["python3", "main.py"]
