"""Ma'lumotlar bazasi — kompaniya, xodimlar, rollar, taklif kodlari."""
import os
import random
import sqlite3
import string
import threading
from datetime import datetime

from config import TZ

# Render'da doimiy disk /var/data ga ulanadi; mahalliy sinovda — shu papkada.
DB_PATH = "/var/data/yordamchi.db" if os.path.isdir("/var/data") else "yordamchi.db"

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
db_lock = threading.Lock()

ROLES = {
    "owner": "Rahbar",
    "head": "Bo'lim boshlig'i",
    "employee": "Xodim",
}


def now_str():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    with db_lock:
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id         INTEGER PRIMARY KEY,
            name       TEXT,
            username   TEXT,
            photo      TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS companies(
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT,
            owner_id   INTEGER,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS members(
            company_id INTEGER,
            user_id    INTEGER,
            role       TEXT,
            department TEXT,
            joined_at  TEXT,
            PRIMARY KEY(company_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS invites(
            code       TEXT PRIMARY KEY,
            company_id INTEGER,
            role       TEXT,
            department TEXT,
            created_by INTEGER,
            created_at TEXT,
            used_by    INTEGER,
            used_at    TEXT
        );
        CREATE TABLE IF NOT EXISTS groups(
            chat_id    INTEGER PRIMARY KEY,
            company_id INTEGER,
            title      TEXT,
            linked_by  INTEGER,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tasks(
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id  INTEGER,
            chat_id     INTEGER,
            message_id  INTEGER,
            text        TEXT,
            assignee_id INTEGER,
            author_id   INTEGER,
            status      TEXT DEFAULT 'new',
            due         TEXT,
            created_at  TEXT,
            done_at     TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_company ON tasks(company_id, status);
        CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee_id, status);
        """)
        conn.commit()


def upsert_user(uid, name, username=None, photo=None):
    with db_lock:
        cursor.execute("""
            INSERT INTO users(id, name, username, photo, created_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                username=COALESCE(excluded.username, users.username),
                photo=COALESCE(excluded.photo, users.photo)
        """, (uid, name, username, photo, now_str()))
        conn.commit()


def membership(uid):
    """Odam qaysi kompaniyada va qaysi rolda — a'zo bo'lmasa None."""
    with db_lock:
        row = cursor.execute("""
            SELECT m.company_id, m.role, m.department, c.name AS company_name
            FROM members m JOIN companies c ON c.id = m.company_id
            WHERE m.user_id = ?
            ORDER BY m.joined_at LIMIT 1
        """, (uid,)).fetchone()
    return dict(row) if row else None


def create_company(name, owner_id):
    with db_lock:
        cursor.execute("INSERT INTO companies(name, owner_id, created_at) VALUES(?,?,?)",
                       (name, owner_id, now_str()))
        company_id = cursor.lastrowid
        cursor.execute("""INSERT OR REPLACE INTO members(company_id, user_id, role, department, joined_at)
                          VALUES(?,?,'owner',NULL,?)""", (company_id, owner_id, now_str()))
        conn.commit()
    return company_id


def _new_code():
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(6))


def create_invite(company_id, role, department, created_by):
    with db_lock:
        for _ in range(20):
            code = _new_code()
            exists = cursor.execute("SELECT 1 FROM invites WHERE code = ?", (code,)).fetchone()
            if exists:
                continue
            cursor.execute("""INSERT INTO invites(code, company_id, role, department, created_by, created_at)
                              VALUES(?,?,?,?,?,?)""",
                           (code, company_id, role, department, created_by, now_str()))
            conn.commit()
            return code
    return None


def use_invite(code, uid):
    """Taklif kodini ishlatadi. Kod bir martalik."""
    code = (code or "").strip().upper()
    with db_lock:
        inv = cursor.execute("SELECT * FROM invites WHERE code = ? AND used_by IS NULL",
                             (code,)).fetchone()
        if not inv:
            return False
        already = cursor.execute("SELECT 1 FROM members WHERE user_id = ?", (uid,)).fetchone()
        if already:
            return False
        cursor.execute("""INSERT INTO members(company_id, user_id, role, department, joined_at)
                          VALUES(?,?,?,?,?)""",
                       (inv["company_id"], uid, inv["role"], inv["department"], now_str()))
        cursor.execute("UPDATE invites SET used_by = ?, used_at = ? WHERE code = ?",
                       (uid, now_str(), code))
        conn.commit()
    return True


def team(company_id):
    with db_lock:
        rows = cursor.execute("""
            SELECT u.id, u.name, u.username, u.photo, m.role, m.department
            FROM members m JOIN users u ON u.id = m.user_id
            WHERE m.company_id = ?
            ORDER BY CASE m.role WHEN 'owner' THEN 0 WHEN 'head' THEN 1 ELSE 2 END, u.name
        """, (company_id,)).fetchall()
    return [dict(r) for r in rows]


def member_by_name(company_id, name):
    """AI aytgan ismni jamoadagi haqiqiy odamga bog'laydi."""
    name = (name or "").strip().lower()
    if not name:
        return None
    for p in team(company_id):
        if (p["name"] or "").strip().lower() == name:
            return p
    for p in team(company_id):
        if name in (p["name"] or "").lower() or (p["name"] or "").lower() in name:
            return p
    return None


def user_by_username(username):
    uname = (username or "").strip().lstrip("@").lower()
    if not uname:
        return None
    with db_lock:
        row = cursor.execute("SELECT * FROM users WHERE LOWER(username) = ?", (uname,)).fetchone()
    return dict(row) if row else None


# ----------------------------------------------------------
# Guruhlar
# ----------------------------------------------------------
def link_group(chat_id, company_id, title, linked_by):
    with db_lock:
        cursor.execute("""INSERT INTO groups(chat_id, company_id, title, linked_by, created_at)
                          VALUES(?,?,?,?,?)
                          ON CONFLICT(chat_id) DO UPDATE SET
                            company_id=excluded.company_id, title=excluded.title""",
                       (chat_id, company_id, title, linked_by, now_str()))
        conn.commit()


def group_company(chat_id):
    with db_lock:
        row = cursor.execute("SELECT company_id FROM groups WHERE chat_id = ?", (chat_id,)).fetchone()
    return row["company_id"] if row else None


# ----------------------------------------------------------
# Vazifalar
# ----------------------------------------------------------
def add_task(company_id, chat_id, message_id, text, assignee_id, author_id, due=None):
    with db_lock:
        cursor.execute("""INSERT INTO tasks(company_id, chat_id, message_id, text,
                                            assignee_id, author_id, status, due, created_at)
                          VALUES(?,?,?,?,?,?,'new',?,?)""",
                       (company_id, chat_id, message_id, text, assignee_id, author_id, due, now_str()))
        task_id = cursor.lastrowid
        conn.commit()
    return task_id


def task(task_id):
    with db_lock:
        row = cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def set_status(task_id, status):
    done_at = now_str() if status == "done" else None
    with db_lock:
        cursor.execute("UPDATE tasks SET status = ?, done_at = ? WHERE id = ?",
                       (status, done_at, task_id))
        conn.commit()


def tasks_for(company_id, assignee_id=None):
    """Vazifalar ro'yxati — mas'ul berilsa faqat o'shaniki."""
    sql = """
        SELECT t.*, u.name AS assignee_name, u.username AS assignee_username, u.photo AS assignee_photo,
               a.name AS author_name
        FROM tasks t
        LEFT JOIN users u ON u.id = t.assignee_id
        LEFT JOIN users a ON a.id = t.author_id
        WHERE t.company_id = ?
    """
    args = [company_id]
    if assignee_id:
        sql += " AND t.assignee_id = ?"
        args.append(assignee_id)
    sql += " ORDER BY CASE t.status WHEN 'new' THEN 0 WHEN 'doing' THEN 1 ELSE 2 END, t.due IS NULL, t.due, t.id DESC"
    with db_lock:
        rows = cursor.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def open_invites(company_id):
    with db_lock:
        rows = cursor.execute("""
            SELECT code, role, department FROM invites
            WHERE company_id = ? AND used_by IS NULL
            ORDER BY created_at DESC LIMIT 20
        """, (company_id,)).fetchall()
    return [dict(r) for r in rows]
