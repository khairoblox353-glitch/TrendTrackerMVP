"""ORM models.

Importing this package registers every mapper, which `create_all` and the
relationship strings depend on.
"""

from app.models.article import Article, ProcessingStatus
from app.models.associations import ArticleTopic
from app.models.category import Category
from app.models.snapshot import TrendSnapshot, TrendStatus
from app.models.source import Source
from app.models.topic import Topic

__all__ = [
    "Article",
    "ArticleTopic",
    "Category",
    "ProcessingStatus",
    "Source",
    "Topic",
    "TrendSnapshot",
    "TrendStatus",
]
