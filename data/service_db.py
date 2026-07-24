import json
import sqlite3
from datetime import datetime
from typing import Optional

from core.models.resource import (
    Resource,
    ResourceKind,
    ResourcePlatform,
    ResourceStatus,
    ResourceType,
)
from core.models.user import User
from data.exceptions import DuplicateResourceError, DuplicateUserError
from data.filter import ResourceFilter, calculate_scores


class ResourceDB:
    def __init__(self, path="data/database.db"):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def insert(self, resource: Resource):
        try:
            with self.conn as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO resources (
                        tg_id, title, description, resource_type, platform, kind, external_id, url,
                        status, tags, my_notes, my_rating, engagement, views,
                        duration, published_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        resource.tg_id if resource.tg_id is not None else 1,
                        resource.title,
                        resource.description,
                        resource.resource_type.code,
                        resource.platform.code,
                        resource.kind.code,
                        resource.external_id,
                        resource.url,
                        resource.status.code,
                        json.dumps(resource.tags, ensure_ascii=False),
                        resource.my_notes,
                        resource.my_rating,
                        resource.engagement,
                        resource.views,
                        resource.duration,
                        resource.published_at.isoformat()
                        if resource.published_at
                        else None,
                        resource.completed_at.isoformat()
                        if resource.completed_at
                        else None,
                    ),
                )
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            raise DuplicateResourceError(resource.url)

    def update(self, resource: Resource):
        with self.conn as conn:
            conn.execute(
                """
                UPDATE resources
                SET resource_type = ?, status = ?, platform = ?, kind = ?, my_notes = ?, my_rating = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    resource.resource_type.code,
                    resource.status.code,
                    resource.platform.code,
                    resource.kind.code,
                    resource.my_notes,
                    resource.my_rating,
                    resource.completed_at.isoformat()
                    if resource.completed_at
                    else None,
                    resource.id,
                ),
            )

    def delete(self, resource_id: int, tg_id: int) -> None:
        with self.conn as conn:
            conn.execute(
                "DELETE FROM resources WHERE id = ? AND tg_id = ?",
                (resource_id, tg_id),
            )

    def delete_all(self, tg_id: int) -> None:
        with self.conn as conn:
            conn.execute("DELETE FROM resources WHERE tg_id = ?", (tg_id,))

    def get(self, resource_id: int, tg_id: int):
        with self.conn as conn:
            cursor = conn.execute(
                "SELECT * FROM resources WHERE id = ? AND tg_id = ?",
                (resource_id, tg_id),
            )
            row = cursor.fetchone()

        return self._row_to_resource(row) if row else None

    def get_all_resources(self, tg_id: int) -> list[Resource]:
        with self.conn as conn:
            cursor = conn.execute("SELECT * FROM resources WHERE tg_id = ?", (tg_id,))
            rows = cursor.fetchall()
        return [self._row_to_resource(row) for row in rows]

    def search(
        self, tg_id: int, filter: Optional[ResourceFilter] = None
    ) -> list[tuple[Resource, int]]:
        if filter is None:
            filter = ResourceFilter(tg_id)

        resources = self._get_candidates(filter)
        return calculate_scores(resources, filter)

    def export_urls(self, tg_id: int) -> list[str]:
        with self.conn as conn:
            cursor = conn.execute("SELECT url FROM resources WHERE tg_id = ?", (tg_id,))
            rows = cursor.fetchall()
        return [row["url"] for row in rows]

    def export_data(self, tg_id: int) -> list[Resource]:
        with self.conn as conn:
            cursor = conn.execute("SELECT * FROM resources WHERE tg_id = ?", (tg_id,))
            rows = cursor.fetchall()
        return [self._row_to_resource(row) for row in rows]

    def import_data(
        self, data: list[Resource], tg_id: Optional[int] = None
    ) -> tuple[int, int]:
        count = 0
        total = len(data)

        with self.conn as conn:
            conn.execute("BEGIN")
            for resource in data:
                try:
                    resource_tg_id = resource.tg_id or tg_id or 1
                    conn.execute(
                        """INSERT INTO resources
                        (tg_id, title, url, description, resource_type, platform, kind,
                            external_id, status, tags, my_notes, my_rating,
                            engagement, views, duration, published_at, completed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            resource_tg_id,
                            resource.title,
                            resource.url,
                            resource.description,
                            resource.resource_type.code,
                            resource.platform.code,
                            resource.kind.code,
                            resource.external_id,
                            resource.status.code,
                            json.dumps(resource.tags),
                            resource.my_notes,
                            resource.my_rating,
                            resource.engagement,
                            resource.views,
                            resource.duration,
                            resource.published_at.isoformat()
                            if resource.published_at
                            else None,
                            resource.completed_at.isoformat()
                            if resource.completed_at
                            else None,
                        ),
                    )
                    count += 1
                except sqlite3.IntegrityError:
                    continue

            conn.commit()

        return count, total

    def _get_candidates(self, f: ResourceFilter) -> list[Resource]:
        query = "SELECT * FROM resources WHERE 1=1"
        params: list = []
        query += " AND tg_id = ?"
        params.append(f.tg_id)

        if f.resource_type is not None:
            query += " AND resource_type = ?"
            params.append(f.resource_type.code)

        if f.status is not None:
            query += " AND status = ?"
            params.append(f.status.code)

        if f.platform is not None:
            query += " AND platform = ?"
            params.append(f.platform.code)

        if f.kind is not None:
            query += " AND kind = ?"
            params.append(f.kind.code)

        if f.max_duration is not None:
            query += " AND duration <= ?"
            params.append(f.max_duration)

        if f.uncompleted_only:
            query += " AND completed_at IS NULL"
        elif f.recently_completed or f.long_ago_completed:
            query += " AND completed_at IS NOT NULL"

        query += " ORDER BY created_at DESC"

        with self.conn as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_resource(row) for row in rows]

    def _row_to_resource(self, row) -> Resource:
        return Resource(
            id=row["id"],
            tg_id=row["tg_id"],
            title=row["title"],
            description=row["description"],
            resource_type=ResourceType.from_code(row["resource_type"]),
            platform=ResourcePlatform.from_code(row["platform"]),
            kind=ResourceKind.from_code(row["kind"]),
            external_id=row["external_id"],
            url=row["url"],
            status=ResourceStatus.from_code(row["status"]),
            tags=json.loads(row["tags"]),
            my_notes=row["my_notes"],
            my_rating=row["my_rating"],
            engagement=row["engagement"],
            views=row["views"],
            duration=row["duration"],
            published_at=datetime.fromisoformat(row["published_at"])
            if row["published_at"]
            else None,
            completed_at=datetime.fromisoformat(row["completed_at"])
            if row["completed_at"]
            else None,
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class UserDB:
    def __init__(self, path="data/database.db"):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def insert(self, user: User):
        with self.conn as conn:
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO users(tg_id, username, first_name, last_name, is_active, last_active_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)""",
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
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                raise DuplicateUserError(user.tg_id)

    def update(self, user: User):
        with self.conn as conn:
            conn.execute(
                """
                UPDATE users SET first_name = ?, last_name = ?, username = ? WHERE tg_id = ?""",
                (user.first_name, user.last_name, user.username, user.tg_id),
            )

    def delete(self, tg_id: int) -> None:
        with self.conn as conn:
            conn.execute("DELETE FROM users WHERE tg_id = ?", (tg_id,))

    def delete_all_users(self) -> None:
        with self.conn as conn:
            conn.execute("DELETE FROM users")
            conn.execute("DELETE FROM sqlite_sequence WHERE name='users'")

    def get(self, tg_id) -> Optional[User]:
        with self.conn as conn:
            cursor = conn.execute(
                "SELECT * FROM users WHERE tg_id = ?",
                (tg_id,),
            )
            row = cursor.fetchone()

        return self._row_to_user(row) if row else None

    def get_users(self) -> list[User]:
        with self.conn as conn:
            cursor = conn.execute("SELECT * FROM users")
            rows = cursor.fetchall()
        return [self._row_to_user(row) for row in rows]

    def update_last_active(self, tg_id: int) -> None:
        with self.conn as conn:
            conn.execute(
                "UPDATE users SET last_active_at = ? WHERE tg_id = ?",
                (datetime.now().isoformat(), tg_id),
            )

    def _row_to_user(self, row) -> User:
        return User(
            id=row["id"],
            tg_id=row["tg_id"],
            username=row["username"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            last_active_at=datetime.fromisoformat(row["last_active_at"])
            if row["last_active_at"]
            else None,
            created_at=datetime.fromisoformat(row["created_at"]),
        )
