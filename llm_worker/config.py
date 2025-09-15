import logging

class Config:
    filename : str = ""
    options : dict = None
    log_level : int = logging.DEBUG
    model_str : str = ""
    results_dir : str = ""


