from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import datetime

from app.core.utils.snowflake import generate_id
from app.modules.tools.dataanalysis.models import ImportLog

class ImportLogRepository:
    """导入日志仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化导入日志仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def add_async(self, import_log: ImportLog) -> ImportLog:
        """
        添加导入日志
        
        Args:
            import_log: 导入日志实体
        
        Returns:
            添加后的实体
        """
        # 使用雪花ID
        import_log.id = generate_id()
        
        # 设置创建和修改时间
        now = datetime.datetime.now()
        import_log.create_date = now
        import_log.last_modify_date = now
        
        # 插入数据
        self.db.add(import_log)
        await self.db.flush()
        await self.db.commit()
        
        return import_log
    
    async def update_async(self, import_log: ImportLog) -> ImportLog:
        """
        更新导入日志
        
        Args:
            import_log: 导入日志实体
        
        Returns:
            更新后的实体
        """
        # 更新最后修改时间
        import_log.last_modify_date = datetime.datetime.now()
        
        # 更新数据
        self.db.add(import_log)
        await self.db.flush()
        await self.db.commit()
        
        return import_log
    
    async def get_by_id_async(self, id: int) -> Optional[ImportLog]:
        """
        获取导入日志
        
        Args:
            id: 导入日志ID
        
        Returns:
            导入日志实体
        """
        result = await self.db.execute(
            select(ImportLog).filter(ImportLog.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_upload_file_id_async(self, upload_file_id: int) -> Optional[ImportLog]:
        """
        获取上传文件的导入日志
        
        Args:
            upload_file_id: 上传文件ID
        
        Returns:
            导入日志实体
        """
        result = await self.db.execute(
            select(ImportLog).filter(ImportLog.upload_file_id == upload_file_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_table_id_async(self, table_id: int) -> Optional[ImportLog]:
        """
        获取数据表的导入日志
        
        Args:
            table_id: 数据表ID
        
        Returns:
            导入日志实体
        """
        result = await self.db.execute(
            select(ImportLog).filter(ImportLog.table_id == table_id)
        )
        return result.scalar_one_or_none()