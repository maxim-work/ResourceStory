from data.service_bd import Database
from data.utils import start_db
from ui.cli.main_cli import start_cli

if __name__ == "__main__":
    start_db()
    db = Database()
    start_cli(db)
