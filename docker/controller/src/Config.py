import logging
from typing import Dict, Optional, Any

class Config:
    filename : str = ""
    options : Optional[Dict[str,Any]] = None
    log_level : int = logging.DEBUG
