"""
面试场景内容项仓储实现

提供面试场景内容项实体的数据访问操作，包括添加、查询、更新和删除等功能。
"""
import datetime
from typing import List, Optional

from sqlalchemy import select, update, or_
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.utils.snowflake import generate_id
from app.modules.tools.interview.models import InterviewScenarioContent


class InterviewScenarioContentRepository:
    """面试场景内容项仓储"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化面试场景内容项仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def get_by_id_async(self, id: int) -> Optional[InterviewScenarioContent]:
        """
        获取场景内容项
        
        Args:
            id: 内容项ID
            
        Returns:
            内容项实体
        """
        query = select(InterviewScenarioContent).where(InterviewScenarioContent.id == id)
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def get_by_scenario_id_async(self, scenario_id: int) -> List[InterviewScenarioContent]:
        """
        获取场景的所有内容项
        
        Args:
            scenario_id: 场景ID
            
        Returns:
            内容项实体列表
        """
        query = select(InterviewScenarioContent).where(InterviewScenarioContent.scenario_id == scenario_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_by_scenario_ids_async(self, scenario_ids: List[int]) -> List[InterviewScenarioContent]:
        """
        获取场景的所有内容项
        
        Args:
            scenario_ids: 场景ID列表
            
        Returns:
            内容项实体列表
        """
        if not scenario_ids:
            return []
        
        query = select(InterviewScenarioContent).where(InterviewScenarioContent.scenario_id.in_(scenario_ids))
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def add_async(self, content_item: InterviewScenarioContent) -> int:
        """
        新增内容项
        
        Args:
            content_item: 内容项实体
            
        Returns:
            内容项ID
        """
        content_item.id = generate_id()
        now = datetime.datetime.now()
        content_item.create_date = now
        content_item.last_modify_date = now
        
        self.db.add(content_item)
        await self.db.flush()
        await self.db.commit()
        return content_item.id
    
    async def update_async(self, content_item: InterviewScenarioContent) -> bool:
        """
        更新内容项
        
        Args:
            content_item: 内容项实体
            
        Returns:
            操作结果
        """
        content_item.last_modify_date = datetime.datetime.now()
        await self.db.flush()
        await self.db.commit()
        return True
    
    async def delete_by_scenario_id_async(self, scenario_id: int) -> bool:
        """
        删除场景的所有内容项
        
        Args:
            scenario_id: 场景ID
            
        Returns:
            操作结果
        """
        stmt = (
            update(InterviewScenarioContent)
            .where(InterviewScenarioContent.scenario_id == scenario_id)
            .values(is_deleted=True)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
    
    async def delete_async(self, id: int) -> bool:
        """
        删除内容项
        
        Args:
            id: 内容项ID
            
        Returns:
            操作结果
        """
        stmt = (
            update(InterviewScenarioContent)
            .where(InterviewScenarioContent.id == id)
            .values(is_deleted=True)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0