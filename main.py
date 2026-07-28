import sys

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python main.py <tg|cli>")
        sys.exit(1)

    mode = sys.argv[1]

    from data.service_db import ResourceDB, UserDB
    from data.utils import start_db

    start_db()
    resource_db = ResourceDB()
    user_db = UserDB()

    if mode == "tg":
        from core.service import UserService
        from ui.tg_bot.dispatcher import start_bot

        start_bot(user_db, resource_db, UserService())
    elif mode == "cli":
        from ui.cli.cli import start_cli

        start_cli(resource_db)
    else:
        print(f"Неизвестный режим: {mode}")
        sys.exit(1)
