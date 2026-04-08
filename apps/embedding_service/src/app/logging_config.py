import logging
import sys
import os

def setup_logging(logger_name: str):
    log_level = os.environ.get("LOGGING_LEVEL", "DEBUG").upper()
    log_format = "%(levelname)s:     %(asctime)s - %(name)s - %(message)s"

    # Force reconfiguration even if basicConfig was called elsewhere
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)

    logging.basicConfig(
        level=log_level,
        format=log_format,
        stream=sys.stdout,
        force=True
    )

    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)

    logger.debug(f"Logging initialized at {log_level} level")
    return logger


logger = setup_logging("nexus-embedding-service")
