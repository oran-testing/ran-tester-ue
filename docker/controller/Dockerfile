FROM ubuntu:22.04

ENV CONFIG="configs/basic_ue_zmq.yaml"
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        build-essential \
        git \
        iperf3 \
        iproute2 \
        inetutils-ping


WORKDIR /app

COPY pyproject.toml .
COPY ./src .
COPY ./configs configs

RUN pip3 install --no-cache-dir poetry

RUN poetry install --only main


WORKDIR /app/

CMD poetry run python3 main.py --config $CONFIG --docker 1
