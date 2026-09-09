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


def open_invites(company_id):
    with db_lock:
        rows = cursor.execute("""
            SELECT code, role, department FROM invites
            WHERE company_id = ? AND used_by IS NULL
            ORDER BY created_at DESC LIMIT 20
        """, (company_id,)).fetchall()
    return [dict(r) for r in rows]
