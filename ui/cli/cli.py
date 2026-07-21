import os
import sys

from data_io.export_data import write_data_file, write_urls_file
from data_io.import_data import parse_data

from .handlers import add_video_cli, edit_video_cli, search_cli, show_all_videos


def setup_encoding():
    try:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = open(
                sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1
            )
    except Exception:
        pass


def clear():
    if sys.platform == "win32":
        os.system("cls")
    else:
        os.system("clear")


def pause():
    input("\nEnter — дальше")


def start_cli(db):
    clear()

    while True:
        print("=== База знаний ===\n")
        print("1. Добавить")
        print("2. Поиск")
        print("3. Удалить по id")
        print("4. Удалить все")
        print("5. Показать все")
        print("6. Редактировать")
        print("7. Экспорт")
        print("8. Импорт")
        print("0. Выход")

        user_enter = input("\n: ").strip()

        if user_enter == "1":
            add_video_cli(db, clear, pause)
        elif user_enter == "2":
            search_cli(db, clear, pause)
        elif user_enter == "3":
            clear()
            print("=== Удаление по id ===\n")
            id_resource = input("Введите id: ").strip()
            if id_resource.isdigit():
                db.delete(int(id_resource))
                print("Done!", flush=True)
                pause()
        elif user_enter == "4":
            clear()
            print("=== Очистка всей базы ===\n")
            confirm = input("Точно удалить ВСЁ? (yes/no): ").strip()
            if confirm.lower() == "yes":
                db.delete_all()
                print("Done!", flush=True)
                pause()
        elif user_enter == "5":
            show_all_videos(db, clear, pause)
        elif user_enter == "6":
            edit_video_cli(db, clear, pause)
        elif user_enter == "7":
            clear()
            print("=== Экспорт ===\n")
            print("1. Экспорт ссылок")
            print("2. Экспорт всей базы")

            choice = input("\n: ").strip()

            if choice in ("1", "2"):
                clear()
                print("=== Экспорт ===\n")
                fname = input("Имя файла (Enter — по умолчанию): ").strip()

                if choice == "1":
                    urls = db.export_urls()
                    path, count = write_urls_file(urls, fname or "urls.txt")
                    clear()
                    print("=== Экспорт ===\n")
                    print(f"{count} ссылок → {path}", flush=True)
                elif choice == "2":
                    data = db.export_data()
                    path, count = write_data_file(data, fname or "data.json")
                    clear()
                    print("=== Экспорт ===\n")
                    print(f"{count} шт. → {path}", flush=True)
            else:
                clear()
                print("=== Экспорт ===\n")
                print("Неверный выбор", flush=True)

            pause()
        elif user_enter == "8":
            clear()
            print("=== Импорт ===\n")
            filepath = input("Путь к JSON файлу: ").strip()

            if not filepath:
                print("Путь не указан", flush=True)
                pause()
                continue

            if not os.path.exists(filepath):
                print(f"Файл не найден: {filepath}", flush=True)
                pause()
                continue

            try:
                data = parse_data(filepath)
                added, total = db.import_data(data)
                clear()
                print("=== Импорт ===\n")
                print(
                    f"Добавлено {added} из {total} (пропущено {total - added})",
                    flush=True,
                )
            except Exception as e:
                clear()
                print("=== Импорт ===\n")
                print(f"Ошибка: {e}", flush=True)

            pause()
        elif user_enter in ["0", "exit"]:
            clear()
            break
        else:
            clear()
            print("=== База знаний ===\n")
            print("Неверный ввод, попробуйте снова", flush=True)
            pause()
        clear()
