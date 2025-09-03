import logging

from typing import List, Dict, Union, Optional, Any
from influxdb_client import InfluxDBClient, WriteApi


class Config:
    filename : str = ""
    options : Optional[Dict[str,Any]] = None
    log_level : int = logging.DEBUG
    docker_client = None
    influxdb_client : InfluxDBClient = None

class Globals:
    process_metadata: List[Dict[str, Any]] = []
    controller_init_time : str = ""
