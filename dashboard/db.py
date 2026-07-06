from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

import psycopg2
import psycopg2.extensions

_SAL_RANGE_RE = re.compile(r"(\d+)\s*[-–]\s*\d+\s*k", re.IGNORECASE)
_SAL_FROM_RE = re.compile(r"partir\s+de\s+(\d+)\s*k", re.IGNORECASE)


def _parse_salary_min(text: str) -> int | None:
    m = _SAL_RANGE_RE.search(text)
    if m:
        return int(m.group(1))
    m = _SAL_FROM_RE.search(text)
    if m:
        return int(m.group(1))
    return None


VALID_STATUSES = [
    "À envoyer",
    "Envoyée",
    "Relance",
    "Entretien RH",
    "Entretien tech",
    "Offre",
    "Acceptée",
    "Refusée",
    "Abandonnée",
]

_RESPONSE_STATUSES = {"Entretien RH", "Entretien tech", "Offre", "Acceptée", "Refusée"}
_INTERVIEW_STATUSES = {"Entretien RH", "Entretien tech", "Offre", "Acceptée"}
_FOLLOW_UP_DAYS = 7

_COLS = (
    "id",
    "company",
    "role",
    "offer_url",
    "detection_date",
    "score_grade",
    "score_value",
    "status",
    "send_date",
    "contacts",
    "notes",
    "cv_path",
    "cover_letter_path",
    "prep_sheet_path",
    "follow_up_date",
    "description",
    "portal",
)
_SELECT = f"SELECT {', '.join(_COLS)} FROM applications"


def _row_to_dict(row: tuple) -> dict[str, Any]:
    return dict(zip(_COLS, row))


class DB:
    def __init__(self, conn: psycopg2.extensions.connection) -> None:
        self.conn = conn

    def get_all(self, filters: dict, user_id: str) -> list[dict]:
        clauses: list[str] = ["user_id = %s"]
        params: list[Any] = [user_id]
        if status := filters.get("status"):
            clauses.append("status = %s")
            params.append(status)
        if grade := filters.get("grade"):
            clauses.append("score_grade = %s")
            params.append(grade)
        if q := filters.get("q"):
            clauses.append("(LOWER(company) LIKE %s OR LOWER(role) LIKE %s)")
            like = f"%{q.lower()}%"
            params.extend([like, like])
        where = "WHERE " + " AND ".join(clauses)
        sql = f"{_SELECT} {where} ORDER BY detection_date DESC"
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            rows = [_row_to_dict(r) for r in cur.fetchall()]
        if sal_min := filters.get("sal_min"):
            try:
                threshold = int(sal_min)
            except ValueError:
                threshold = None
            if threshold is not None:

                def _above(r: dict) -> bool:
                    raw = r.get("description", "")
                    try:
                        d = json.loads(raw)
                        sal_text = d.get("salaire", "")
                    except (json.JSONDecodeError, ValueError):
                        sal_text = ""
                    v = _parse_salary_min(sal_text)
                    return v is not None and v >= threshold

                rows = [r for r in rows if _above(r)]
        return rows

    def get_by_id(self, id: int, user_id: str) -> dict | None:
        with self.conn.cursor() as cur:
            cur.execute(f"{_SELECT} WHERE id = %s AND user_id = %s", (id, user_id))
            row = cur.fetchone()
        return _row_to_dict(row) if row else None

    def update(self, id: int, fields: dict, user_id: str) -> dict:
        allowed = {
            "company",
            "role",
            "offer_url",
            "detection_date",
            "score_grade",
            "score_value",
            "status",
            "send_date",
            "contacts",
            "notes",
            "cv_path",
            "cover_letter_path",
            "prep_sheet_path",
            "follow_up_date",
            "description",
            "portal",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_by_id(id, user_id)
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        with self.conn.cursor() as cur:
            cur.execute(
                f"UPDATE applications SET {set_clause} WHERE id = %s AND user_id = %s",
                [*updates.values(), id, user_id],
            )
        self.conn.commit()
        return self.get_by_id(id, user_id)

    def delete(self, id: int, user_id: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM applications WHERE id = %s AND user_id = %s",
                (id, user_id),
            )
        self.conn.commit()

    def update_status(self, id: int, status: str, user_id: str) -> dict:
        return self.update(id, {"status": status}, user_id)

    def get_stats(self, user_id: str) -> dict:
        rows = self.get_all({}, user_id=user_id)
        by_status = {s: 0 for s in VALID_STATUSES}
        sent = response = interviews = stale = 0
        today = date.today()
        for r in rows:
            s = r["status"]
            by_status[s] += 1
            if s != "À envoyer":
                sent += 1
            if s in _RESPONSE_STATUSES:
                response += 1
            if s in _INTERVIEW_STATUSES:
                interviews += 1
            if s == "Envoyée" and r.get("send_date"):
                try:
                    send_dt = date.fromisoformat(r["send_date"])
                    if (today - send_dt).days >= _FOLLOW_UP_DAYS:
                        stale += 1
                except ValueError:
                    pass
        response_rate = (response / sent * 100) if sent else 0.0
        return {
            "total": len(rows),
            "response_rate": round(response_rate, 1),
            "interview_count": interviews,
            "stale_count": stale,
            "by_status": by_status,
        }

    def get_followups(self, user_id: str) -> list[dict]:
        cutoff = (date.today() - timedelta(days=_FOLLOW_UP_DAYS)).isoformat()
        with self.conn.cursor() as cur:
            cur.execute(
                f"{_SELECT} WHERE user_id = %s AND status IN ('Envoyée', 'Entretien RH')"
                " AND send_date IS NOT NULL AND send_date <= %s",
                (user_id, cutoff),
            )
            rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]

    def close(self) -> None:
        self.conn.close()


def open_db(url: str) -> DB:
    conn = psycopg2.connect(url)
    conn.autocommit = False
    return DB(conn)
