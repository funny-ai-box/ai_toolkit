# app/modules/base/knowledge/repositories/document_vector_repository.py
from typing import Optional, List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
import datetime

from app.modules.base.knowledge.models import DocumentVector # 相对导入
from app.core.utils.snowflake import generate_id

class DocumentVectorRepository:
    """文档向量 (关系数据库部分) 仓库"""
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_document_vector_async(self, document_vector: DocumentVector) -> int:
        """添加单个向量记录"""
        document_vector.id = generate_id()
        now = datetime.datetime.now()
        document_vector.create_date = now
        document_vector.last_modify_date = now
        self.db.add(document_vector)
        await self.db.flush()
        return document_vector.id

    async def add_document_vectors_async(self, document_vectors: List[DocumentVector]) -> bool:
        """批量添加向量记录"""
        if not document_vectors:
            return True
        now = datetime.datetime.now()
        for vector in document_vectors:
            vector.id = generate_id()
            vector.create_date = now
            vector.last_modify_date = now
        self.db.add_all(document_vectors)
        await self.db.flush()
        return True

    async def update_document_vector_async(self, document_vector: DocumentVector) -> bool:
        """更新向量记录 (不常用)"""
        if document_vector not in self.db and not self.db.is_modified(document_vector):
             existing = await self.db.get(DocumentVector, document_vector.id)
             if not existing: return False
             existing.chunk_index = document_vector.chunk_index
             existing.chunk_content = document_vector.chunk_content
             existing.vector_id = document_vector.vector_id
        # last_modify_date 会自动更新
        await self.db.flush()
        return True

    async def get_document_vectors_async(self, document_id: int) -> List[DocumentVector]:
        """获取指定文档的所有向量记录"""
        stmt = select(DocumentVector).where(
            DocumentVector.document_id == document_id
        ).order_by(DocumentVector.chunk_index.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_user_vectors_async(self, user_id: int) -> List[DocumentVector]:
        """获取用户的所有向量记录 (且 VectorId > 0?)"""
        stmt = select(DocumentVector).where(
            DocumentVector.user_id == user_id,
            DocumentVector.vector_id > 0
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_document_id_async(self, document_id: int) -> bool:
        """删除指定文档的所有向量记录"""
        stmt = delete(DocumentVector).where(DocumentVector.document_id == document_id)
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount > 0