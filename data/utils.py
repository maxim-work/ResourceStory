import sqlite3


def start_db(path: str = "data/database.db") -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER NOT NULL UNIQUE,
                username TEXT,
                first_name TEXT NOT NULL,
                last_name TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_active_at DATETIME
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_tg_id ON users(tg_id)")

        conn.execute("""
            INSERT OR IGNORE INTO users (id, tg_id, first_name)
            VALUES (1, 0, 'cli_user')
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL DEFAULT 1,
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
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_resources_user_id ON resources(user_id)"
        )
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
            "CREATE INDEX IF NOT EXISTS idx_resources_created_at ON resources(created_at)"
        )
