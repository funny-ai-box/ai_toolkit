# app/modules/base/knowledge/repositories/document_repository.py
from typing import Optional, List, Tuple
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
import datetime

from app.modules.base.knowledge.models import Document # 相对导入
from app.modules.base.knowledge.dtos import DocumentStatus # 相对导入
from app.core.dtos import DocumentAppType # 从 core 导入
from app.core.utils.snowflake import generate_id

class DocumentRepository:
    """知识库文档仓库实现"""
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_document_async(self, document: Document) -> int:
        """添加文档"""
        document.id = generate_id()
        now = datetime.datetime.now()
        document.create_date = now
        document.last_modify_date = now
        self.db.add(document)
        await self.db.flush()
        return document.id

    async def update_document_async(self, document: Document) -> bool:
        """更新文档"""
        if document not in self.db and not self.db.is_modified(document):
             existing = await self.db.get(Document, document.id)
             if not existing: return False
             for col in document.__table__.columns:
                 if col.name not in ['id', 'CreateDate']:
                     setattr(existing, col.key, getattr(document, col.key))
        # last_modify_date 会自动更新
        await self.db.flush()
        return True

    async def update_status_async(self, doc_id: int, status: DocumentStatus, message: str = "", content_length: int = 0) -> bool:
        """更新文档解析状态"""
        values_to_update = {
            "status": status.value,
            "last_modify_date": func.now()
        }
        if message:
            values_to_update["process_message"] = message
        if content_length > 0:
             values_to_update["content_length"] = content_length

        stmt = update(Document).where(Document.id == doc_id).values(**values_to_update)
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount > 0

    async def update_vector_status_async(self, doc_id: int, vector_status: DocumentStatus, message: str = "") -> bool:
        """更新文档向量化状态"""
        values_to_update = {
            "vector_status": vector_status,
            "last_modify_date": func.now()
        }
        if message:
            values_to_update["vector_message"] = message
        stmt = update(Document).where(Document.id == doc_id).values(**values_to_update)
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount > 0

    async def update_graph_status_async(self, doc_id: int, graph_status: DocumentStatus, message: str = "") -> bool:
        """更新文档图谱化状态"""
        values_to_update = {
            "graph_status": graph_status,
            "last_modify_date": func.now()
        }
        if message:
            values_to_update["graph_message"] = message
        stmt = update(Document).where(Document.id == doc_id).values(**values_to_update)
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount > 0

    async def get_document_async(self, doc_id: int) -> Optional[Document]:
        """根据 ID 获取文档"""
        stmt = select(Document).where(Document.id == doc_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_documents_async(self, doc_ids: List[int]) -> List[Document]:
        """根据 ID 列表获取文档"""
        if not doc_ids: return []
        stmt = select(Document).where(Document.id.in_(doc_ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ids_async(self, doc_ids: List[int]) -> List[Document]:
        """根据 ID 列表获取文档 (同 get_documents_async)"""
        return await self.get_documents_async(doc_ids)

    async def delete_async(self, doc_id: int) -> bool:
        """根据 ID 删除文档"""
        stmt = delete(Document).where(Document.id == doc_id)
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount > 0

    async def get_user_documents_async(self, user_id: int, app_type: DocumentAppType, page_index: int = 1, page_size: int = 20) -> Tuple[List[Document], int]:
        """分页获取用户指定应用类型的文档"""
        offset = (page_index - 1) * page_size

        count_stmt = select(func.count(Document.id)).where( # 使用 count(主键) 可能更精确
            Document.user_id == user_id,
            Document.app_type == int(app_type)
        )
        total_count_result = await self.db.execute(count_stmt)
        total_count = total_count_result.scalar_one() or 0

        if total_count == 0:
            return [], 0

        data_stmt = select(Document).where(
            Document.user_id == user_id,
            Document.app_type == int(app_type)
        ).order_by(Document.id.desc()).offset(offset).limit(page_size)

        data_result = await self.db.execute(data_stmt)
        items = list(data_result.scalars().all())

        return items, total_count

    async def get_pending_documents_async(self, limit: int = 10) -> List[Document]:
        """获取待处理文档列表"""
        stmt = select(Document).where(
            Document.status == DocumentStatus.PENDING
        ).order_by(Document.create_date.asc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_vectorization_documents_async(self, limit: int = 10) -> List[Document]:
        """获取待向量化文档列表"""
        stmt = select(Document).where(
            Document.status == DocumentStatus.COMPLETED,
            Document.is_need_vector == True, # 显式比较布尔值
            Document.vector_status == DocumentStatus.PENDING
        ).order_by(Document.create_date.asc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_graph_documents_async(self, limit: int = 10) -> List[Document]:
        """获取待图谱化文档列表"""
        stmt = select(Document).where(
            Document.status == DocumentStatus.COMPLETED,
            Document.is_need_graph == True, # 显式比较布尔值
            Document.graph_status == DocumentStatus.PENDING
        ).order_by(Document.create_date.asc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())