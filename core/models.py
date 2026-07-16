from dataclasses import dataclass, field
from datetime import datetime
from math import log10
from typing import Optional
from urllib.parse import urlparse

from config import MAX_URL_LENGTH
from core.config import RATING_CONFIG
from core.enum import ResourceKind, ResourcePlatform, ResourceStatus, ResourceType
from core.exceptions import InvalidParamError, InvalidRatingError, UnknownClassCodeError
from core.utils import detect_platform


@dataclass
class Resource:
    title: str
    url: str

    id: Optional[int] = None
    description: Optional[str] = None
    resource_type: ResourceType = ResourceType.OTHER
    platform: ResourcePlatform = ResourcePlatform.OTHER
    kind: ResourceKind = ResourceKind.OTHER
    external_id: Optional[str] = None
    status: ResourceStatus = ResourceStatus.TO_TEACH
    tags: list[str] = field(default_factory=list)
    my_notes: Optional[str] = None
    my_rating: Optional[int] = None
    engagement: Optional[int] = None
    views: Optional[int] = None
    duration: Optional[int] = None  # Duration in minutes (always stored as minutes)
    published_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.title:
            raise InvalidParamError("title", str(self.title), "Название обязательно")
        if not self.url:
            raise InvalidParamError("url", str(self.url), "URL обязателен")
        if not self._is_valid_url(self.url):
            raise InvalidParamError("url", self.url, f"Некорректный URL: {self.url}")
        if isinstance(self.platform, str):
            try:
                self.platform = ResourcePlatform.from_code(self.platform)
            except UnknownClassCodeError:
                self.platform = ResourcePlatform.OTHER

        if not isinstance(self.platform, ResourcePlatform):
            raise TypeError(
                f"platform должна быть ResourcePlatform — принято: {type(self.platform).__name__}"
            )

        if (
            self.my_rating is not None
            and not 1 <= self.my_rating <= RATING_CONFIG.max_personal_rating
        ):
            raise InvalidRatingError(self.my_rating, RATING_CONFIG.max_personal_rating)

        if self.duration is not None:
            self._validate_positive(
                self.duration,
                "duration",
                f"Длительность не может быть отрицательной: {self.duration}",
            )

        if self.views is not None:
            self._validate_positive(
                self.views,
                "views",
                f"Количество просмотров не может быть отрицательным: {self.views}",
            )

        if self.engagement is not None:
            self._validate_positive(
                self.engagement,
                "engagement",
                f"Вовлеченность(лайки, комментарии и тд) не может быть отрицательной: {self.engagement}",
            )

        if self.platform == ResourcePlatform.OTHER:
            detected = detect_platform(self.url)
            if detected in ("youtube", "habr"):
                self.platform = ResourcePlatform.from_code(detected)

        if self.kind == ResourceKind.OTHER:
            if self.platform == ResourcePlatform.YOUTUBE:
                self.kind = ResourceKind.VIDEO
            elif self.platform == ResourcePlatform.HABR:
                self.kind = ResourceKind.ARTICLE

    def update_stats(
        self, views: Optional[int] = None, engagement: Optional[int] = None
    ):
        if views is not None:
            self._validate_positive(
                views,
                "views",
                f"Количество просмотров не может быть отрицательным: {views}",
            )
            self.views = views
        if engagement is not None:
            self._validate_positive(
                engagement,
                "engagement",
                f"Вовлеченность(лайки, комментарии и тд) не может быть отрицательной: {engagement}",
            )
            self.engagement = engagement

    def update_type(self, new_type: ResourceType):
        self.resource_type = new_type

    def update_my_notes(self, my_note: str):
        self.my_notes = my_note

    def update_my_rating(self, rating: int):
        if not 1 <= rating <= RATING_CONFIG.max_personal_rating:
            raise InvalidRatingError(rating, RATING_CONFIG.max_personal_rating)
        self.my_rating = rating

    def update_status(self, status: ResourceStatus):
        if status == ResourceStatus.TO_TEACH:
            self.reset()
        elif status == ResourceStatus.TEACHED:
            self.complete()
        else:
            self.status = status

    def complete(self, rating: Optional[int] = None):
        self.status = ResourceStatus.TEACHED
        self.completed_at = datetime.now()
        if rating is not None:
            self.update_my_rating(rating)

    def master(self):
        self.status = ResourceStatus.MASTERED
        if not self.completed_at:
            self.completed_at = datetime.now()

    def archive(self):
        self.status = ResourceStatus.ARCHIVED

    def reset(self, reset_rating: bool = True):
        self.status = ResourceStatus.TO_TEACH
        self.completed_at = None
        if reset_rating:
            self.my_rating = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "resource_type": self.resource_type.code,
            "platform": self.platform.code,
            "kind": self.kind.code,
            "external_id": self.external_id,
            "url": self.url,
            "status": self.status.code,
            "tags": self.tags,
            "my_notes": self.my_notes,
            "my_rating": self.my_rating,
            "engagement": self.engagement,
            "views": self.views,
            "duration": self.duration,
            "published_at": self.published_at.isoformat()
            if self.published_at
            else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "created_at": self.created_at.isoformat(),
            "rating": self.rating,
        }

    def _calculate_rating(
        self,
        view_smoothing: int,
        engagement_smoothing: int,
        view_norm: float,
        reach_multiplier: float,
        engagement_rate_multiplier: float,
        engagement_multiplier: float,
    ) -> float:
        """
        Formula:
        - Reach score: log10(1 + views/norm) * reach_multiplier
        - Engagement rate: engagement / views
        - Engagement score: log10(1 + rate * rate_multiplier) * engagement_multiplier
        - Final result: min(100, reach + engagement) with personal rating blending
        """
        cfg = RATING_CONFIG

        v = self.views or 1
        e = self.engagement or 0

        smoothed_v = v + view_smoothing
        smoothed_e = e + engagement_smoothing

        reach_raw = log10(1.0 + smoothed_v / view_norm)
        reach_score = min(cfg.max_score / 2, reach_raw * reach_multiplier)

        capped_e = min(smoothed_e, float(smoothed_v))
        engagement_rate = capped_e / smoothed_v

        if engagement_rate > 0:
            eng_raw = log10(1.0 + engagement_rate * engagement_rate_multiplier)
        else:
            eng_raw = 0.0

        eng_score = min(cfg.max_score / 2, eng_raw * engagement_multiplier)

        platform_score = reach_score + eng_score

        if self.my_rating is not None:
            personal_score = self._personal_rating_score()
            return round(
                cfg.platform_weight * platform_score
                + cfg.personal_weight * personal_score,
                2,
            )

        return round(min(cfg.max_score, platform_score), 2)

    def _personal_rating_score(self) -> float:
        if self.my_rating is None:
            return 0.0
        return (
            self.my_rating / RATING_CONFIG.max_personal_rating
        ) * RATING_CONFIG.max_score

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            if len(url) > MAX_URL_LENGTH:
                return False
            return True
        except Exception:
            return False

    @staticmethod
    def _validate_positive(value: int, param: str, error_msg: str) -> None:
        if value < 0:
            raise InvalidParamError(param, str(value), error_msg)

    @property
    def is_completed(self) -> bool:
        return self.status in (ResourceStatus.TEACHED, ResourceStatus.MASTERED)

    @property
    def is_active(self) -> bool:
        return self.status != ResourceStatus.ARCHIVED

    @property
    def rating(self) -> float:
        cfg = RATING_CONFIG

        if not self.views or self.views <= 0:
            return self._personal_rating_score()

        if self.platform == ResourcePlatform.YOUTUBE:
            return self._calculate_rating(
                view_smoothing=cfg.view_smoothing,
                engagement_smoothing=cfg.engagement_smoothing,
                view_norm=cfg.video_view_norm,
                reach_multiplier=cfg.video_reach_multiplier,
                engagement_rate_multiplier=cfg.video_engagement_rate_multiplier,
                engagement_multiplier=cfg.video_engagement_multiplier,
            )
        elif self.platform == ResourcePlatform.HABR:
            return self._calculate_rating(
                view_smoothing=cfg.habr_view_smoothing,
                engagement_smoothing=cfg.habr_engagement_smoothing,
                view_norm=cfg.habr_view_norm,
                reach_multiplier=cfg.habr_reach_multiplier,
                engagement_rate_multiplier=cfg.habr_engagement_rate_multiplier,
                engagement_multiplier=cfg.habr_engagement_multiplier,
            )

        return self._personal_rating_score()

    @property
    def duration_display(self) -> str:
        if self.duration is None:
            return "Не указано"

        hours = self.duration // 60
        minutes = self.duration % 60

        if hours > 0:
            return f"{hours}ч {minutes}мин"
        return f"{minutes}мин"

    @classmethod
    def from_dict(cls, data: dict) -> "Resource":
        return cls(
            id=data.get("id"),
            title=data["title"],
            description=data.get("description"),
            resource_type=ResourceType.from_code(data.get("resource_type", "others")),
            platform=ResourcePlatform.from_code(data.get("platform", "others")),
            kind=ResourceKind.from_code(data.get("kind", "others")),
            external_id=data.get("external_id"),
            url=data["url"],
            status=ResourceStatus.from_code(data.get("status", "to_teach")),
            tags=data.get("tags", []),
            my_notes=data.get("my_notes") if data.get("my_notes") else None,
            my_rating=data.get("my_rating"),
            engagement=data.get("engagement"),
            views=data.get("views"),
            duration=data.get("duration"),
            published_at=datetime.fromisoformat(data["published_at"])
            if data.get("published_at")
            else None,
            completed_at=datetime.fromisoformat(data["completed_at"])
            if data.get("completed_at")
            else None,
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else datetime.now(),
        )

    def format_detailed(self) -> str:
        parts = [
            self.title,
            f"[{self.resource_type.label}]",
            f"- {self.status.label}",
        ]
        if self.my_rating is not None:
            parts.append(f"(Ваша оценка: {self.my_rating}/5)")
        return " ".join(parts)

    def __str__(self) -> str:
        return f"{self.title} [{self.resource_type.label}]"

    # def __repr__(self) -> str:
    #     return f"Resource(id={self.id}, title='{self.title}', platform={self.platform.code}, status={self.status.code})"

    def __repr__(self) -> str:
        fields = {k: v for k, v in self.__dict__.items() if k != "args"}
        parts = [f"{k}={v!r}" for k, v in fields.items()]
        return f"Resource({', '.join(parts)})"
