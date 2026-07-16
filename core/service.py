from datetime import datetime
from typing import Optional

from core.exceptions import InvalidUrlParamError, UnknownClassCodeError
from core.models import (
    Resource,
    ResourceKind,
    ResourcePlatform,
    ResourceStatus,
    ResourceType,
)
from core.parse_info import (
    fetch_page_info,
    fetch_youtube_video_info,
)
from core.utils import (
    detect_platform,
    extract_external_id,
)


def create_resource(
    url: str,
    resource_type: ResourceType = ResourceType.OTHER,
    kind: Optional[ResourceKind] = None,
    user_tags: Optional[list[str]] = None,
    youtube_api_key: Optional[str] = None,
    proxy: Optional[str] = None,
    proxy_type: str = "socks5",
) -> Resource:
    info = None
    external_id = None

    platform = detect_platform(url)

    if platform == "unknown":
        raise InvalidUrlParamError(
            "platform", url, f"Не удалось определить платформу для url: {url}"
        )

    if platform in ("youtube", "habr"):
        external_id = extract_external_id(url, platform)

        if not external_id:
            raise InvalidUrlParamError(
                "external_id", url, f"Не смогли выделить external id из url({url})"
            )

    if (
        platform == "youtube"
        and youtube_api_key is not None
        and external_id is not None
    ):
        info = fetch_youtube_video_info(external_id, youtube_api_key, proxy, proxy_type)
        kind = kind or ResourceKind.VIDEO
    elif platform == "habr":
        info = fetch_page_info(url, platform="habr", proxy=proxy, proxy_type=proxy_type)
        kind = kind or ResourceKind.ARTICLE
    else:
        info = fetch_page_info(url, proxy=proxy, proxy_type=proxy_type)
        kind = kind or ResourceKind.SITE

    if not info:
        raise InvalidUrlParamError(
            "info", url, f"Не получилось получить информацию по url({url})"
        )

    try:
        platform_enum = ResourcePlatform.from_code(platform)
    except UnknownClassCodeError:
        platform_enum = ResourcePlatform.OTHER

    return Resource(
        title=info["title"],
        description=info["description"],
        platform=platform_enum,
        kind=kind,
        external_id=external_id,
        url=url,
        resource_type=resource_type,
        tags=user_tags or info["tags"],
        engagement=info["engagement"],
        views=info["views"],
        duration=info["duration"],
        published_at=info["published_at"],
    )


def edit_resource(
    resource: Resource,
    resource_type: Optional[ResourceType] = None,
    status: Optional[ResourceStatus] = None,
    my_notes: Optional[str] = None,
    my_rating: Optional[int] = None,
    completed_at: Optional[datetime] = None,
) -> Resource:
    if resource_type is not None:
        resource.update_type(resource_type)
    if status is not None:
        resource.update_status(status)
    if my_notes is not None and my_notes:
        resource.update_my_notes(my_notes)
    if my_rating is not None:
        resource.update_my_rating(my_rating)
    if completed_at is not None and resource.status != ResourceStatus.TO_TEACH:
        resource.completed_at = completed_at
    return resource
