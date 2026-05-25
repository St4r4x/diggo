# dashboard/db.py
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

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

_SELECT = """
SELECT id, company, role, offer_url, detection_date, score_grade, score_value,
       status, send_date, contacts, notes, cv_path, cover_letter_path, follow_up_date
FROM applications
"""


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


class DB:
    def __init__(self, conn: sqlite3.Connection) -> None:
        conn.row_factory = sqlite3.Row
        self.conn = conn

    def get_all(self, filters: dict) -> list[dict]:
        clauses: list[str] = []
        params: list[Any] = []
        if status := filters.get("status"):
            clauses.append("status = ?")
            params.append(status)
        if grade := filters.get("grade"):
            clauses.append("score_grade = ?")
            params.append(grade)
        if q := filters.get("q"):
            clauses.append("(LOWER(company) LIKE ? OR LOWER(role) LIKE ?)")
            like = f"%{q.lower()}%"
            params.extend([like, like])
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"{_SELECT} {where} ORDER BY detection_date DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]

    def get_by_id(self, id: int) -> dict | None:
        row = self.conn.execute(_SELECT + "WHERE id = ?", (id,)).fetchone()
        return _row_to_dict(row) if row else None

    def update(self, id: int, fields: dict) -> dict:
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
            "follow_up_date",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_by_id(id)
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        self.conn.execute(
            f"UPDATE applications SET {set_clause} WHERE id = ?",
            [*updates.values(), id],
        )
        self.conn.commit()
        return self.get_by_id(id)

    def delete(self, id: int) -> None:
        self.conn.execute("DELETE FROM applications WHERE id = ?", (id,))
        self.conn.commit()

    def update_status(self, id: int, status: str) -> dict:
        return self.update(id, {"status": status})

    def get_stats(self) -> dict:
        rows = self.get_all({})
        by_status = {s: 0 for s in VALID_STATUSES}
        sent = response = interviews = stale = 0
        today = date.today()
        for r in rows:
            s = r["status"]
            by_status[s] = by_status.get(s, 0) + 1
            if s != "À envoyer":
                sent += 1
            if s in _RESPONSE_STATUSES:
                response += 1
            if s in _INTERVIEW_STATUSES:
                interviews += 1
            if s == "Envoyée" and r.get("send_date"):
                try:
                    send_dt = date.fromisoformat(r["send_date"])
                    if (today - send_dt).days > _FOLLOW_UP_DAYS:
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


def open_db(path: Path) -> DB:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return DB(conn)
