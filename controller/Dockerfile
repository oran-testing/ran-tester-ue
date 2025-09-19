ARG OS_VERSION=3.18
ARG LIB=uhd
ARG LIB_VERSION=4.7.0.0
ARG MARCH=native
ARG NUM_CORES=""

FROM alpine:latest

# Set environment variables
ENV CONFIG="configs/basic_ue_zmq.yaml"
ENV PYTHONUNBUFFERED=1

# Install necessary packages (replace apt-get with apk)
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-virtualenv \
    iperf3 \
    iproute2 \
    docker-cli \
    gcc

# Set working directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN python3 -m venv venv && \
    ./venv/bin/pip install --no-cache-dir -r requirements.txt

COPY server.pem /server.pem
COPY server.key /server.key

# Copy application source code and configs
COPY ./src .

CMD ./venv/bin/python3 main.py --config /controller.yml

