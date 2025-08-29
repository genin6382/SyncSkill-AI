FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./

RUN apt-get update && apt-get install -y \
    default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

COPY wait-for-mysql.sh /wait-for-mysql.sh

RUN chmod +x /wait-for-mysql.sh

CMD ["/wait-for-mysql.sh", "python", "app.py"]