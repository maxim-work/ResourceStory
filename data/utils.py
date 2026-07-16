import sqlite3


def start_db(path: str = "data/database.db") -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT NULL,
                resource_type TEXT NOT NULL DEFAULT 'other',
                platform TEXT NOT NULL DEFAULT 'other',
                kind TEXT NOT NULL DEFAULT 'other',
                external_id TEXT DEFAULT NULL,
                url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'to_teach',
                tags TEXT NOT NULL DEFAULT '[]',
                my_notes TEXT,
                my_rating INTEGER,
                engagement INTEGER,
                views INTEGER,
                duration INTEGER,
                published_at DATETIME,
                completed_at DATETIME,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_resources_status ON resources(status)"
        )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_resources_resource_type ON resources(resource_type)"
        )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_resources_external_id ON resources(external_id)"
        )

        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_resources_url ON resources(url)"
        )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_created_at ON resources(created_at)"
        )
