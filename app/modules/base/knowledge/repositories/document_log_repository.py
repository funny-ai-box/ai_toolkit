# app/modules/base/knowledge/repositories/document_log_repository.py
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import datetime

from app.modules.base.knowledge.models import DocumentLog # 相对导入
from app.modules.base.knowledge.dtos import DocumentLogType # 相对导入
from app.core.utils.snowflake import generate_id

class DocumentLogRepository:
    """文档日志仓库"""
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_document_log_async(self, document_log: DocumentLog) -> int:
        """添加文档日志"""
        document_log.id = generate_id()
        now = datetime.datetime.now()
        document_log.create_date = now
        document_log.last_modify_date = now
        self.db.add(document_log)
        await self.db.flush()
        return document_log.id

    async def get_document_logs_async(self, document_id: int, log_type: Optional[DocumentLogType] = None) -> List[DocumentLog]:
        """获取文档日志"""
        stmt = select(DocumentLog).where(DocumentLog.document_id == document_id)
        if log_type is not None:
            stmt = stmt.where(DocumentLog.log_type == log_type)
        stmt = stmt.order_by(DocumentLog.id.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())