"""
职位仓储实现

提供职位实体的数据访问操作，包括添加、查询、更新和删除等功能。
"""
import datetime
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.utils.snowflake import generate_id
from app.modules.tools.interview.models import JobPosition
from app.modules.tools.interview.enums import JobPositionQuestionStatusType


class JobPositionRepository:
    """职位仓储"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化职位仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def add_async(self, position: JobPosition) -> JobPosition:
        """
        添加职位
        
        Args:
            position: 职位实体
            
        Returns:
            成功添加的职位实体
        """
        position.id = generate_id()
        now = datetime.datetime.now()
        position.create_date = now
        position.last_modify_date = now
        
        self.db.add(position)
        await self.db.flush()
        await self.db.commit()
        return position
    
    async def batch_add_async(self, positions: List[JobPosition]) -> List[JobPosition]:
        """
        批量添加职位
        
        Args:
            positions: 职位实体列表
            
        Returns:
            成功添加的职位实体列表
        """
        if not positions:
            return []
        
        now = datetime.datetime.now()
        for position in positions:
            position.id = generate_id()
            position.create_date = now
            position.last_modify_date = now
            self.db.add(position)
        
        await self.db.flush()
        await self.db.commit()
        return positions
    
    async def get_by_id_async(self, id: int) -> Optional[JobPosition]:
        """
        获取指定ID的职位
        
        Args:
            id: 职位ID
            
        Returns:
            职位实体
        """
        query = select(JobPosition).where(JobPosition.id == id)
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def get_by_scenario_id_async(self, scenario_id: int) -> List[JobPosition]:
        """
        获取指定场景的所有职位
        
        Args:
            scenario_id: 场景ID
            
        Returns:
            职位实体列表
        """
        query = select(JobPosition).where(JobPosition.scenario_id == scenario_id).order_by(JobPosition.level)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_async(self, position: JobPosition) -> bool:
        """
        更新职位
        
        Args:
            position: 职位实体
            
        Returns:
            更新结果
        """
        position.last_modify_date = datetime.datetime.now()
        await self.db.flush()
        await self.db.commit()
        return True
    
    async def update_status_async(
        self, 
        id: int, 
        status: JobPositionQuestionStatusType,
        error_message: Optional[str] = None
    ) -> bool:
        """
        更新职位问题生成的状态
        
        Args:
            id: ID
            status: 状态
            error_message: 日志
            
        Returns:
            操作结果
        """
        stmt = (
            update(JobPosition)
            .where(JobPosition.id == id)
            .values(
                question_status=status,
                error_message=error_message,
                last_modify_date=datetime.datetime.now()
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
    
    async def delete_async(self, id: int) -> bool:
        """
        删除职位
        
        Args:
            id: 职位ID
            
        Returns:
            删除结果
        """
        stmt = (
            update(JobPosition)
            .where(JobPosition.id == id)
            .values(is_deleted=True)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
    
    async def delete_by_scenario_id_async(self, scenario_id: int) -> bool:
        """
        删除场景的所有职位
        
        Args:
            scenario_id: 场景ID
            
        Returns:
            删除结果
        """
        stmt = (
            update(JobPosition)
            .where(JobPosition.scenario_id == scenario_id)
            .values(is_deleted=True)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0