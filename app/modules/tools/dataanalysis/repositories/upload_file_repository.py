from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import datetime

from app.core.utils.snowflake import generate_id
from app.modules.tools.dataanalysis.models import UploadFile

class UploadFileRepository:
    """文件上传仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化文件上传仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def add_async(self, upload_file: UploadFile) -> UploadFile:
        """
        添加文件上传记录
        
        Args:
            upload_file: 文件上传实体
        
        Returns:
            添加后的实体
        """
        # 使用雪花ID
        upload_file.id = generate_id()
        
        # 设置创建和修改时间
        now = datetime.datetime.now()
        upload_file.create_date = now
        upload_file.last_modify_date = now
        
        # 插入数据
        self.db.add(upload_file)
        await self.db.flush()
        
        return upload_file
    
    async def update_async(self, upload_file: UploadFile) -> UploadFile:
        """
        更新文件上传记录
        
        Args:
            upload_file: 文件上传实体
        
        Returns:
            更新后的实体
        """
        # 更新最后修改时间
        upload_file.last_modify_date = datetime.datetime.now()
        
        # 更新数据
        self.db.add(upload_file)
        await self.db.flush()
        
        return upload_file
    
    async def get_by_id_async(self, id: int) -> Optional[UploadFile]:
        """
        获取文件上传记录
        
        Args:
            id: 文件上传ID
        
        Returns:
            文件上传实体
        """
        result = await self.db.execute(
            select(UploadFile).filter(UploadFile.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_files_async(self, user_id: int) -> List[UploadFile]:
        """
        获取用户的所有文件上传记录
        
        Args:
            user_id: 用户ID
        
        Returns:
            文件上传实体列表
        """
        result = await self.db.execute(
            select(UploadFile)
            .filter(UploadFile.user_id == user_id)
            .order_by(UploadFile.create_date.desc())
        )
        return list(result.scalars().all())
    
    async def delete_async(self, id: int) -> bool:
        """
        删除文件上传记录
        
        Args:
            id: 文件上传ID
        
        Returns:
            是否成功
        """
        upload_file = await self.get_by_id_async(id)
        if upload_file:
            await self.db.delete(upload_file)
            await self.db.flush()
            return True
        return False
    
    async def get_pending_files_async(self, limit: int = 10) -> List[UploadFile]:
        """
        获取待处理的文档
        
        Args:
            limit: 数量限制
        
        Returns:
            文档实体列表
        """
        result = await self.db.execute(
            select(UploadFile)
            .filter(UploadFile.status == 0)
            .order_by(UploadFile.create_date)
            .limit(limit)
        )
        return list(result.scalars().all())
