import logging
import os
import sys

import click
from redis import Redis
from rq import Queue


def setup_logging():
    # Use the uvicorn access logger format for consistency
    log_format = "%(levelname)s:     %(asctime)s - %(name)s - %(message)s"

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        stream=sys.stdout,
    )

    return logging.getLogger("nexus-ingestion-enqueuer")


logger = setup_logging()


@click.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True))
def ingest(directory):
    logger.info(f"Enqueuing ingestion jobs for {directory}...")
    
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_conn = Redis.from_url(redis_url)
    queue = Queue(connection=redis_conn)
    
    job_count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            path = os.path.join(root, file)
            if file.endswith('.pdf') or file.endswith('.docx') or file.endswith('.txt'):
                # Enqueue background task
                queue.enqueue("worker.process_file_job", path, job_timeout="1h")
                job_count += 1
                
    logger.info(f"Successfully enqueued {job_count} documentation files for asynchronous ingestion by Worker nodes!")

if __name__ == "__main__":
    ingest()
