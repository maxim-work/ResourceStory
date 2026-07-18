import re
from datetime import datetime

from config import YOUTUBE_API_KEY
from core.exceptions import (
    APIResponseError,
    InvalidParamError,
    InvalidRatingError,
    InvalidUrlParamError,
    NetworkError,
    ProxyRequestError,
    ResourceNotFoundError,
)
from core.models.resource import ResourceKind, ResourceStatus, ResourceType
from core.service import ResourceService
from data.exceptions import (
    DuplicateResourceError,
    EmptyDatabaseError,
)
from data.filter import InvalidFilterError, ResourceFilter


def clean_tags(tags: list[str]) -> list[str]:
    cleaned = []
    for tag in tags:
        tag = re.sub(r"[^\w\s\-]", "", tag)
        tag = tag.strip()
        if tag:
            cleaned.append(tag)
    return cleaned


def _choose_enum(clear, pause, title: str, enum_cls, default=None):
    while True:
        clear()
        print(f"=== {title} ===\n")
        items = list(enum_cls)
        for i, item in enumerate(items, 1):
            print(f"  {i}. {item.label}")

        if default is not None:
            prompt = f"Номер (Enter={default.label}): "
        else:
            prompt = "Номер: "

        choice = input(prompt).strip()
        if not choice:
            return default
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(items):
                return items[idx - 1]
        print(f"ERROR: Введите число от 1 до {len(items)}", flush=True)
        pause()


def _choose_tags(clear, title, pause, existing_tags: list[str] | None) -> list[str]:
    clear()
    print("=== Тэги ===\n")
    print(f"Title: {title}\n")

    if existing_tags:
        print(f"Текущие: {', '.join(existing_tags)}")
        print("\n[y] оставить  [n] новые  [Enter] дополнить")
        choice = input(": ").strip().lower()

        if choice == "n":
            tags_input = input("Новые тэги: ").strip()
            return (
                [t.strip() for t in tags_input.split(",") if t.strip()]
                if tags_input
                else []
            )
        elif choice == "":
            tags_input = input("Дополнить: ").strip()
            extra = (
                [t.strip() for t in tags_input.split(",") if t.strip()]
                if tags_input
                else []
            )
            return existing_tags + extra
        else:
            return existing_tags
    else:
        tags_input = input("Тэги через запятую: ").strip()
        return (
            [t.strip() for t in tags_input.split(",") if t.strip()]
            if tags_input
            else []
        )


def add_video_cli(db, clear, pause):
    clear()
    print("=== Добавление ресурса ===\n")

    url = input("URL: ").strip()
    if not url:
        print("ERROR: URL обязателен", flush=True)
        pause()
        return

    resource_type = _choose_enum(
        clear, pause, "Тип ресурса", ResourceType, ResourceType.OTHER
    )
    kind = _choose_enum(clear, pause, "Формат ресурса", ResourceKind, None)

    clear()
    print("=== Добавление ресурса ===\n")
    proxy_input = input(
        "Прокси host:port (Enter=без прокси, d=127.0.0.1:10809): "
    ).strip()
    proxy = "127.0.0.1:10809" if proxy_input.lower() == "d" else (proxy_input or None)

    try:
        resource = ResourceService.create_resource(
            user_id=1,
            url=url,
            resource_type=resource_type,
            kind=kind,
            proxy=proxy,
            youtube_api_key=YOUTUBE_API_KEY,
        )
    except InvalidUrlParamError as e:
        clear()
        print(f"ERROR: {e}")
        pause()
        return
    except InvalidParamError as e:
        clear()
        print(f"ERROR: Некорректный параметр «{e.param}»: {e}")
        pause()
        return
    except InvalidRatingError as e:
        clear()
        print(f"ERROR: {e}")
        pause()
        return
    except ResourceNotFoundError as e:
        clear()
        print(f"ERROR: Ресурс не найден: {e}")
        pause()
        return
    except ProxyRequestError as e:
        clear()
        print(f"ERROR: Проблема с прокси ({e.proxy}): {e.original_error}")
        pause()
        return
    except APIResponseError as e:
        clear()
        print(f"ERROR: Ошибка API (код {e.code})")
        pause()
        return
    except NetworkError as e:
        clear()
        print(f"ERROR: Сетевая ошибка: {e}")
        pause()
        return

    tags = _choose_tags(clear, resource.title, pause, resource.tags)
    resource.tags = clean_tags(tags)

    try:
        resource_id = db.insert(resource)
    except DuplicateResourceError as e:
        clear()
        print(f"ERROR: {e}")
        pause()
        return

    clear()
    print("=== Добавлен ресурс ===\n")
    print(f"  {resource.title}")
    print(f"   Тип: {resource.resource_type.label}")
    print(f"   Формат: {resource.kind.label}")
    print(f"   Платформа: {resource.platform.label}")
    print(f"   Тэги: {', '.join(resource.tags)}")
    print(f"   Длительность: {resource.duration_display}")
    print(f"   Рейтинг: {resource.rating:.1f}")
    print(f"   ID: {resource_id}")

    pause()


def search_cli(db, clear, pause):
    while True:
        clear()
        print("=== Поиск ===\n")
        print("Тип ресурса:")
        types_list = list(ResourceType)
        print("  0. Любой")
        for i, rt in enumerate(types_list, 1):
            print(f"  {i}. {rt.label}")
        choice = input("Номер типа (Enter=0): ").strip()
        if not choice or choice == "0":
            resource_type = None
            break
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(types_list):
                resource_type = types_list[idx - 1]
                break
        print(f"ERROR: Введите число от 0 до {len(types_list)}", flush=True)
        pause()

    while True:
        clear()
        print("=== Поиск ===\n")
        print("Статус:")
        status_list = list(ResourceStatus)
        print("  0. Любой")
        for i, st in enumerate(status_list, 1):
            print(f"  {i}. {st.label}")
        choice = input("Номер статуса (Enter=0): ").strip()
        if not choice or choice == "0":
            status = None
            break
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(status_list):
                status = status_list[idx - 1]
                break
        print(f"ERROR: Введите число от 1 до {len(status_list)}", flush=True)
        pause()

    clear()
    print("=== Поиск ===\n")
    keywords = input("Ключевые слова (Enter — пропустить): ").strip() or None

    clear()
    print("=== Поиск ===\n")
    tags_input = input("Тэги через запятую (Enter — пропустить): ").strip()
    tags = (
        [t.strip() for t in tags_input.split(",") if t.strip()] if tags_input else None
    )

    uncompleted_only = True
    recently_completed = False
    long_ago_completed = False
    while True:
        clear()
        print("=== Поиск ===\n")
        print("Статус просмотра:")
        print("  0. Любые")
        print("  1. Непросмотренные")
        print("  2. Недавно просмотренные")
        print("  3. Давно просмотренные")
        choice = input("Выбор (Enter=1): ").strip()
        if not choice or choice == "1":
            break
        elif choice == "0":
            uncompleted_only = False
            break
        elif choice == "2":
            uncompleted_only = False
            recently_completed = True
            break
        elif choice == "3":
            uncompleted_only = False
            long_ago_completed = True
            break
        print("ERROR: Введите 0-3", flush=True)
        pause()

    clear()
    print("=== Поиск ===\n")
    max_dur = input("Макс. длительность в минутах (Enter — любая): ").strip()
    max_duration = int(max_dur) if max_dur.isdigit() else None

    clear()
    print("=== Поиск ===\n")
    limit_input = input("Сколько показать (Enter=10): ").strip()
    limit = int(limit_input) if limit_input.isdigit() else 10

    try:
        f = ResourceFilter(
            resource_type=resource_type,
            status=status,
            tags=tags,
            keywords=keywords,
            uncompleted_only=uncompleted_only,
            recently_completed=recently_completed,
            long_ago_completed=long_ago_completed,
            max_duration=max_duration,
            limit=limit,
        )
    except InvalidFilterError as e:
        clear()
        print(f"ERROR: {e}")
        pause()
        return

    try:
        results = db.search(f)
    except EmptyDatabaseError:
        clear()
        print("База пуста")
        pause()
        return

    clear()
    if results:
        page = 0
        per_page = 1
        total_pages = (len(results) + per_page - 1) // per_page

        while True:
            clear()
            start = page * per_page
            end = min(start + per_page, len(results))

            print(
                f"=== Результаты ({len(results)}) стр. {page + 1}/{total_pages} ===\n"
            )

            for i in range(start, end):
                resource, score = results[i]
                print(f"{i + 1:2d}. {resource.title}")
                print(f"    url: {resource.url}")
                print(f"    id: {resource.id}")
                print(
                    f"    {resource.resource_type.label} | {resource.duration_display} | Рейтинг: {resource.rating:.1f}"
                )
                if resource.tags:
                    print(f"    Тэги: {', '.join(resource.tags)}")
                print()

            print("─" * 40)
            nav = []
            if page > 0:
                nav.append("p — назад")
            if page < total_pages - 1:
                nav.append("n — вперёд")
            nav.append("q — выход")
            print(" | ".join(nav))

            cmd = input(": ").strip().lower()
            if cmd == "n" and page < total_pages - 1:
                page += 1
            elif cmd == "p" and page > 0:
                page -= 1
            elif cmd == "q":
                break
    else:
        print("Ничего не найдено")
        pause()


def show_all_videos(db, clear, pause):
    clear()

    f = ResourceFilter(
        resource_type=None,
        status=None,
        tags=None,
        sort_by_my_rating=False,
        sort_by_rating=False,
        newest_published=False,
        oldest_published=False,
        uncompleted_only=False,
        recently_completed=False,
        long_ago_completed=False,
        keywords=None,
        max_duration=None,
        limit=1000,
    )

    try:
        results = db.search(f)
    except EmptyDatabaseError:
        clear()
        print("=== Все ресурсы ===\n")
        print("База пуста")
        pause()
        return

    if not results:
        print("=== Все ресурсы ===\n")
        print("База пуста")
        pause()
        return

    idx = 0
    total = len(results)

    while True:
        clear()
        resource, score = results[idx]

        print(f"{'─' * 50}")
        print(f"#{idx + 1} из {total} (ID: {resource.id})")
        print(f"Название: {resource.title}")
        desc = resource.description or ""
        print(f"Описание: {desc[:200]}{'...' if len(desc) > 200 else ''}")
        print(f"Тип: {resource.resource_type.label}")
        print(f"Формат: {resource.kind.label}")
        print(f"Статус: {resource.status.label}")
        print(f"Платформа: {resource.platform.label}")
        print(f"URL: {resource.url}")
        print(f"External ID: {resource.external_id}")
        print(f"Тэги: {', '.join(resource.tags) if resource.tags else 'нет'}")
        print(f"Заметки: {resource.my_notes or 'нет'}")
        print(
            f"Мой рейтинг: {resource.my_rating}/5"
            if resource.my_rating
            else "Мой рейтинг: —"
        )
        print(f"Вовлеченность: {resource.engagement}, Просмотров: {resource.views}")
        print(f"Рейтинг: {resource.rating:.1f}")
        print(f"Длительность: {resource.duration_display}")
        print(f"Опубликовано: {resource.published_at or 'неизвестно'}")
        print(f"Завершено: {resource.completed_at or 'нет'}")
        print(f"Добавлено: {resource.created_at}")

        print(f"\n{'─' * 50}")
        nav_parts = []
        if idx > 0:
            nav_parts.append("p — назад")
        if idx < total - 1:
            nav_parts.append("n — вперёд")
        nav_parts.append("q — выход")
        print(" | ".join(nav_parts))

        cmd = input(": ").strip().lower()
        if cmd == "n" and idx < total - 1:
            idx += 1
        elif cmd == "p" and idx > 0:
            idx -= 1
        elif cmd == "q":
            break

    clear()


def edit_video_cli(db, clear, pause):
    clear()
    print("=== Редактирование ===\n")

    id_input = input("ID ресурса (Enter — найти поиском): ").strip()

    if id_input and id_input.isdigit():
        try:
            resource = db.get(int(id_input))
        except ResourceNotFoundError as e:
            clear()
            print(f"ERROR: {e}")
            pause()
            return
    else:
        clear()
        print("=== Редактирование ===\n")
        keywords = input("Ключевые слова для поиска: ").strip()
        if not keywords:
            clear()
            print("=== Редактирование ===\n")
            print("ERROR: Нужен ID или ключевые слова", flush=True)
            pause()
            return

        f = ResourceFilter(keywords=keywords, limit=10)
        try:
            results = db.search(f)
        except EmptyDatabaseError:
            clear()
            print("База пуста")
            pause()
            return

        if not results:
            clear()
            print("=== Редактирование ===\n")
            print("ERROR: Ничего не найдено", flush=True)
            pause()
            return

        while True:
            clear()
            print(f"=== Найдено ({len(results)}) ===\n")
            for i, (r, score) in enumerate(results, 1):
                print(f"{i}. [{score}] {r.title}")
            choice = input("\nНомер: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(results):
                resource = results[int(choice) - 1][0]
                break
            print(f"ERROR: Введите число от 1 до {len(results)}", flush=True)
            pause()

    while True:
        clear()
        print(f"=== Редактирование: {resource.title} ===\n")
        print(f"1. Тип: {resource.resource_type.label}")
        print(f"2. Формат:  {resource.kind.label if resource.kind else '—'}")
        print(f"3. Статус: {resource.status.label}")
        print(f"4. Тэги: {', '.join(resource.tags) if resource.tags else 'нет'}")
        print(f"5. Заметки: {resource.my_notes or 'нет'}")
        print(f"6. Мой рейтинг: {resource.my_rating or '—'}/5")
        print(f"7. Дата завершения: {resource.completed_at or 'нет'}")
        print("0. Сохранить и выйти")
        choice = input("\nЧто меняем: ").strip()

        if choice == "1":
            resource.update_type(_choose_enum(clear, pause, "Тип", ResourceType))

        elif choice == "2":
            resource.kind = _choose_enum(clear, pause, "Формат", ResourceKind)

        elif choice == "3":
            new_status = _choose_enum(clear, pause, "Статус", ResourceStatus)
            resource.update_status(new_status)

        elif choice == "4":
            resource.tags = clean_tags(
                _choose_tags(clear, resource.title, pause, resource.tags)
            )

        elif choice == "5":
            clear()
            print("=== Заметка ===\n")
            if resource.my_notes:
                print(f"Текущая:\n{resource.my_notes}\n")
                print("1. Исправить")
                print("2. Новая")
                print("3. Удалить")
                print("0. Оставить")
                action = input("\n: ").strip()
                if action == "1":
                    clear()
                    print("=== Заметка ===\n")
                    print(f"Текущая:\n{resource.my_notes}\n")
                    new_notes = input("Исправленная: ").strip()
                    if new_notes:
                        resource.update_my_notes(new_notes)
                elif action == "2":
                    clear()
                    resource.update_my_notes(input("Новая заметка: ").strip())
                elif action == "3":
                    resource.update_my_notes("")
            else:
                resource.update_my_notes(input("Новая заметка: ").strip())
            pause()

        elif choice == "6":
            while True:
                clear()
                print("=== Мой рейтинг ===\n")
                r = input("Рейтинг (1-5): ").strip()
                if r.isdigit() and 1 <= int(r) <= 5:
                    try:
                        resource.update_my_rating(int(r))
                    except InvalidRatingError as e:
                        print(f"ERROR: {e}")
                        pause()
                        continue
                    break
                print("ERROR: Введите 1-5")
                pause()

        elif choice == "7":
            clear()
            print("=== Дата завершения ===\n")
            d = input("Дата (YYYY-MM-DD HH:MM, Enter — сейчас): ").strip()
            if d:
                try:
                    resource.completed_at = datetime.fromisoformat(d)
                except ValueError:
                    print("ERROR: Неверный формат", flush=True)
                    pause()
            else:
                resource.completed_at = datetime.now()

        elif choice == "0":
            db.update(resource)
            clear()
            print(f"=== {resource.title} ===\n")
            print("Сохранено!", flush=True)
            pause()
            break

        else:
            print("ERROR: Неверный выбор")
            pause()
