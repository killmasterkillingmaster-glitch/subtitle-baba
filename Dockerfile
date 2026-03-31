FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# Render ke liye port expose karna zaroori hai
EXPOSE 10000

CMD ["python3", "main.py"]
