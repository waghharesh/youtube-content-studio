import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).parent / "studio.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """Initialize the SQLite database with the videos table."""
    with get_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                tags TEXT NOT NULL,
                script TEXT NOT NULL,
                video_path TEXT NOT NULL,
                duration REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING_REVIEW',
                youtube_video_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def insert_video(
    topic: str,
    title: str,
    description: str,
    tags: List[str] | str,
    script: str,
    video_path: str,
    duration: float,
    status: str = "PENDING_REVIEW",
    youtube_video_id: Optional[str] = None,
    db_path: Path = DB_PATH,
) -> int:
    """Insert a new video record and return its row ID."""
    tags_str = json.dumps(tags) if isinstance(tags, list) else tags
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO videos (
                topic, title, description, tags, script,
                video_path, duration, status, youtube_video_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                topic,
                title,
                description,
                tags_str,
                script,
                video_path,
                duration,
                status,
                youtube_video_id,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def get_videos_by_status(status: str, db_path: Path = DB_PATH) -> List[Dict[str, Any]]:
    """Fetch all videos matching a given status."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM videos WHERE status = ? ORDER BY id DESC", (status,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def get_all_videos(db_path: Path = DB_PATH) -> List[Dict[str, Any]]:
    """Fetch all videos ordered by newest first."""
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM videos ORDER BY id DESC").fetchall()
        return [_row_to_dict(r) for r in rows]


def get_video_by_id(video_id: int, db_path: Path = DB_PATH) -> Optional[Dict[str, Any]]:
    """Fetch a single video record by its ID."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM videos WHERE id = ?", (video_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None


def update_video_metadata(
    video_id: int,
    title: str,
    description: str,
    tags: List[str] | str,
    db_path: Path = DB_PATH,
) -> None:
    """Update editable metadata before publishing."""
    tags_str = json.dumps(tags) if isinstance(tags, list) else tags
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE videos
            SET title = ?, description = ?, tags = ?
            WHERE id = ?
            """,
            (title, description, tags_str, video_id),
        )
        conn.commit()


def update_video_status(
    video_id: int,
    status: str,
    youtube_video_id: Optional[str] = None,
    db_path: Path = DB_PATH,
) -> None:
    """Update the review/publication status and optional YouTube video ID."""
    with get_connection(db_path) as conn:
        if youtube_video_id is not None:
            conn.execute(
                """
                UPDATE videos
                SET status = ?, youtube_video_id = ?
                WHERE id = ?
                """,
                (status, youtube_video_id, video_id),
            )
        else:
            conn.execute(
                "UPDATE videos SET status = ? WHERE id = ?",
                (status, video_id),
            )
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    item = dict(row)
    raw_tags = item.get("tags", "[]")
    try:
        parsed = json.loads(raw_tags)
        item["tags_list"] = parsed if isinstance(parsed, list) else [str(parsed)]
    except (json.JSONDecodeError, TypeError):
        item["tags_list"] = [t.strip() for t in str(raw_tags).split(",") if t.strip()]
    return item


if __name__ == "__main__":
    init_db()
    print(f"Initialized SQLite database at {DB_PATH}")
