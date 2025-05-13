# app/modules/base/knowledge/repositories/document_content_repository.py
from typing import Optional, List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
import datetime

from app.modules.base.knowledge.models import DocumentContent # 相对导入

class DocumentContentRepository:
    """文档内容仓库"""
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_document_content_async(self, document_content: DocumentContent) -> bool:
        """添加文档内容"""
        if not document_content.id:
             raise ValueError("DocumentContent ID (必须与 Document ID 相同) 不能为空")
        now = datetime.datetime.now()
        document_content.create_date = now
        document_content.last_modify_date = now
        self.db.add(document_content)
        await self.db.flush()
        return True

    async def get_document_content_async(self, document_id: int) -> Optional[DocumentContent]:
        """获取文档内容"""
        stmt = select(DocumentContent).where(DocumentContent.document_id == document_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_document_contents_async(self, document_ids: List[int]) -> List[DocumentContent]:
        """批量获取文档内容"""
        if not document_ids: return []
        stmt = select(DocumentContent).where(DocumentContent.document_id.in_(document_ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_document_content_async(self, document_id: int) -> bool:
        """删除文档内容"""
        stmt = delete(DocumentContent).where(DocumentContent.document_id == document_id)
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount > 0