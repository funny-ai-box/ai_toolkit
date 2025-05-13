# app/modules/base/knowledge/repositories/__init__.py
from .document_repository import DocumentRepository
from .document_content_repository import DocumentContentRepository
from .document_graph_repository import DocumentGraphRepository
from .document_log_repository import DocumentLogRepository
from .document_vector_repository import DocumentVectorRepository

__all__ = [
    "DocumentRepository",
    "DocumentContentRepository",
    "DocumentGraphRepository",
    "DocumentLogRepository",
    "DocumentVectorRepository",
]