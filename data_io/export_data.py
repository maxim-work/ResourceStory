import json
from pathlib import Path

from config import EXPORT_DIR
from core.models import Resource


def write_urls_file(urls: list[str], filename: str = "urls.txt") -> tuple[Path, int]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = EXPORT_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        for url in urls:
            f.write(url + "\n")

    return filepath, len(urls)


def write_data_file(
    data: list[Resource], filename: str = "data.json"
) -> tuple[Path, int]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = EXPORT_DIR / filename

    serialized = [r.to_dict() for r in data]

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(serialized, f, ensure_ascii=False, indent=2)

    return filepath, len(data)
