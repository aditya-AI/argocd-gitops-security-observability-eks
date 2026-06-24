from __future__ import annotations

import os
import time

from worker.db import get_conn
from worker.observability import configure_observability, get_tracer


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _maybe_allocate_memory() -> None:
    allocate_mb = _env_int("ALLOCATE_MB", 0)
    if allocate_mb <= 0:
        return

    # Intentional drill hook: allocate a big chunk of memory.
    # This is here so you can demonstrate OOMKilled with low memory limits.
    _ = bytearray(allocate_mb * 1024 * 1024)


def run_once(tracer) -> bool:
    with tracer.start_as_current_span("worker.run_once") as span:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH picked AS (
                      SELECT id
                      FROM jobs
                      WHERE status = 'pending'
                      ORDER BY created_at
                      FOR UPDATE SKIP LOCKED
                      LIMIT 1
                    )
                    UPDATE jobs
                    SET status = 'processing', updated_at = now()
                    WHERE id IN (SELECT id FROM picked)
                    RETURNING id
                    """
                )
                row = cur.fetchone()

                if row is None:
                    span.set_attribute("worker.job_found", False)
                    return False

                (job_id,) = row
                span.set_attribute("worker.job_found", True)
                span.set_attribute("worker.job_id", str(job_id))
                print(f"processing job {job_id}", flush=True)

                _maybe_allocate_memory()

                # Simulate work.
                time.sleep(_env_int("WORK_SECONDS", 1))

                cur.execute(
                    "UPDATE jobs SET status = 'done', updated_at = now() WHERE id = %s",
                    (job_id,),
                )
                print(f"completed job {job_id}", flush=True)

                return True


def main() -> None:
    configure_observability()
    tracer = get_tracer(__name__)
    poll_seconds = max(1, _env_int("POLL_SECONDS", 2))
    print("worker started", flush=True)

    while True:
        try:
            did_work = run_once(tracer)
        except Exception as e:  # noqa: BLE001
            print(f"worker error: {e}", flush=True)
            did_work = False

        if not did_work:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
