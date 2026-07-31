import sqlite3
from datetime import datetime
from typing import Any, Optional

from core.exceptions import ResourceNotFoundError
from core.models.resource import Resource
from core.models.user import User
from data.exceptions import DuplicateResourceError, DuplicateUserError
from data.filter import ResourceFilter, calculate_scores


class ResourceDB:
    COLUMNS = [
        "tg_id",
        "title",
        "url",
        "description",
        "resource_type",
        "platform",
        "kind",
        "external_id",
        "status",
        "tags",
        "my_notes",
        "my_rating",
        "engagement",
        "views",
        "duration",
        "published_at",
        "completed_at",
    ]

    def __init__(self, path: str = "data/database.db"):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def insert(self, resource: Resource) -> int:
        try:
            data = resource.to_db_dict()
            with self.conn:
                cursor = self.conn.execute(self._build_insert_query(), data)
                if cursor.lastrowid is None:
                    raise RuntimeError("Failed to insert resource")
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            raise DuplicateResourceError(resource.url)

    def update(self, resource: Resource) -> None:
        data = resource.to_db_dict()
        data["id"] = resource.id

        with self.conn:
            cursor = self.conn.execute(self._build_update_query(), data)
            if cursor.rowcount == 0:
                raise ResourceNotFoundError(str(resource.id))

    def delete(self, resource_id: int, tg_id: int) -> None:
        with self.conn:
            self.conn.execute(
                "DELETE FROM resources WHERE id = ? AND tg_id = ?",
                (resource_id, tg_id),
            )

    def delete_all(self, tg_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM resources WHERE tg_id = ?", (tg_id,))

    def get(self, resource_id: int, tg_id: int) -> Optional[Resource]:
        with self.conn:
            row = self.conn.execute(
                "SELECT * FROM resources WHERE id = ? AND tg_id = ?",
                (resource_id, tg_id),
            ).fetchone()
        return Resource(**dict(row)) if row else None

    def get_all_resources(self, tg_id: int) -> list[Resource]:
        with self.conn:
            rows = self.conn.execute(
                "SELECT * FROM resources WHERE tg_id = ? ORDER BY created_at DESC",
                (tg_id,),
            ).fetchall()
        return [Resource(**dict(row)) for row in rows]

    def count(self, tg_id: int) -> int:
        with self.conn:
            row = self.conn.execute(
                "SELECT COUNT(*) as count FROM resources WHERE tg_id = ?",
                (tg_id,),
            ).fetchone()
        return row["count"] if row else 0

    def search(
        self, tg_id: int, filter: Optional[ResourceFilter] = None
    ) -> list[tuple[Resource, int]]:
        if filter is None:
            filter = ResourceFilter(tg_id)
        resources = self._get_candidates(filter)
        return calculate_scores(resources, filter)

    def export_urls(self, tg_id: int) -> list[str]:
        with self.conn:
            rows = self.conn.execute(
                "SELECT url FROM resources WHERE tg_id = ?", (tg_id,)
            ).fetchall()
        return [row["url"] for row in rows]

    def export_data(self, tg_id: int) -> list[Resource]:
        with self.conn:
            rows = self.conn.execute(
                "SELECT * FROM resources WHERE tg_id = ?", (tg_id,)
            ).fetchall()
        return [Resource(**dict(row)) for row in rows]

    def import_data(
        self, data: list[Resource], tg_id: Optional[int] = None
    ) -> tuple[int, int]:
        count = 0
        total = len(data)

        with self.conn:
            for resource in data:
                try:
                    resource.tg_id = resource.tg_id or tg_id or 1
                    resource_data = resource.to_db_dict()
                    self.conn.execute(self._build_insert_query(), resource_data)
                    count += 1
                except sqlite3.IntegrityError:
                    continue
            self.conn.commit()

        return count, total

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _get_candidates(self, f: ResourceFilter) -> list[Resource]:
        query = "SELECT * FROM resources WHERE tg_id = :tg_id"
        params: dict[str, Any] = {"tg_id": f.tg_id}

        if f.resource_type is not None:
            query += " AND resource_type = :resource_type"
            params["resource_type"] = f.resource_type.code

        if f.status is not None:
            query += " AND status = :status"
            params["status"] = f.status.code

        if f.platform is not None:
            query += " AND platform = :platform"
            params["platform"] = f.platform.code

        if f.kind is not None:
            query += " AND kind = :kind"
            params["kind"] = f.kind.code

        if f.max_duration is not None:
            query += " AND duration <= :max_duration"
            params["max_duration"] = f.max_duration

        if f.uncompleted_only:
            query += " AND completed_at IS NULL"
        elif f.recently_completed or f.long_ago_completed:
            query += " AND completed_at IS NOT NULL"

        query += " ORDER BY created_at DESC"

        with self.conn:
            rows = self.conn.execute(query, params).fetchall()
        return [Resource(**dict(row)) for row in rows]

    def _build_insert_query(self) -> str:
        cols = ", ".join(self.COLUMNS)
        placeholders = ", ".join(f":{col}" for col in self.COLUMNS)
        return f"INSERT INTO resources ({cols}) VALUES ({placeholders})"

    def _build_update_query(self) -> str:
        sets = ", ".join(f"{col} = :{col}" for col in self.COLUMNS)
        return f"UPDATE resources SET {sets} WHERE id = :id"


class UserDB:
    def __init__(self, path: str = "data/database.db"):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def insert(self, user: User) -> int:
        with self.conn:
            try:
                cursor = self.conn.execute(
                    """INSERT INTO users(tg_id, username, first_name, last_name,
                       is_active, last_active_at, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        user.tg_id,
                        user.username,
                        user.first_name,
                        user.last_name,
                        user.is_active,
                        user.last_active_at,
                        user.created_at,
                    ),
                )
                return cursor.lastrowid or 0
            except sqlite3.IntegrityError:
                raise DuplicateUserError(user.tg_id)

    def update(self, user: User) -> None:
        with self.conn:
            self.conn.execute(
                """UPDATE users
                   SET first_name = ?, last_name = ?, username = ?
                   WHERE tg_id = ?""",
                (user.first_name, user.last_name, user.username, user.tg_id),
            )

    def delete(self, tg_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM users WHERE tg_id = ?", (tg_id,))

    def delete_all_users(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM users")
            self.conn.execute("DELETE FROM sqlite_sequence WHERE name='users'")

    def get(self, tg_id: int) -> Optional[User]:
        with self.conn:
            row = self.conn.execute(
                "SELECT * FROM users WHERE tg_id = ?", (tg_id,)
            ).fetchone()
        return User(**dict(row)) if row else None

    def get_users(self) -> list[User]:
        with self.conn:
            rows = self.conn.execute("SELECT * FROM users").fetchall()
        return [User(**dict(row)) for row in rows]

    def update_last_active(self, tg_id: int) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE users SET last_active_at = ? WHERE tg_id = ?",
                (datetime.now().isoformat(), tg_id),
            )
