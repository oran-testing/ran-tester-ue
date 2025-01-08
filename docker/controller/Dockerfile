ARG OS_VERSION=24.04
ARG LIB=uhd
ARG LIB_VERSION=4.7.0.0
ARG MARCH=native
ARG NUM_CORES=""

FROM ubuntu:$OS_VERSION

ENV CONFIG="configs/basic_ue_zmq.yaml"
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        iperf3 \
        iproute2 \
        inetutils-ping \
        docker.io


WORKDIR /app

COPY ./src .
COPY ./configs configs




WORKDIR /app/

CMD python3 main.py --config $CONFIG --docker 1

