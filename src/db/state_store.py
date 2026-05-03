"""SQLite-backed persistence for patrol issue state."""

from __future__ import annotations

from datetime import datetime, timezone
import sqlite3

from src.types import StateRecord, StateRow


class StateStore:
    """Persist fingerprint-to-issue mappings between patrol runs.

    The store keeps the patrol workflow's durable SQLite state in one place so
    repeated fingerprints can update existing issues, preserve patrol counts,
    and support stale-issue cleanup across separate process executions.

    Attributes:
        db_path: Filesystem path to the SQLite database file.
        _conn: Open SQLite connection used for all state queries and updates.
    """

    def __init__(self, db_path: str):
        """Open the SQLite database and ensure the schema exists.

        Args:
            db_path: Filesystem path to the SQLite state database.
        """
        self.db_path = db_path
        self._conn: sqlite3.Connection = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS problems (
                fingerprint TEXT PRIMARY KEY,
                issue_iid INTEGER,
                patrol_count INTEGER DEFAULT 1,
                last_seen TEXT
            )
            """
        )
        self._conn.commit()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def get(self, fingerprint: str) -> StateRow | None:
        """Return the stored patrol state for a fingerprint, if present.

        Args:
            fingerprint: Fingerprint key to look up.

        Returns:
            The stored state row, or `None` if the fingerprint is unknown.
        """
        row = self._conn.execute(
            "SELECT issue_iid, patrol_count, last_seen FROM problems WHERE fingerprint = ?",
            (fingerprint,),
        ).fetchone()
        if row is None:
            return None
        return {
            "issue_iid": int(row["issue_iid"]),
            "patrol_count": int(row["patrol_count"]),
            "last_seen": str(row["last_seen"]),
        }

    def upsert(self, fingerprint: str, issue_iid: int, patrol_count: int) -> None:
        """Insert or update patrol state for a fingerprint.

        Args:
            fingerprint: Fingerprint key to insert or update.
            issue_iid: GitLab issue IID associated with the fingerprint.
            patrol_count: Number of patrol runs that have seen the fingerprint.
        """
        self._conn.execute(
            """
            INSERT INTO problems (fingerprint, issue_iid, patrol_count, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(fingerprint) DO UPDATE SET
                issue_iid=excluded.issue_iid,
                patrol_count=excluded.patrol_count,
                last_seen=excluded.last_seen
            """,
            (fingerprint, issue_iid, patrol_count, self._now_iso()),
        )
        self._conn.commit()

    def get_all(self) -> list[StateRecord]:
        """Return all persisted patrol state rows.

        Returns:
            Every persisted patrol state record in the database.
        """
        rows = self._conn.execute(
            "SELECT fingerprint, issue_iid, patrol_count, last_seen FROM problems"
        ).fetchall()
        return [
            {
                "fingerprint": str(row["fingerprint"]),
                "issue_iid": int(row["issue_iid"]),
                "patrol_count": int(row["patrol_count"]),
                "last_seen": str(row["last_seen"]),
            }
            for row in rows
        ]

    def delete(self, fingerprint: str) -> None:
        """Delete persisted patrol state for a fingerprint.

        Args:
            fingerprint: Fingerprint key to remove.
        """
        self._conn.execute("DELETE FROM problems WHERE fingerprint = ?", (fingerprint,))
        self._conn.commit()
