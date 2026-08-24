FROM python:3.11-slim
RUN pip install --no-cache-dir pyzmq numpy
COPY zmq_relay.py /zmq_relay.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
CMD ["/entrypoint.sh"]
