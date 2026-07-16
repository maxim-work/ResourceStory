import json

from core.models import Resource


def parse_data(filepath: str) -> list[Resource]:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("JSON должен содержать список ресурсов")

    resources = []
    for i, item in enumerate(data):
        try:
            resources.append(Resource.from_dict(item))
        except Exception as e:
            raise ValueError(f"Ошибка в ресурсе #{i}: {e}") from e

    return resources
