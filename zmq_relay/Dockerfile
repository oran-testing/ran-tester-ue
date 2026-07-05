FROM python:3.11-slim
RUN pip install --no-cache-dir pyzmq numpy
COPY zmq_relay.py /zmq_relay.py
CMD ["python3", "/zmq_relay.py"]
