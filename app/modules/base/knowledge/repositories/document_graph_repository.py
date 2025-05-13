# app/modules/base/knowledge/repositories/document_graph_repository.py
from typing import Optional, List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
import datetime

from app.modules.base.knowledge.models import DocumentGraph # 相对导入
from app.core.utils.snowflake import generate_id

class DocumentGraphRepository:
    """文档知识图谱仓库"""
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id_async(self, graph_id: int) -> Optional[DocumentGraph]:
        """按 ID 获取图谱"""
        stmt = select(DocumentGraph).where(DocumentGraph.id == graph_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_document_id_async(self, document_id: int) -> Optional[DocumentGraph]:
        """按文档 ID 获取图谱"""
        stmt = select(DocumentGraph).where(DocumentGraph.document_id == document_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_document_ids_async(self, document_ids: List[int]) -> List[DocumentGraph]:
        """按文档 ID 列表获取图谱"""
        if not document_ids: return []
        stmt = select(DocumentGraph).where(DocumentGraph.document_id.in_(document_ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_async(self, knowledge_graph: DocumentGraph) -> bool:
        """添加知识图谱"""
        knowledge_graph.id = generate_id()
        now = datetime.datetime.now()
        knowledge_graph.create_date = now
        knowledge_graph.last_modify_date = now
        self.db.add(knowledge_graph)
        await self.db.flush()
        return True

    async def update_async(self, knowledge_graph: DocumentGraph) -> bool:
        """更新知识图谱"""
        if knowledge_graph not in self.db and not self.db.is_modified(knowledge_graph):
             existing = await self.db.get(DocumentGraph, knowledge_graph.id)
             if not existing: return False
             existing.summary = knowledge_graph.summary
             existing.keywords = knowledge_graph.keywords
             existing.mind_map = knowledge_graph.mind_map
        # last_modify_date 会自动更新
        await self.db.flush()
        return True

    async def delete_async(self, graph_id: int) -> bool:
        """删除知识图谱"""
        stmt = delete(DocumentGraph).where(DocumentGraph.id == graph_id)
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount > 0

    async def delete_by_document_id_async(self, document_id: int) -> bool:
        """根据文档ID删除知识图谱"""
        stmt = delete(DocumentGraph).where(DocumentGraph.document_id == document_id)
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount > 0