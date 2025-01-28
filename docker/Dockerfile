ARG OS_VERSION=24.04
ARG LIB=uhd
ARG LIB_VERSION=4.7.0.0
ARG MARCH=native
ARG NUM_CORES=""

FROM ubuntu:$OS_VERSION

ENV CONFIG="configs/zmq/ue_zmq_docker.conf"
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y \
    cmake \
    make \
    gcc \
    g++ \
    pkg-config \
    libfftw3-dev \
    libmbedtls-dev \
    libsctp-dev \
    libyaml-cpp-dev \
    libgtest-dev \
    libzmq3-dev \
    net-tools \
    libboost-all-dev \
    libconfig++-dev \
    iperf3 \
    git \
    libxcb-cursor0 \
    libgles2-mesa-dev \
    gr-osmosdr \
    iproute2 \
   uhd-host \
    libuhd-dev


RUN mkdir -p /app

WORKDIR /app

COPY CMakeLists.txt .
COPY lib lib
COPY srsue srsue
COPY cmake cmake
COPY cmake_uninstall.cmake.in .
COPY CTestConfig.cmake .
COPY CTestCustom.cmake.in .

RUN mkdir -p /app/build

WORKDIR /app/build

RUN cmake ../ && \
    make -j$(nproc) && \
    make install && \
    srsran_install_configs.sh user && \
    ldconfig

WORKDIR /app

COPY configs configs

CMD [ "sh", "-c", "/usr/local/bin/srsue \"${CONFIG}\" $ARGS" ]
