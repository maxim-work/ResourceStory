import sys

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python main.py <tg|cli>")
        sys.exit(1)

    mode = sys.argv[1]

    from data.service_db import ResourceDB, UserDB
    from data.utils import start_db

    start_db()
    db = ResourceDB()
    user_db = UserDB

    if mode == "tg":
        from ui.tg_bot.dispatcher import start_bot

        start_bot(user_db)
    elif mode == "cli":
        from ui.cli.cli import start_cli

        start_cli(db)
    else:
        print(f"Неизвестный режим: {mode}")
        sys.exit(1)
