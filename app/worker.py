from __future__ import annotations

import logging
import signal
import time

from app.config import settings
from app.database import SessionLocal, run_migrations
from app.logging_config import configure_logging
from app.services.outbox_service import claim_jobs, process_job, worker_identity

configure_logging()
logger = logging.getLogger("integration-worker")
_stop = False


def _handle_signal(signum, _frame) -> None:
    global _stop
    logger.info("Sinal %s recebido; encerrando worker.", signum)
    _stop = True


def main() -> None:
    if settings.run_migrations_on_startup:
        run_migrations()
    worker_id = worker_identity()
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    logger.info("Worker iniciado", extra={"worker_id": worker_id})
    while not _stop:
        processed = 0
        with SessionLocal() as db:
            jobs = claim_jobs(db, worker_id)
            for job in jobs:
                process_job(db, job)
                processed += 1
        if processed == 0:
            time.sleep(settings.worker_poll_seconds)
    logger.info("Worker finalizado", extra={"worker_id": worker_id})


if __name__ == "__main__":
    main()
