import os
import sqlite3
import secrets
import hashlib
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Header, Query
from pydantic import BaseModel
from typing import Optional

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "prodsmart_cloud.db")

app = FastAPI(title="ProdSmart Cloud API")


def _utc_now():
    return datetime.now(timezone.utc)


def _iso(dt):
    if isinstance(dt, str):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_seen TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            join_code TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS team_members (
            team_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(team_id, user_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS team_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            is_completed INTEGER DEFAULT 0,
            completed_at TEXT,
            task_type TEXT,
            is_urgent INTEGER DEFAULT 0,
            is_important INTEGER DEFAULT 0,
            priority TEXT,
            created_date TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS team_pomodoro (
            team_id INTEGER PRIMARY KEY,
            phase TEXT,
            status TEXT,
            started_at TEXT,
            duration_min INTEGER,
            started_by INTEGER,
            updated_at TEXT,
            ended_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS team_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migrate existing installations
    for stmt in (
        "ALTER TABLE team_tasks ADD COLUMN task_type TEXT",
        "ALTER TABLE team_tasks ADD COLUMN is_urgent INTEGER DEFAULT 0",
        "ALTER TABLE team_tasks ADD COLUMN is_important INTEGER DEFAULT 0",
        "ALTER TABLE team_tasks ADD COLUMN priority TEXT",
        "ALTER TABLE team_tasks ADD COLUMN created_date TEXT",
    ):
        try:
            cur.execute(stmt)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


_init_db()


def _create_join_code(conn):
    cur = conn.cursor()
    while True:
        code = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8].upper()
        exists = cur.execute("SELECT 1 FROM teams WHERE join_code = ?", (code,)).fetchone()
        if not exists:
            return code


def _extract_token(auth_header):
    if not auth_header:
        return None
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return auth_header.strip()


def _require_user(authorization):
    token = _extract_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing authorization token.")
    conn = _get_db()
    row = conn.execute(
        "SELECT users.id, users.username FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token = ?",
        (token,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    conn.execute(
        "UPDATE sessions SET last_seen = ? WHERE token = ?",
        (_iso(_utc_now()), token)
    )
    conn.commit()
    conn.close()
    return {"id": row["id"], "username": row["username"], "token": token}


def _deadline_is_urgent(due_date_str):
    if not due_date_str:
        return 0
    try:
        due = datetime.fromisoformat(due_date_str)
    except Exception:
        try:
            due = datetime.strptime(due_date_str, "%Y-%m-%d")
        except Exception:
            return 0
    today = _utc_now().date()
    days_to = (due.date() - today).days
    return 1 if days_to <= 2 else 0


def _priority_from_flags(is_urgent, is_important):
    try:
        urg = int(is_urgent or 0)
        imp = int(is_important or 0)
    except Exception:
        urg = 0
        imp = 0
    if urg == 1 and imp == 1:
        return "high"
    if urg == 0 and imp == 1:
        return "medium"
    if urg == 1 and imp == 0:
        return "low"
    return "too low"


def _ensure_member(conn, team_id, user_id):
    row = conn.execute(
        "SELECT role FROM team_members WHERE team_id = ? AND user_id = ?",
        (team_id, user_id)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=403, detail="Not a member of this team.")
    return row["role"]


class AuthPayload(BaseModel):
    username: str
    password: str


class TeamCreatePayload(BaseModel):
    name: str


class TeamJoinPayload(BaseModel):
    code: str


class TeamTaskPayload(BaseModel):
    title: str
    description: Optional[str] = ""
    due_date: Optional[str] = None
    task_type: Optional[str] = None
    is_important: Optional[bool] = None


class TeamTaskUpdatePayload(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    is_completed: Optional[bool] = None
    task_type: Optional[str] = None
    is_important: Optional[bool] = None


class PomodoroStartPayload(BaseModel):
    phase: str
    duration_min: int


class TeamMessagePayload(BaseModel):
    message: str


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/auth/register")
def register(payload: AuthPayload):
    username = payload.username.strip()
    if not username or not payload.password:
        raise HTTPException(status_code=400, detail="Username and password are required.")
    conn = _get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, _hash_password(payload.password))
        )
        conn.commit()
        user_id = cur.lastrowid
        return {"user_id": user_id, "username": username}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username already exists.")
    finally:
        conn.close()


@app.post("/auth/login")
def login(payload: AuthPayload):
    conn = _get_db()
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE username = ?",
        (payload.username.strip(),)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    if row["password_hash"] != _hash_password(payload.password):
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token, user_id, last_seen) VALUES (?, ?, ?)",
        (token, row["id"], _iso(_utc_now()))
    )
    conn.commit()
    conn.close()
    return {"token": token, "user_id": row["id"], "username": payload.username.strip()}


@app.get("/me")
def me(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    user = _require_user(authorization)
    return {"user_id": user["id"], "username": user["username"]}


@app.get("/teams")
def list_teams(authorization: Optional[str] = Header(default=None, alias="Authorization")):
    user = _require_user(authorization)
    conn = _get_db()
    rows = conn.execute(
        """SELECT teams.id, teams.name, team_members.role
           FROM team_members
           JOIN teams ON teams.id = team_members.team_id
           WHERE team_members.user_id = ?
           ORDER BY teams.name""",
        (user["id"],)
    ).fetchall()
    conn.close()
    return {"teams": [dict(row) for row in rows]}


@app.post("/teams")
def create_team(payload: TeamCreatePayload, authorization: Optional[str] = Header(default=None, alias="Authorization")):
    user = _require_user(authorization)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Team name is required.")
    conn = _get_db()
    join_code = _create_join_code(conn)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO teams (name, owner_id, join_code) VALUES (?, ?, ?)",
        (name, user["id"], join_code)
    )
    team_id = cur.lastrowid
    cur.execute(
        "INSERT INTO team_members (team_id, user_id, role) VALUES (?, ?, ?)",
        (team_id, user["id"], "owner")
    )
    conn.commit()
    conn.close()
    return {"id": team_id, "name": name, "join_code": join_code, "role": "owner"}


@app.post("/teams/join")
def join_team(payload: TeamJoinPayload, authorization: Optional[str] = Header(default=None, alias="Authorization")):
    user = _require_user(authorization)
    code = payload.code.strip().upper()
    conn = _get_db()
    team = conn.execute(
        "SELECT id, name FROM teams WHERE join_code = ?",
        (code,)
    ).fetchone()
    if not team:
        conn.close()
        raise HTTPException(status_code=404, detail="Invalid team code.")
    try:
        conn.execute(
            "INSERT INTO team_members (team_id, user_id, role) VALUES (?, ?, ?)",
            (team["id"], user["id"], "member")
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()
    return {"id": team["id"], "name": team["name"], "role": "member"}


@app.get("/teams/{team_id}")
def get_team(team_id: int, authorization: Optional[str] = Header(default=None, alias="Authorization")):
    user = _require_user(authorization)
    conn = _get_db()
    role = _ensure_member(conn, team_id, user["id"])
    team = conn.execute("SELECT id, name, join_code, owner_id FROM teams WHERE id = ?", (team_id,)).fetchone()
    conn.close()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found.")
    data = {"id": team["id"], "name": team["name"], "role": role}
    if role == "owner" or team["owner_id"] == user["id"]:
        data["join_code"] = team["join_code"]
    return data


@app.get("/teams/{team_id}/members")
def list_team_members(team_id: int, authorization: Optional[str] = Header(default=None, alias="Authorization")):
    user = _require_user(authorization)
    conn = _get_db()
    _ensure_member(conn, team_id, user["id"])
    rows = conn.execute(
        """SELECT users.id as user_id, users.username, team_members.role
           FROM team_members
           JOIN users ON users.id = team_members.user_id
           WHERE team_members.team_id = ?
           ORDER BY users.username""",
        (team_id,)
    ).fetchall()
    conn.close()
    return {"members": [dict(row) for row in rows]}


@app.get("/teams/{team_id}/tasks")
def list_team_tasks(team_id: int, authorization: Optional[str] = Header(default=None, alias="Authorization")):
    user = _require_user(authorization)
    conn = _get_db()
    _ensure_member(conn, team_id, user["id"])
    rows = conn.execute(
        """SELECT id, title, description, due_date, created_at, created_date, is_completed, completed_at,
                  created_by, task_type, is_urgent, is_important, priority
           FROM team_tasks WHERE team_id = ? ORDER BY is_completed, created_at DESC""",
        (team_id,)
    ).fetchall()
    conn.close()
    return {"tasks": [dict(row) for row in rows]}


@app.post("/teams/{team_id}/tasks")
def create_team_task(team_id: int, payload: TeamTaskPayload, authorization: Optional[str] = Header(default=None, alias="Authorization")):
    user = _require_user(authorization)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required.")
    conn = _get_db()
    _ensure_member(conn, team_id, user["id"])
    is_important = 1 if payload.is_important else 0
    is_urgent = _deadline_is_urgent(payload.due_date)
    priority = _priority_from_flags(is_urgent, is_important)
    created_date = _utc_now().date().isoformat()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO team_tasks (team_id, title, description, due_date, created_by,
                                   task_type, is_urgent, is_important, priority, created_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (team_id, title, payload.description or "", payload.due_date, user["id"],
         payload.task_type, is_urgent, is_important, priority, created_date)
    )
    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    return {
        "id": task_id,
        "title": title,
        "due_date": payload.due_date,
        "task_type": payload.task_type,
        "is_urgent": is_urgent,
        "is_important": is_important,
        "priority": priority,
        "created_date": created_date,
    }


@app.patch("/teams/{team_id}/tasks/{task_id}")
def update_team_task(team_id: int, task_id: int, payload: TeamTaskUpdatePayload, authorization: Optional[str] = Header(default=None, alias="Authorization")):
    user = _require_user(authorization)
    conn = _get_db()
    _ensure_member(conn, team_id, user["id"])
    existing = conn.execute(
        "SELECT due_date, is_important FROM team_tasks WHERE team_id = ? AND id = ?",
        (team_id, task_id)
    ).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found.")
    fields = []
    values = []
    if payload.title is not None:
        fields.append("title = ?")
        values.append(payload.title.strip())
    if payload.description is not None:
        fields.append("description = ?")
        values.append(payload.description)
    if payload.due_date is not None:
        fields.append("due_date = ?")
        values.append(payload.due_date)
    if payload.task_type is not None:
        fields.append("task_type = ?")
        values.append(payload.task_type)
    if payload.is_important is not None:
        fields.append("is_important = ?")
        values.append(1 if payload.is_important else 0)
    if payload.is_completed is not None:
        fields.append("is_completed = ?")
        values.append(1 if payload.is_completed else 0)
        fields.append("completed_at = ?")
        values.append(_iso(_utc_now()) if payload.is_completed else None)
    # Recompute urgency/priority when due date or importance changes
    if payload.due_date is not None or payload.is_important is not None:
        new_due = payload.due_date if payload.due_date is not None else existing["due_date"]
        new_imp = payload.is_important if payload.is_important is not None else bool(existing["is_important"])
        new_urg = _deadline_is_urgent(new_due)
        new_prio = _priority_from_flags(new_urg, 1 if new_imp else 0)
        fields.append("is_urgent = ?")
        values.append(new_urg)
        fields.append("priority = ?")
        values.append(new_prio)
    if fields:
        values.extend([team_id, task_id])
        conn.execute(
            f"UPDATE team_tasks SET {', '.join(fields)} WHERE team_id = ? AND id = ?",
            tuple(values)
        )
        conn.commit()
    conn.close()
    return {"ok": True}


@app.delete("/teams/{team_id}/tasks/{task_id}")
def delete_team_task(team_id: int, task_id: int, authorization: Optional[str] = Header(default=None, alias="Authorization")):
    user = _require_user(authorization)
    conn = _get_db()
    _ensure_member(conn, team_id, user["id"])
    conn.execute("DELETE FROM team_tasks WHERE team_id = ? AND id = ?", (team_id, task_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/teams/{team_id}/pomodoro")
def get_pomodoro_state(team_id: int, authorization: Optional[str] = Header(default=None, alias="Authorization")):
    user = _require_user(authorization)
    conn = _get_db()
    _ensure_member(conn, team_id, user["id"])
    row = conn.execute(
        "SELECT team_id, phase, status, started_at, duration_min, started_by, ended_at FROM team_pomodoro WHERE team_id = ?",
        (team_id,)
    ).fetchone()
    now = _utc_now()
    if not row:
        conn.close()
        return {"status": "idle", "server_time": _iso(now)}
    status = row["status"] or "idle"
    remaining_seconds = None
    if status == "running" and row["started_at"] and row["duration_min"]:
        try:
            started_at = datetime.fromisoformat(row["started_at"])
        except Exception:
            started_at = now
        elapsed = (now - started_at).total_seconds()
        remaining_seconds = int(max(0, row["duration_min"] * 60 - elapsed))
        if remaining_seconds <= 0:
            status = "completed"
            conn.execute(
                "UPDATE team_pomodoro SET status = ?, ended_at = ?, updated_at = ? WHERE team_id = ?",
                ("completed", _iso(now), _iso(now), team_id)
            )
            conn.commit()
    started_by_name = None
    if row["started_by"]:
        user_row = conn.execute("SELECT username FROM users WHERE id = ?", (row["started_by"],)).fetchone()
        if user_row:
            started_by_name = user_row["username"]
    conn.close()
    return {
        "status": status,
        "phase": row["phase"],
        "started_at": row["started_at"],
        "duration_min": row["duration_min"],
        "started_by": started_by_name,
        "remaining_seconds": remaining_seconds,
        "server_time": _iso(now),
    }


@app.get("/teams/{team_id}/messages")
def list_team_messages(
    team_id: int,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    limit: int = Query(default=50, ge=1, le=200),
    before_id: Optional[int] = Query(default=None, ge=1),
):
    user = _require_user(authorization)
    conn = _get_db()
    _ensure_member(conn, team_id, user["id"])
    params = [team_id]
    where = "WHERE team_messages.team_id = ?"
    if before_id is not None:
        where += " AND team_messages.id < ?"
        params.append(before_id)
    params.append(limit)
    rows = conn.execute(
        f"""SELECT team_messages.id, team_messages.message, team_messages.created_at,
                   users.id as user_id, users.username
            FROM team_messages
            JOIN users ON users.id = team_messages.user_id
            {where}
            ORDER BY team_messages.id DESC
            LIMIT ?""",
        tuple(params)
    ).fetchall()
    conn.close()
    messages = [dict(row) for row in rows]
    messages.reverse()
    return {"messages": messages}


@app.post("/teams/{team_id}/messages")
def send_team_message(team_id: int, payload: TeamMessagePayload, authorization: Optional[str] = Header(default=None, alias="Authorization")):
    user = _require_user(authorization)
    msg = (payload.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    if len(msg) > 1000:
        raise HTTPException(status_code=400, detail="Message is too long.")
    conn = _get_db()
    _ensure_member(conn, team_id, user["id"])
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO team_messages (team_id, user_id, message) VALUES (?, ?, ?)",
        (team_id, user["id"], msg)
    )
    msg_id = cur.lastrowid
    row = conn.execute(
        """SELECT team_messages.id, team_messages.message, team_messages.created_at,
                  users.id as user_id, users.username
           FROM team_messages
           JOIN users ON users.id = team_messages.user_id
           WHERE team_messages.id = ?""",
        (msg_id,)
    ).fetchone()
    conn.commit()
    conn.close()
    return {"message": dict(row) if row else None}


@app.post("/teams/{team_id}/pomodoro/start")
def start_pomodoro(team_id: int, payload: PomodoroStartPayload, authorization: Optional[str] = Header(default=None, alias="Authorization")):
    user = _require_user(authorization)
    phase = payload.phase.strip().lower()
    if phase not in ("focus", "break"):
        raise HTTPException(status_code=400, detail="Phase must be 'focus' or 'break'.")
    if payload.duration_min < 1 or payload.duration_min > 240:
        raise HTTPException(status_code=400, detail="Duration must be between 1 and 240 minutes.")
    conn = _get_db()
    _ensure_member(conn, team_id, user["id"])
    now = _utc_now()
    conn.execute(
        """INSERT INTO team_pomodoro (team_id, phase, status, started_at, duration_min, started_by, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(team_id) DO UPDATE SET
             phase = excluded.phase,
             status = excluded.status,
             started_at = excluded.started_at,
             duration_min = excluded.duration_min,
             started_by = excluded.started_by,
             updated_at = excluded.updated_at,
             ended_at = NULL""",
        (team_id, phase, "running", _iso(now), payload.duration_min, user["id"], _iso(now))
    )
    conn.commit()
    conn.close()
    return {"status": "running", "phase": phase, "started_at": _iso(now), "duration_min": payload.duration_min}


@app.post("/teams/{team_id}/pomodoro/stop")
def stop_pomodoro(team_id: int, authorization: Optional[str] = Header(default=None, alias="Authorization")):
    user = _require_user(authorization)
    conn = _get_db()
    _ensure_member(conn, team_id, user["id"])
    now = _utc_now()
    conn.execute(
        "UPDATE team_pomodoro SET status = ?, ended_at = ?, updated_at = ? WHERE team_id = ?",
        ("stopped", _iso(now), _iso(now), team_id)
    )
    conn.commit()
    conn.close()
    return {"status": "stopped"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
