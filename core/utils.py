import re
from urllib.parse import urlparse


def is_valid_domain(domain: str) -> bool:
    if not domain or " " in domain:
        return False

    if any(ord(c) > 127 for c in domain):
        return "." in domain

    pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)+$"
    return bool(re.match(pattern, domain))


def detect_platform(url: str) -> str:
    domain = urlparse(url).netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    if not domain:
        return "unknown"

    if any(yt in domain for yt in ["youtube.com", "youtu.be"]):
        return "youtube"
    elif any(h in domain for h in ["habr.com", "habr.ru"]):
        return "habr"
    elif is_valid_domain(domain):
        return domain
    else:
        return "unknown"


def extract_external_id(url: str, platform: str) -> str | None:
    """
    Extract external ID from URL based on platform.

    Supports formats:
        YouTube:
            https://www.youtube.com/watch?v=dQw4w9WgXcQ
            https://youtu.be/dQw4w9WgXcQ
            https://www.youtube.com/embed/dQw4w9WgXcQ
            https://www.youtube.com/shorts/dQw4w9WgXcQ
        Habr:
            https://habr.com/ru/articles/123456/
            https://habr.com/ru/companies/company_name/articles/123456/
            https://habr.com/ru/news/123456/
            https://habr.com/ru/posts/123456/
            https://habr.com/ru/sandbox/123456/

    Args:
        url: Full URL to parse.
        platform: Platform name ('youtube' or 'habr').

    Returns:
        External ID string if found, None otherwise.
    """
    if platform == "youtube":
        match = re.search(
            r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([a-zA-Z0-9_-]{11})", url
        )
        if match:
            return match.group(1)

    elif platform == "habr":
        match = re.search(r"/(?:articles|news|posts|sandbox)/(\d+)", url)
        if match:
            return match.group(1)

    return None
