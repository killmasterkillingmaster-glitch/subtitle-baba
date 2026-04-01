FROM python:3.10.8-slim-buster

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# Render port configuration
EXPOSE 10000

CMD ["python3", "main.py"]
