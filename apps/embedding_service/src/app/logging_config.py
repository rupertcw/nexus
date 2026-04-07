import logging
import sys


def setup_logging():
    # Use the uvicorn access logger format for consistency
    log_format = "%(levelname)s:     %(asctime)s - %(name)s - %(message)s"

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        stream=sys.stdout,
    )

    return logging.getLogger("nexus-embedding-service")


# Initialize it
logger = setup_logging()