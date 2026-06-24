from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from hashlib import sha256
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.db import get_conn
from app.observability import configure_observability

_STATE_LOCK = Lock()
_STARTED_AT = time.monotonic()
_DRAINING = False


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _uptime_seconds() -> float:
    return max(0.0, time.monotonic() - _STARTED_AT)


def _set_draining(value: bool) -> None:
    global _DRAINING
    with _STATE_LOCK:
        _DRAINING = value


def _is_draining() -> bool:
    with _STATE_LOCK:
        return _DRAINING


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _STARTED_AT
    _STARTED_AT = time.monotonic()
    _set_draining(False)
    yield


app = FastAPI(title="gitops-demo-api", lifespan=lifespan)
configure_observability(app)


@app.get("/startupz")
def startupz() -> JSONResponse:
    required = max(0, _env_int("STARTUP_DELAY_SECONDS", 0))
    uptime = _uptime_seconds()
    if uptime < required:
        return JSONResponse(
            status_code=503,
            content={
                "started": False,
                "reason": "startup delay still in effect",
                "remaining_seconds": round(required - uptime, 2),
            },
        )
    return JSONResponse(status_code=200, content={"started": True, "uptime_seconds": round(uptime, 2)})


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "service": "gitops-demo-api"}


@app.get("/loadz")
def loadz(cpu_ms: int = 250, payload_kb: int = 64) -> dict:
    """Burn CPU on demand so HPA demos are deterministic on local clusters."""

    cpu_ms = max(25, min(cpu_ms, 5000))
    payload_kb = max(1, min(payload_kb, 512))

    payload = b"x" * (payload_kb * 1024)
    deadline = time.perf_counter() + (cpu_ms / 1000.0)
    loops = 0
    digest = payload

    while time.perf_counter() < deadline:
        digest = sha256(digest).digest()
        loops += 1

    return {
        "ok": True,
        "cpu_ms": cpu_ms,
        "payload_kb": payload_kb,
        "loops": loops,
        "digest_prefix": digest.hex()[:16],
    }


@app.get("/readyz")
def readyz() -> JSONResponse:
    if _is_draining():
        return JSONResponse(status_code=503, content={"ready": False, "reason": "draining for shutdown"})

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.execute(
                    "SELECT to_regclass('public.jobs') is not null as jobs_table_present"
                )
                (present,) = cur.fetchone()
        if not present:
            return JSONResponse(
                status_code=503,
                content={"ready": False, "reason": "migrations not applied (jobs table missing)"},
            )
        return JSONResponse(status_code=200, content={"ready": True})
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"ready": False, "reason": str(e)})


@app.post("/drain")
def drain() -> dict:
    _set_draining(True)
    return {
        "draining": True,
        "sleep_hint_seconds": max(0, _env_int("DRAIN_SLEEP_SECONDS", 12)),
    }


@app.post("/jobs")
def create_job(payload: dict) -> dict:
    job_id = str(uuid.uuid4())
    payload_json = json.dumps(payload)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO jobs (id, status, payload) VALUES (%s, %s, %s::jsonb)",
                    (job_id, "pending", payload_json),
                )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))

    return {"id": job_id, "status": "pending"}


@app.get("/jobs")
def list_jobs(limit: int = 50) -> list[dict]:
    limit = max(1, min(limit, 200))

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status, payload, created_at, updated_at FROM jobs ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()

    jobs: list[dict] = []
    for job_id, status, payload, created_at, updated_at in rows:
        jobs.append(
            {
                "id": str(job_id),
                "status": status,
                "payload": payload,
                "created_at": created_at.isoformat(),
                "updated_at": updated_at.isoformat(),
            }
        )

    return jobs


@app.get("/")
def root() -> dict:
    return {
        "service": "gitops-demo-api",
        "version": os.getenv("APP_VERSION", "v1"),
        "draining": _is_draining(),
        "uptime_seconds": round(_uptime_seconds(), 2),
        "env": {
            "DB_HOST": os.getenv("DB_HOST", ""),
            "DB_NAME": os.getenv("DB_NAME", ""),
            "POD_NAME": os.getenv("HOSTNAME", ""),
        },
    }
