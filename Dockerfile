FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 10000
CMD ["python3", "main.py"]
