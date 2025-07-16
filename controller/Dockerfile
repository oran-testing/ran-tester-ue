FROM alpine:latest

ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-virtualenv \
    iperf3 \
    iproute2 \
    docker-cli \
    gcc

WORKDIR /app

COPY requirements.txt .
RUN python3 -m venv venv && \
    ./venv/bin/pip install --no-cache-dir -r requirements.txt

COPY ./src .

COPY server.pem /server.pem
COPY server.key /server.key

CMD ./venv/bin/python3 main.py --config /controller.yml
