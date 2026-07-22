from datetime import datetime
from math import log10
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, ValidationInfo, field_serializer, field_validator

from config import MAX_URL_LENGTH
from core.config import RATING_CONFIG
from core.enum import ResourceKind, ResourcePlatform, ResourceStatus, ResourceType
from core.exceptions import InvalidParamError, InvalidRatingError, UnknownClassCodeError
from core.utils import detect_platform


class Resource(BaseModel):
    model_config = {"frozen": False}

    id: Optional[int] = None
    user_id: Optional[int] = None
    title: str
    url: str
    description: Optional[str] = None
    resource_type: ResourceType = ResourceType.OTHER
    platform: ResourcePlatform = ResourcePlatform.OTHER
    kind: ResourceKind = ResourceKind.OTHER
    external_id: Optional[str] = None
    status: ResourceStatus = ResourceStatus.TO_TEACH
    tags: list[str] = Field(default_factory=list)
    my_notes: Optional[str] = None
    my_rating: Optional[int] = None
    engagement: Optional[int] = None
    views: Optional[int] = None
    duration: Optional[int] = None  # Duration in minutes (always stored as minutes)
    published_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, v: str) -> str:
        if not v:
            raise InvalidParamError("title", str(v), "Название обязательно")
        return v

    @field_validator("url")
    @classmethod
    def url_must_be_valid(cls, v: str) -> str:
        if not v:
            raise InvalidParamError("url", str(v), "URL обязателен")
        if not cls._is_valid_url(v):
            raise InvalidParamError("url", v, f"Некорректный URL: {v}")
        return v

    @field_validator("resource_type", mode="before")
    @classmethod
    def coerce_resource_type(cls, v) -> ResourceType:
        if isinstance(v, str):
            try:
                return ResourceType.from_code(v)
            except UnknownClassCodeError:
                return ResourceType.OTHER
        if not isinstance(v, ResourceType):
            raise TypeError(
                f"resource_type должен быть ResourceType — принято: {type(v).__name__}"
            )
        return v

    @field_validator("platform", mode="before")
    @classmethod
    def coerce_and_detect_platform(cls, v, info: ValidationInfo) -> ResourcePlatform:
        if isinstance(v, str):
            try:
                v = ResourcePlatform.from_code(v)
            except UnknownClassCodeError:
                v = ResourcePlatform.OTHER

        if not isinstance(v, ResourcePlatform):
            raise TypeError(
                f"platform должна быть ResourcePlatform — принято: {type(v).__name__}"
            )

        if v == ResourcePlatform.OTHER:
            url = info.data.get("url") if info.data else None
            if url:
                detected = detect_platform(url)
                if detected in ("youtube", "habr"):
                    return ResourcePlatform.from_code(detected)

        return v

    @field_validator("kind", mode="before")
    @classmethod
    def coerce_and_detect_kind(cls, v, info: ValidationInfo) -> ResourceKind:
        if isinstance(v, str):
            try:
                v = ResourceKind.from_code(v)
            except UnknownClassCodeError:
                v = ResourceKind.OTHER

        if not isinstance(v, ResourceKind):
            raise TypeError(
                f"kind должен быть ResourceKind — принято: {type(v).__name__}"
            )

        if v == ResourceKind.OTHER:
            platform = info.data.get("platform") if info.data else None
            if platform == ResourcePlatform.YOUTUBE:
                return ResourceKind.VIDEO
            elif platform == ResourcePlatform.HABR:
                return ResourceKind.ARTICLE

        return v

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, v) -> ResourceStatus:
        if isinstance(v, str):
            try:
                return ResourceStatus.from_code(v)
            except UnknownClassCodeError:
                return ResourceStatus.TO_TEACH
        if not isinstance(v, ResourceStatus):
            raise TypeError(
                f"status должна быть ResourceStatus — принято: {type(v).__name__}"
            )
        return v

    @field_validator("my_rating")
    @classmethod
    def validate_my_rating(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 1 <= v <= RATING_CONFIG.max_personal_rating:
            raise InvalidRatingError(v, RATING_CONFIG.max_personal_rating)
        return v

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            cls._validate_positive(
                v, "duration", f"Длительность не может быть отрицательной: {v}"
            )
        return v

    @field_validator("views")
    @classmethod
    def validate_views(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            cls._validate_positive(
                v, "views", f"Количество просмотров не может быть отрицательным: {v}"
            )
        return v

    @field_validator("engagement")
    @classmethod
    def validate_engagement(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            cls._validate_positive(
                v,
                "engagement",
                f"Вовлеченность(лайки, комментарии и тд) не может быть отрицательной: {v}",
            )
        return v

    @field_serializer("resource_type", "platform", "kind", "status")
    def serialize_enum(self, value):
        return value.code

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

    def update_kind(self, new_kind: ResourceKind):
        self.kind = new_kind

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

    def __repr__(self) -> str:
        fields = {k: v for k, v in self.__dict__.items() if k != "args"}
        parts = [f"{k}={v!r}" for k, v in fields.items()]
        return f"Resource({', '.join(parts)})"

    def _calculate_rating(
        self,
        view_smoothing: int,
        engagement_smoothing: int,
        view_norm: float,
        reach_multiplier: float,
        engagement_rate_multiplier: float,
        engagement_multiplier: float,
    ) -> float:
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
