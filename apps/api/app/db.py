from __future__ import annotations

import os
from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    name: str
    user: str
    password: str


def load_db_config() -> DbConfig:
    host = os.getenv("DB_HOST", "postgres")
    port = int(os.getenv("DB_PORT", "5432"))
    name = os.getenv("DB_NAME", "app")
    user = os.getenv("DB_USER", "app")
    password = os.getenv("DB_PASSWORD", "")
    return DbConfig(host=host, port=port, name=name, user=user, password=password)


def get_conn() -> psycopg.Connection:
    cfg = load_db_config()
    return psycopg.connect(
        host=cfg.host,
        port=cfg.port,
        dbname=cfg.name,
        user=cfg.user,
        password=cfg.password,
        connect_timeout=2,
        autocommit=True,
    )
