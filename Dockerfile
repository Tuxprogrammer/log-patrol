FROM python:3.12-alpine

RUN apk add --no-cache tzdata

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config.yml ./config.yml
COPY run.sh ./run.sh
RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]
