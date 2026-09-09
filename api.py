import hmac
import json
import hashlib
from datetime import date
from functools import wraps
from urllib.parse import parse_qsl

from flask import Flask, request, jsonify, g

import db
from config import BOT_TOKEN, BOT_USERNAME, DEV_MODE, PORT
from parse import human_due

app = Flask(__name__, static_folder="webapp", static_url_path="")
db.init_db()


def validate_init_data(init_data: str):
    """Telegram yuborgan ma'lumot haqiqiyligini tekshiradi."""
    if not init_data or not BOT_TOKEN:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        got_hash = pairs.pop("hash", None)
        if not got_hash:
            return None
        check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, got_hash):
            return None
        return json.loads(pairs.get("user", "{}"))
    except Exception:
        return None


def need_user(fn):
    """Har so'rovda foydalanuvchini tanib oladi va bazada yangilab qo'yadi."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = validate_init_data(request.headers.get("X-Init-Data", ""))
        if user is None and DEV_MODE:
            user = {"id": 1, "first_name": "Sinov", "last_name": "Foydalanuvchi"}
        if not user or not user.get("id"):
            return jsonify({"error": "auth"}), 401

        name = " ".join(x for x in [user.get("first_name"), user.get("last_name")] if x)
        g.uid = user["id"]
        g.user = {
            "id": user["id"],
            "name": name or "Foydalanuvchi",
            "username": user.get("username"),
            "photo": user.get("photo_url"),
        }
        db.upsert_user(g.uid, g.user["name"], g.user["username"], g.user["photo"])
        return fn(*args, **kwargs)
    return wrapper


def task_json(t, uid):
    late = t["status"] != "done" and t["due"] and t["due"] < date.today().isoformat()
    return {
        "id": t["id"],
        "text": t["text"],
        "status": t["status"],
        "due": t["due"],
        "due_h": human_due(t["due"]),
        "late": bool(late),
        "mine": t["assignee_id"] == uid,
        "assignee": {
            "id": t["assignee_id"],
            "name": t["assignee_name"],
            "photo": t["assignee_photo"],
        },
        "author": t["author_name"],
    }


def stats_of(tasks):
    return {
        "new": sum(1 for t in tasks if t["status"] == "new"),
        "doing": sum(1 for t in tasks if t["status"] == "doing"),
        "done": sum(1 for t in tasks if t["status"] == "done"),
        "late": sum(1 for t in tasks if t["late"]),
    }


def me_payload():
    m = db.membership(g.uid)
    data = dict(g.user)
    data["member"] = bool(m)
    if m:
        mine = [task_json(t, g.uid) for t in db.tasks_for(m["company_id"], g.uid)]
        data.update({
            "company": m["company_name"],
            "company_id": m["company_id"],
            "role": m["role"],
            "role_name": db.ROLES.get(m["role"], "Xodim"),
            "department": m["department"],
            "stats": stats_of(mine),
            "tasks": mine,
        })
    return data


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/me")
@need_user
def me():
    return jsonify(me_payload())


@app.post("/api/company")
@need_user
def new_company():
    if db.membership(g.uid):
        return jsonify({"error": "already"}), 400
    name = (request.json or {}).get("name", "").strip()
    if not 2 <= len(name) <= 60:
        return jsonify({"error": "name"}), 400
    db.create_company(name, g.uid)
    return jsonify(me_payload())


@app.post("/api/join")
@need_user
def join():
    code = (request.json or {}).get("code", "").strip().upper()
    if not db.use_invite(code, g.uid):
        return jsonify({"error": "code"}), 400
    return jsonify(me_payload())


@app.get("/api/tasks")
@need_user
def tasks():
    m = db.membership(g.uid)
    if not m:
        return jsonify({"error": "member"}), 403

    scope = request.args.get("scope", "mine")
    boss = m["role"] in ("owner", "head")
    assignee = None if (scope == "all" and boss) else g.uid

    rows = [task_json(t, g.uid) for t in db.tasks_for(m["company_id"], assignee)]
    return jsonify({"tasks": rows, "stats": stats_of(rows), "boss": boss})


@app.post("/api/task/<int:task_id>/status")
@need_user
def task_status(task_id):
    m = db.membership(g.uid)
    t = db.task(task_id)
    if not m or not t or t["company_id"] != m["company_id"]:
        return jsonify({"error": "topilmadi"}), 404

    # O'z vazifasini xodim o'zi yuritadi; rahbar hammasini yurita oladi.
    if t["assignee_id"] != g.uid and m["role"] not in ("owner", "head"):
        return jsonify({"error": "ruxsat"}), 403

    status = (request.json or {}).get("status")
    if status not in ("new", "doing", "done"):
        return jsonify({"error": "status"}), 400

    db.set_status(task_id, status)
    return jsonify({"ok": True})


@app.get("/api/team")
@need_user
def team():
    m = db.membership(g.uid)
    if not m:
        return jsonify({"error": "member"}), 403
    return jsonify({
        "team": db.team(m["company_id"]),
        "invites": db.open_invites(m["company_id"]) if m["role"] in ("owner", "head") else [],
        "can_invite": m["role"] in ("owner", "head"),
        "bot": BOT_USERNAME,
    })


@app.post("/api/invite")
@need_user
def invite():
    m = db.membership(g.uid)
    if not m or m["role"] not in ("owner", "head"):
        return jsonify({"error": "role"}), 403

    body = request.json or {}
    role = body.get("role", "employee")
    if role not in db.ROLES or role == "owner":
        return jsonify({"error": "role"}), 400
    department = (body.get("department") or "").strip() or None

    code = db.create_invite(m["company_id"], role, department, g.uid)
    return jsonify({
        "code": code,
        "link": f"https://t.me/{BOT_USERNAME}?start={code}",
        "role": role,
        "department": department,
    })


def run_server(port=None):
    port = port or PORT
    try:
        from waitress import serve
    except ImportError:
        app.run(host="0.0.0.0", port=port, threaded=True)
        return
    serve(app, host="0.0.0.0", port=port, threads=8)
