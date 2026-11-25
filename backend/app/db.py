import json
import sqlite3
from .config import DB_PATH


def run(sql, args=(), fetch=False):
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        cur = c.execute(sql, args)
        rows = [dict(r) for r in cur.fetchall()] if fetch else None
        c.commit()
        return rows
    finally:
        c.close()


def _add_cols(table, cols):
    have = {r["name"] for r in run(f"PRAGMA table_info({table})", fetch=True)}
    for name, ddl in cols.items():
        if name not in have:
            run(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init():
    for ddl in (
        "CREATE TABLE IF NOT EXISTS jobs(thread_id TEXT PRIMARY KEY, title TEXT, query TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY, thread_id TEXT, name TEXT, email TEXT, source TEXT, resume_path TEXT, text TEXT)",
        "CREATE TABLE IF NOT EXISTS email_logs(id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id TEXT, to_email TEXT, type TEXT, subject TEXT, status TEXT, sent_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id TEXT, actor TEXT, action TEXT, payload TEXT, ts TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, email TEXT UNIQUE, name TEXT, role TEXT, password_hash TEXT, phone TEXT DEFAULT '', skills TEXT DEFAULT '', experience_years INTEGER DEFAULT 0, location TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS applications(id TEXT PRIMARY KEY, thread_id TEXT, user_id TEXT, name TEXT, email TEXT, source TEXT, status TEXT, resume_path TEXT, resume_name TEXT, file_hash TEXT, score REAL, offer_path TEXT, submitted_at TEXT, UNIQUE(thread_id, user_id))",
        "CREATE TABLE IF NOT EXISTS app_events(id INTEGER PRIMARY KEY AUTOINCREMENT, app_id TEXT, status TEXT, note TEXT, ts TEXT)",
        "CREATE TABLE IF NOT EXISTS job_channels(thread_id TEXT, platform TEXT, status TEXT, url TEXT, updated_at TEXT, PRIMARY KEY(thread_id, platform))",
    ):
        run(ddl)
    _add_cols("jobs", {"location": "TEXT DEFAULT ''", "work_mode": "TEXT DEFAULT ''", "exp_min": "INTEGER DEFAULT 0",
                       "exp_max": "INTEGER DEFAULT 40", "skills": "TEXT DEFAULT ''", "jd": "TEXT DEFAULT ''",
                       "status": "TEXT DEFAULT 'draft'", "published_at": "TEXT", "deadline_at": "TEXT"})


def audit(thread_id, actor, action, payload=None):
    run("INSERT INTO audit_log(thread_id,actor,action,payload,ts) VALUES(?,?,?,?,strftime('%Y-%m-%dT%H:%M:%S','now'))",
        (thread_id, actor, action, json.dumps(payload or {}, default=str)))
