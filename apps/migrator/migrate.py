from __future__ import annotations

import os
import pathlib
import sys
import time

import psycopg


def _connect() -> psycopg.Connection:
    host = os.getenv("DB_HOST", "postgres")
    port = int(os.getenv("DB_PORT", "5432"))
    name = os.getenv("DB_NAME", "app")
    user = os.getenv("DB_USER", "app")
    password = os.getenv("DB_PASSWORD", "")

    return psycopg.connect(
        host=host,
        port=port,
        dbname=name,
        user=user,
        password=password,
        connect_timeout=2,
        autocommit=True,
    )


def _wait_for_db(max_seconds: int = 60) -> None:
    deadline = time.time() + max_seconds
    while True:
        try:
            with _connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return
        except Exception as e:  # noqa: BLE001
            if time.time() >= deadline:
                raise RuntimeError(f"DB not ready after {max_seconds}s: {e}")
            print(f"waiting for db: {e}")
            time.sleep(2)


def _ensure_migrations_table(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version TEXT PRIMARY KEY,
              applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )


def _already_applied(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}


def _split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_double_quote = False

    for ch in sql:
        if ch == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif ch == '"' and not in_single_quote:
            in_double_quote = not in_double_quote

        if ch == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            continue

        current.append(ch)

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)

    return statements


def _apply_file(conn: psycopg.Connection, version: str, sql_path: pathlib.Path) -> None:
    sql = sql_path.read_text(encoding="utf-8")
    statements = _split_sql_statements(sql)
    with conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
        cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))


def main() -> None:
    migrations_dir = pathlib.Path(__file__).parent / "migrations"
    if not migrations_dir.exists():
        raise RuntimeError(f"missing migrations dir: {migrations_dir}")

    _wait_for_db()

    with _connect() as conn:
        _ensure_migrations_table(conn)
        applied = _already_applied(conn)

        migration_files = sorted(migrations_dir.glob("*.sql"))
        if not migration_files:
            print("no migrations found")
            return

        for path in migration_files:
            version = path.name
            if version in applied:
                print(f"skip {version} (already applied)")
                continue

            print(f"apply {version}")
            _apply_file(conn, version, path)

    print("migrations complete")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        print(f"migrations failed: {e}")
        sys.exit(1)
