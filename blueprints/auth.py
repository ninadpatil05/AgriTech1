import sqlite3
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from flask import Blueprint, jsonify, request

import config

auth_bp = Blueprint("auth", __name__)


def init_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash BLOB NOT NULL,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def issue_token(email: str) -> str:
    payload = {
        "sub": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRES_HOURS),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    first_name = (data.get("first_name") or "").strip() or None
    last_name = (data.get("last_name") or "").strip() or None
    phone = (data.get("phone") or "").strip() or None

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    created = datetime.now(timezone.utc).isoformat()

    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.execute(
            """
            INSERT INTO users (email, password_hash, first_name, last_name, phone, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (email, pw_hash, first_name, last_name, phone, created),
        )
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with this email already exists."}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"message": "User created successfully", "status": "success"}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    conn = sqlite3.connect(config.DB_PATH)
    row = conn.execute(
        "SELECT password_hash FROM users WHERE email = ? COLLATE NOCASE",
        (email,),
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Invalid email or password."}), 401

    stored = row[0]
    if isinstance(stored, str):
        stored = stored.encode("utf-8")

    if not bcrypt.checkpw(password.encode("utf-8"), stored):
        return jsonify({"error": "Invalid email or password."}), 401

    token = issue_token(email)
    return jsonify(
        {
            "message": "Login successful",
            "status": "success",
            "token": token,
        }
    ), 200
