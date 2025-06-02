from enum import Enum


class PostStatus(Enum):
    PENDING = "pending"
    STARTED = "started"
    PROCESSED = "processed"
    POSTED = "posted"
    ERROR = "error"

    @classmethod
    def values(cls):
        return [status.value for status in cls]

    @classmethod
    def choices(cls):
        return [(status.name, status.value) for status in cls]


class PostType(Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    ARTICLE = "article"

    @classmethod
    def values(cls):
        return [postType.value for postType in cls]

    @classmethod
    def choices(cls):
        return [(postType.name, postType.value) for postType in cls]


class Platforms(Enum):
    LINKEDIN = "linkedin"
    X = "x"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"

    @classmethod
    def values(cls):
        return [platform.value for platform in cls]

    @classmethod
    def choices(cls):
        return [(platform.name, platform.value) for platform in cls]
