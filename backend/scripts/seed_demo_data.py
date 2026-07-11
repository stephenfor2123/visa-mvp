#!/usr/bin/env python3
"""Seed demo data — fill the dev database with a fixed set of users / orders
/ materials / admin hints so a fresh checkout is interactive immediately.

Idempotent by default: re-running on a populated DB only creates rows that
don't yet exist (matched by phone+country, order_no, sha256+user).
Use --reset to drop the demo rows first, then re-insert.

Usage
-----
    cd backend
    .venv/bin/python scripts/seed_demo_data.py                  # default 3 demo users
    .venv/bin/python scripts/seed_demo_data.py --user-count 5  # 5 demo users
    .venv/bin/python scripts/seed_demo_data.py --reset          # drop demo, then re-seed
    .venv/bin/python scripts/seed_demo_data.py --apply-admin-password
        # write ADMIN_PASSWORD_SECRET=HtexAd@26 into backend/.env

Demo accounts (all created here)
--------------------------------
Regular users  (login: POST /api/v2/auth/login with phone + password):
    phone = +86-13800138000{1..N}      (N = --user-count, default 3)
    password = Htex@2026               (8 chars, DEMO ONLY — bypasses strength
                                       check by direct bcrypt hash, see Notes)
    phone_country = +86
    nickname = demo_user_{phone}
    role variants:
      #1 (default)         : brand-new registered user, no orders
      #2 (default)         : has 1 order in `created` (待提交)
      #3 (default)         : has 1 order in `submitted` (已提交) + 1 in
                              `approved` (已完成/已批准)

Admin (login: POST /api/v2/admin/login):
    username = admin
    password = HtexAd@26               (8 chars, set ADMIN_PASSWORD_SECRET=
                                       HtexAd@26 in backend/.env, or pass
                                       --apply-admin-password to do it for you)

Demo materials (2 rows)
-----------------------
    #1 passport  → user #1 (no order linked)
    #2 id_card   → user #2 (linked to the `created` order's material_ids)

Demo orders (3 rows)
--------------------
    #1 created     : user #2 → dest #1 (US) tourism, material_ids=[2]
    #2 submitted   : user #3 → dest #1 (US) tourism
    #3 approved    : user #3 → dest #1 (US) student

Notes
-----
- This script uses the stdlib `sqlite3` driver directly (NOT SQLAlchemy
  ORM). The project's main ORM chain uses `Mapped[str | None]` PEP-604
  annotations, which SQLAlchemy 2.0 cannot de-stringify on Python 3.9
  — see "Python 3.9 venv + SQLAlchemy 2.0 Mapped[str | None]" in
  deliverable.md Notes. By driving raw SQL we sidestep the ORM chain
  entirely and the script works on any Python ≥ 3.7 with sqlite3.

- Password `Htex@2026` (8 chars, meets `password_min_length=8` + letter+digit
  rule) is the **demo-only** password. We bypass any stricter product
  policy by calling `passlib.CryptContext` directly — never use these
  accounts in a real deployment. Production still enforces the rule via
  AuthService.register / reset-password paths.

- Admin password is `HtexAd@26` (8 chars), distinct from the user password
  so demo screenshots / operator handover don't accidentally leak the
  user credential when an admin also tests user-side flows.

- Admin login uses an env-based secret (ADMIN_PASSWORD_SECRET) per the
  v2 admin auth design (no Admin user row in the users table).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Make `app` importable for getting DATABASE_URL only — we avoid
# SQLAlchemy ORM chain by NOT importing any model / service that
# triggers `Mapped[...]` evaluation.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from app.core.config import get_settings  # noqa: E402  (after sys.path tweak)
except Exception:
    # Fallback: hardcode the dev default.
    get_settings = None  # type: ignore[assignment]


# --------------------------------------------------------------------------- #
# Constants — change here only. Idempotency keys come from these.            #
# --------------------------------------------------------------------------- #
DEMO_PHONE_BASE = "13800138000"   # 11 digits — +86 prefix appended at login
DEMO_PASSWORD = "Htex@2026"        # 8 chars, demo-only; see Notes above
DEMO_PHONE_COUNTRY = "+86"
DEMO_NICKNAME_PREFIX = "demo_user_"

# Admin (env-based, no user row login)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "HtexAd@26"       # 8 chars, paired with ADMIN_PASSWORD_SECRET

# Destination to use for all demo orders. Override via --destination if
# you need a different country (must be enabled in visa_destinations).
DEFAULT_DESTINATION_ID = 1


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _now_naive() -> str:
    """SQLite-friendly naive UTC datetime string (matches func.now())."""
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _hash_password(plain: str) -> str:
    """Direct bcrypt hash — independent of `app.core.security` so we don't
    trigger the ORM import chain (see Notes)."""
    from passlib.context import CryptContext

    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
    return ctx.hash(plain)


def _resolve_db_path() -> Path:
    """Pull DATABASE_URL from settings; convert sqlite+aiosqlite:///PATH
    into a real Path. Falls back to data/visa_mvp.db."""
    if get_settings is None:
        return BACKEND_DIR / "data" / "visa_mvp.db"
    try:
        url = get_settings().database_url
    except Exception:
        return BACKEND_DIR / "data" / "visa_mvp.db"
    # sqlite+aiosqlite:///{ABS_PATH}  OR  sqlite+aiosqlite:///{REL_PATH}
    prefix = "sqlite+aiosqlite:///"
    if url.startswith(prefix):
        tail = url[len(prefix):]
        p = Path(tail)
        if not p.is_absolute():
            p = BACKEND_DIR / p
        return p
    # Unknown URL — abort loudly so the user fixes it.
    raise RuntimeError(
        f"Unsupported DATABASE_URL for seed script: {url!r}. "
        f"This script only handles sqlite+aiosqlite URLs."
    )


def _connect(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(
            f"{db_path} not found. Run `alembic upgrade head` first."
        )
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Enforce FKs (sqlite is off by default).
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --------------------------------------------------------------------------- #
# Idempotent inserts — pure SQL, no ORM                                       #
# --------------------------------------------------------------------------- #
def _find_user(conn: sqlite3.Connection, phone: str, country: str) -> Optional[sqlite3.Row]:
    """Locate a demo user by the stable identifier they were seeded with.

    Older schemas used (phone, phone_country) as the natural key. After the
    W26 email/username migration (see TEST-ACCOUNTS.md) the schema no
    longer carries a `phone` column, so we look up by username
    (`demo_user_<phone>`) as the schema-agnostic stable handle.
    """
    cols = _table_columns(conn, "users")
    if "phone" in cols:
        return conn.execute(
            "SELECT * FROM users WHERE phone = ? AND phone_country = ?",
            (phone, country),
        ).fetchone()
    username = f"{DEMO_NICKNAME_PREFIX}{phone}"
    return conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()


def _find_order(conn: sqlite3.Connection, order_no: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM orders WHERE order_no = ?", (order_no,)
    ).fetchone()


def _find_material(
    conn: sqlite3.Connection, user_id: int, sha256: str
) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM materials "
        "WHERE user_id = ? AND sha256 = ? AND deleted_at IS NULL",
        (user_id, sha256),
    ).fetchone()


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return set of column names that actually exist on `table` in the
    current DB schema. Lets us be tolerant of partial alembic migrations
    (DB might be 3 versions behind the model)."""
    return {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }


def _new_uuid() -> str:
    import uuid as _uuid
    return str(_uuid.uuid4())


def _insert_user(
    conn: sqlite3.Connection,
    *,
    phone: str,
    phone_country: str,
    password_hash: str,
    nickname: str,
) -> int:
    cols = _table_columns(conn, "users")
    payload = {
        "password_hash": password_hash,
        "nickname": nickname,
    }
    # Legacy schema (pre-W26) keyed users by phone; new schema keys by
    # email/username. Both branches are populated when the column exists
    # so a single seed insert works against either migration level.
    if "phone" in cols:
        payload["phone"] = phone
        payload["phone_country"] = phone_country
    if "username" in cols:
        payload["username"] = f"{DEMO_NICKNAME_PREFIX}{phone}"
    if "email" in cols:
        payload["email"] = f"demo{phone}@htex.app"
    if "uuid" in cols:
        payload["uuid"] = _new_uuid()
    if "status" in cols:
        payload["status"] = "active"
    if "language_pref" in cols:
        payload["language_pref"] = "zh-CN"
    if "mfa_enabled" in cols:
        payload["mfa_enabled"] = 0

    col_names = list(payload.keys())
    placeholders = ",".join("?" for _ in col_names)
    col_sql = ",".join(col_names)
    cur = conn.execute(
        f"INSERT INTO users ({col_sql}) VALUES ({placeholders})",
        list(payload.values()),
    )
    return cur.lastrowid


def _insert_material(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    material_type: str,
    original_filename: str,
    mime_type: str,
    file_size: int,
    sha256: str,
    storage_key: str,
    ocr_status: str,
) -> int:
    cols = _table_columns(conn, "materials")
    payload: dict[str, Any] = {
        "user_id": user_id,
        "material_type": material_type,
        "original_filename": original_filename,
        "mime_type": mime_type,
        "file_size": file_size,
        "sha256": sha256,
        "storage_key": storage_key,
    }
    if "uuid" in cols:
        payload["uuid"] = _new_uuid()
    if "encryption_key_id" in cols:
        payload["encryption_key_id"] = "dev-kms-stub"
    if "ocr_status" in cols:
        payload["ocr_status"] = ocr_status
    if "archived" in cols:
        payload["archived"] = 0

    col_names = list(payload.keys())
    placeholders = ",".join("?" for _ in col_names)
    col_sql = ",".join(col_names)
    cur = conn.execute(
        f"INSERT INTO materials ({col_sql}) VALUES ({placeholders})",
        list(payload.values()),
    )
    return cur.lastrowid


def _insert_order(
    conn: sqlite3.Connection,
    *,
    order_no: str,
    user_id: int,
    destination_id: int,
    visa_type: str,
    status: str,
    total_amount: float,
    currency: str,
    applicant_data: Optional[str],
    material_ids: Optional[str],
    submitted_at: Optional[str],
    reviewed_at: Optional[str],
    closed_at: Optional[str],
) -> int:
    cols = _table_columns(conn, "orders")
    payload: dict[str, Any] = {
        "order_no": order_no,
        "user_id": user_id,
        "destination_id": destination_id,
        "visa_type": visa_type,
        "status": status,
        "total_amount": total_amount,
        "currency": currency,
        "applicant_data": applicant_data,
        "material_ids": material_ids,
        "submitted_at": submitted_at,
        "reviewed_at": reviewed_at,
        "closed_at": closed_at,
    }
    if "uuid" in cols:
        payload["uuid"] = _new_uuid()

    col_names = list(payload.keys())
    placeholders = ",".join("?" for _ in col_names)
    col_sql = ",".join(col_names)
    cur = conn.execute(
        f"INSERT INTO orders ({col_sql}) VALUES ({placeholders})",
        list(payload.values()),
    )
    return cur.lastrowid


def _insert_order_history(
    conn: sqlite3.Connection,
    *,
    order_id: int,
    from_status: Optional[str],
    to_status: str,
    source: str,
    note: str,
) -> None:
    conn.execute(
        "INSERT INTO order_status_history "
        "(order_id, from_status, to_status, source, note) "
        "VALUES (?, ?, ?, ?, ?)",
        (order_id, from_status, to_status, source, note),
    )


# --------------------------------------------------------------------------- #
# --reset: drop demo rows                                                     #
# --------------------------------------------------------------------------- #
DEMO_USER_PHONES = tuple(f"{DEMO_PHONE_BASE}{i}" for i in range(1, 100))
DEMO_ORDER_PREFIX = "DEMO-"


def _drop_demo_rows(conn: sqlite3.Connection) -> dict[str, int]:
    deleted: dict[str, int] = {"materials": 0, "orders": 0, "users": 0}

    # Resolve demo user ids via whatever natural key the current schema
    # exposes — `phone` on legacy schemas, `username` on the post-W26
    # email/username schema (no `phone` column).
    cols = _table_columns(conn, "users")
    if "phone" in cols:
        placeholders = ",".join("?" for _ in DEMO_USER_PHONES)
        cur = conn.execute(
            f"SELECT id FROM users WHERE phone IN ({placeholders})",
            DEMO_USER_PHONES,
        )
        demo_user_ids = [r[0] for r in cur.fetchall()]
    else:
        username_placeholders = ",".join(
            "?" for _ in DEMO_USER_PHONES
        )
        usernames = tuple(
            f"{DEMO_NICKNAME_PREFIX}{p}" for p in DEMO_USER_PHONES
        )
        cur = conn.execute(
            f"SELECT id FROM users WHERE username IN ({username_placeholders})",
            usernames,
        )
        demo_user_ids = [r[0] for r in cur.fetchall()]

    if not demo_user_ids:
        return deleted

    id_placeholders = ",".join("?" for _ in demo_user_ids)

    # Materials owned by any demo user whose sha starts with `demo-sha-`.
    cur = conn.execute(
        f"DELETE FROM materials "
        f"WHERE sha256 LIKE 'demo-sha-%' "
        f"AND user_id IN ({id_placeholders})",
        demo_user_ids,
    )
    deleted["materials"] = cur.rowcount

    # Orders whose order_no starts with DEMO-.
    cur = conn.execute(
        f"DELETE FROM orders WHERE order_no LIKE '{DEMO_ORDER_PREFIX}%'"
    )
    deleted["orders"] = cur.rowcount

    # Demo users themselves.
    cur = conn.execute(
        f"DELETE FROM users WHERE id IN ({id_placeholders})",
        demo_user_ids,
    )
    deleted["users"] = cur.rowcount

    return deleted


# --------------------------------------------------------------------------- #
# Core seed                                                                   #
# --------------------------------------------------------------------------- #
def _verify_destination(conn: sqlite3.Connection, destination_id: int) -> None:
    row = conn.execute(
        "SELECT id, country_code, enabled FROM visa_destinations WHERE id = ?",
        (destination_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError(
            f"destination_id={destination_id} not found in visa_destinations. "
            f"Run `alembic upgrade head` then create one via the admin API "
            f"or pass --destination <id>."
        )
    if not row["enabled"]:
        raise RuntimeError(
            f"destination_id={destination_id} (country={row['country_code']}) "
            f"is disabled. Enable it first or pick another."
        )


def _build_user_plan(count: int) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    for idx in range(1, count + 1):
        phone = f"{DEMO_PHONE_BASE}{idx}"
        role = {
            1: "new",
            2: "has_created_order",
            3: "has_submitted_and_approved",
        }.get(idx, "new")
        plans.append(
            {
                "phone": phone,
                "phone_country": DEMO_PHONE_COUNTRY,
                "nickname": f"{DEMO_NICKNAME_PREFIX}{phone}",
                "role": role,
                "index": idx,
            }
        )
    return plans


def seed(
    *,
    user_count: int,
    reset: bool,
    destination_id: int,
    dry_run: bool,
) -> dict[str, Any]:
    db_path = _resolve_db_path()
    conn = _connect(db_path)
    summary: dict[str, Any] = {
        "db_path": str(db_path),
        "users_created": 0,
        "users_skipped": 0,
        "orders_created": 0,
        "orders_skipped": 0,
        "materials_created": 0,
        "materials_skipped": 0,
        "reset": reset,
        "destination_id": destination_id,
    }

    try:
        if reset:
            deleted = _drop_demo_rows(conn)
            summary["reset_deleted"] = deleted
            print(f"[--reset] Dropped demo rows: {deleted}")

        _verify_destination(conn, destination_id)

        password_hash = _hash_password(DEMO_PASSWORD)

        # Pass 1 — users
        users_by_phone: dict[str, int] = {}
        for plan in _build_user_plan(user_count):
            existing = _find_user(
                conn, plan["phone"], plan["phone_country"]
            )
            if existing is not None:
                users_by_phone[plan["phone"]] = existing["id"]
                summary["users_skipped"] += 1
            else:
                uid = _insert_user(
                    conn,
                    phone=plan["phone"],
                    phone_country=plan["phone_country"],
                    password_hash=password_hash,
                    nickname=plan["nickname"],
                )
                users_by_phone[plan["phone"]] = uid
                summary["users_created"] += 1

        # Pass 2 — materials
        # Material #1: passport owned by user #1.
        user1_id = users_by_phone[f"{DEMO_PHONE_BASE}1"]
        passport_sha = "demo-sha-passport-001"
        if _find_material(conn, user1_id, passport_sha) is not None:
            summary["materials_skipped"] += 1
        else:
            _insert_material(
                conn,
                user_id=user1_id,
                material_type="passport",
                original_filename="demo_passport.png",
                mime_type="image/png",
                file_size=204800,
                sha256=passport_sha,
                storage_key=f"demo/{user1_id}/passport.png",
                ocr_status="pending",
            )
            summary["materials_created"] += 1

        # Material #2: id_card owned by user #2 (linked to order #1).
        user2_id = users_by_phone[f"{DEMO_PHONE_BASE}2"]
        idcard_sha = "demo-sha-id_card-002"
        mat2_row: Optional[sqlite3.Row] = _find_material(
            conn, user2_id, idcard_sha
        )
        if mat2_row is not None:
            summary["materials_skipped"] += 1
            mat2_id = mat2_row["id"]
        else:
            mat2_id = _insert_material(
                conn,
                user_id=user2_id,
                material_type="id_card",
                original_filename="demo_id_card.png",
                mime_type="image/png",
                file_size=153600,
                sha256=idcard_sha,
                storage_key=f"demo/{user2_id}/id_card.png",
                ocr_status="done",
            )
            summary["materials_created"] += 1

        # Pass 3 — orders (only when we have >= 3 users)
        if user_count >= 3:
            user3_id = users_by_phone[f"{DEMO_PHONE_BASE}3"]
            now = _now_naive()

            # Order #1: created — owned by user #2
            order_no_1 = f"{DEMO_ORDER_PREFIX}20260615-CREATED-001"
            if _find_order(conn, order_no_1) is not None:
                summary["orders_skipped"] += 1
            else:
                oid1 = _insert_order(
                    conn,
                    order_no=order_no_1,
                    user_id=user2_id,
                    destination_id=destination_id,
                    visa_type="tourism",
                    status="created",
                    total_amount=199.00,
                    currency="USD",
                    applicant_data=json.dumps(
                        {
                            "full_name": "Demo Applicant",
                            "nationality": "CN",
                            "passport_no": "E12345678",
                            "birth_date": "1990-01-01",
                        },
                        ensure_ascii=False,
                    ),
                    material_ids=json.dumps([mat2_id], ensure_ascii=False),
                    submitted_at=None,
                    reviewed_at=None,
                    closed_at=None,
                )
                _insert_order_history(
                    conn,
                    order_id=oid1,
                    from_status=None,
                    to_status="created",
                    source="system",
                    note="seed_demo_data: initial insert",
                )
                summary["orders_created"] += 1

            # Order #2: submitted — owned by user #3
            order_no_2 = f"{DEMO_ORDER_PREFIX}20260615-SUBMITTED-002"
            if _find_order(conn, order_no_2) is not None:
                summary["orders_skipped"] += 1
            else:
                oid2 = _insert_order(
                    conn,
                    order_no=order_no_2,
                    user_id=user3_id,
                    destination_id=destination_id,
                    visa_type="tourism",
                    status="submitted",
                    total_amount=199.00,
                    currency="USD",
                    applicant_data=json.dumps(
                        {
                            "full_name": "Demo Applicant 2",
                            "nationality": "CN",
                            "passport_no": "E87654321",
                            "birth_date": "1992-05-15",
                        },
                        ensure_ascii=False,
                    ),
                    material_ids=json.dumps([], ensure_ascii=False),
                    submitted_at=now,
                    reviewed_at=None,
                    closed_at=None,
                )
                _insert_order_history(
                    conn,
                    order_id=oid2,
                    from_status=None,
                    to_status="submitted",
                    source="system",
                    note="seed_demo_data: initial insert",
                )
                summary["orders_created"] += 1

            # Order #3: approved — owned by user #3
            order_no_3 = f"{DEMO_ORDER_PREFIX}20260615-APPROVED-003"
            if _find_order(conn, order_no_3) is not None:
                summary["orders_skipped"] += 1
            else:
                oid3 = _insert_order(
                    conn,
                    order_no=order_no_3,
                    user_id=user3_id,
                    destination_id=destination_id,
                    visa_type="student",
                    status="approved",
                    total_amount=399.00,
                    currency="USD",
                    applicant_data=json.dumps(
                        {
                            "full_name": "Demo Applicant 3",
                            "nationality": "CN",
                            "passport_no": "E11223344",
                            "birth_date": "1995-09-20",
                        },
                        ensure_ascii=False,
                    ),
                    material_ids=json.dumps([], ensure_ascii=False),
                    submitted_at=now,
                    reviewed_at=now,
                    closed_at=None,
                )
                _insert_order_history(
                    conn,
                    order_id=oid3,
                    from_status=None,
                    to_status="approved",
                    source="system",
                    note="seed_demo_data: initial insert",
                )
                summary["orders_created"] += 1

        if dry_run:
            conn.rollback()
            print("[--dry-run] Rolled back; no changes persisted.")
        else:
            conn.commit()

    finally:
        conn.close()

    return summary


# --------------------------------------------------------------------------- #
# --apply-admin-password                                                     #
# --------------------------------------------------------------------------- #
def apply_admin_password(env_path: Path, secret: str) -> None:
    """Write / replace `ADMIN_PASSWORD_SECRET=<secret>` in backend/.env.

    Preserves the rest of the file (preserves comments + other keys).
    Idempotent: re-running replaces the value, not duplicates the key.
    """
    if not env_path.exists():
        raise FileNotFoundError(f"{env_path} not found. Create the env file first.")

    text = env_path.read_text(encoding="utf-8")
    target_line = f"ADMIN_PASSWORD_SECRET={secret}"
    replaced = False
    new_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("ADMIN_PASSWORD_SECRET="):
            new_lines.append(target_line)
            replaced = True
        else:
            new_lines.append(line)

    if not replaced:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.append(
            f"# Auto-set by scripts/seed_demo_data.py --apply-admin-password "
            f"({datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')})"
        )
        new_lines.append(target_line)

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Seed demo users / orders / materials into the dev DB."
    )
    p.add_argument(
        "--user-count",
        type=int,
        default=3,
        help="Number of demo users to create (default: 3).",
    )
    p.add_argument(
        "--reset",
        action="store_true",
        help="Drop existing demo rows (matched by DEMO order_no prefix and "
             "demo phone pattern) before re-inserting.",
    )
    p.add_argument(
        "--destination",
        type=int,
        default=DEFAULT_DESTINATION_ID,
        help=f"visa_destinations.id to use for demo orders (default: "
             f"{DEFAULT_DESTINATION_ID}).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the plan but roll back before commit (no DB writes).",
    )
    p.add_argument(
        "--apply-admin-password",
        action="store_true",
        help=f"Write ADMIN_PASSWORD_SECRET={ADMIN_PASSWORD} into backend/.env "
             f"so the demo admin login (admin/{ADMIN_PASSWORD}) works.",
    )
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if args.user_count < 1:
        print("error: --user-count must be >= 1", file=sys.stderr)
        return 2
    if args.user_count > 99:
        print("error: --user-count capped at 99 (DEMO_USER_PHONES limit)",
              file=sys.stderr)
        return 2

    summary = seed(
        user_count=args.user_count,
        reset=args.reset,
        destination_id=args.destination,
        dry_run=args.dry_run,
    )

    if args.apply_admin_password:
        env_path = BACKEND_DIR / ".env"
        try:
            apply_admin_password(env_path, ADMIN_PASSWORD)
            print(
                f"[--apply-admin-password] Wrote ADMIN_PASSWORD_SECRET="
                f"{ADMIN_PASSWORD} to {env_path}"
            )
        except Exception as exc:
            print(
                f"[--apply-admin-password] FAILED to update {env_path}: {exc}",
                file=sys.stderr,
            )
            return 1

    print()
    print("=== seed summary ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print()
    print("Demo user accounts (phone / password):")
    for idx in range(1, args.user_count + 1):
        print(
            f"  +86-{DEMO_PHONE_BASE}{idx}  /  {DEMO_PASSWORD}  "
            f"(nickname: {DEMO_NICKNAME_PREFIX}{DEMO_PHONE_BASE}{idx})"
        )
    print()
    print("Admin login (POST /api/v2/admin/login):")
    print(f"  username: {ADMIN_USERNAME}")
    print(f"  password: {ADMIN_PASSWORD}")
    if not args.apply_admin_password:
        print(
            f"  (NOTE: set ADMIN_PASSWORD_SECRET={ADMIN_PASSWORD} in backend/.env, "
            "or re-run with --apply-admin-password)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
