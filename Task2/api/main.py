import os
import time
import mysql.connector
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager

# ── Config from env (ConfigMap + Secret) ────────────────────────────────────
APP_TITLE       = os.getenv("APP_TITLE",        "MLOPS MENA Guestbook")
MYSQL_HOST      = os.getenv("MYSQL_HOST",       "mysql-svc")
MYSQL_PORT      = int(os.getenv("MYSQL_PORT",   "3306"))
MYSQL_USER      = os.getenv("MYSQL_USER",       "guestbook")
DB_PASSWORD     = os.getenv("DB_PASSWORD",      "")
MYSQL_DATABASE  = os.getenv("MYSQL_DATABASE",   "guestbook")

# ── DB helpers ───────────────────────────────────────────────────────────────
def get_connection():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=DB_PASSWORD,
        database=MYSQL_DATABASE,
    )

def wait_for_db(retries: int = 30, delay: int = 3):
    """Retry until MySQL is ready — it starts slower than FastAPI."""
    for i in range(retries):
        try:
            conn = get_connection()
            conn.close()
            print(f"[startup] DB ready after {i * delay}s")
            return
        except Exception as exc:
            print(f"[startup] waiting for DB ({i+1}/{retries}): {exc}")
            time.sleep(delay)
    raise RuntimeError("Could not connect to MySQL after retries")

def init_db():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            name       VARCHAR(255) NOT NULL,
            message    TEXT         NOT NULL,
            created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

# ── App lifecycle ────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    wait_for_db()
    init_db()
    yield

app = FastAPI(title=APP_TITLE, lifespan=lifespan)

# ── Models ───────────────────────────────────────────────────────────────────
class MessageIn(BaseModel):
    name:    str
    message: str

# ── Routes ───────────────────────────────────────────────────────────────────
@app.get("/api/info")
def info():
    return {"title": APP_TITLE, "status": "ok", "version": "task2"}

@app.get("/api/messages")
def get_messages():
    try:
        conn = get_connection()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT id, name, message, created_at FROM messages ORDER BY created_at DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        for row in rows:
            row["created_at"] = str(row["created_at"])
        return rows
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/api/messages", status_code=201)
def post_message(msg: MessageIn):
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO messages (name, message) VALUES (%s, %s)",
            (msg.name, msg.message),
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "created"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
