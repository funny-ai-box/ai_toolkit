"""
面试交互记录仓储实现

提供面试交互记录实体的数据访问操作，包括添加、查询、更新和删除等功能。
"""
import datetime
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.utils.snowflake import generate_id
from app.modules.tools.interview.models import InterviewInteraction


class InterviewInteractionRepository:
    """面试交互记录仓储"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化面试交互记录仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def add_async(self, interaction: InterviewInteraction) -> InterviewInteraction:
        """
        添加交互记录
        
        Args:
            interaction: 交互记录实体
            
        Returns:
            成功添加的交互记录实体
        """
        interaction.id = generate_id()
        interaction.create_date = datetime.datetime.now()
        
        self.db.add(interaction)
        await self.db.flush()
        return interaction
    
    async def batch_add_async(self, interactions: List[InterviewInteraction]) -> bool:
        """
        批量添加交互记录
        
        Args:
            interactions: 交互记录实体列表
            
        Returns:
            添加结果
        """
        if not interactions:
            return False
        
        now = datetime.datetime.now()
        for interaction in interactions:
            interaction.id = generate_id()
            interaction.create_date = now
            self.db.add(interaction)
        
        await self.db.flush()
        return True
    
    async def get_by_id_async(self, id: int) -> Optional[InterviewInteraction]:
        """
        获取指定ID的交互记录
        
        Args:
            id: 交互记录ID
            
        Returns:
            交互记录实体
        """
        query = select(InterviewInteraction).where(InterviewInteraction.id == id)
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def get_by_session_id_async(self, session_id: int) -> List[InterviewInteraction]:
        """
        获取会话的所有交互记录
        
        Args:
            session_id: 会话ID
            
        Returns:
            交互记录实体列表
        """
        query = (
            select(InterviewInteraction)
            .where(InterviewInteraction.session_id == session_id)
            .order_by(InterviewInteraction.interaction_order)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_async(self, interaction: InterviewInteraction) -> bool:
        """
        更新交互记录
        
        Args:
            interaction: 交互记录实体
            
        Returns:
            更新结果
        """
        await self.db.flush()
        return True
    
    async def batch_update_async(self, interactions: List[InterviewInteraction]) -> bool:
        """
        批量更新交互记录
        
        Args:
            interactions: 交互记录实体列表
            
        Returns:
            更新结果
        """
        if not interactions:
            return False
        
        await self.db.flush()
        return True
    
    async def delete_async(self, id: int) -> bool:
        """
        删除交互记录
        
        Args:
            id: 交互记录ID
            
        Returns:
            删除结果
        """
        stmt = (
            update(InterviewInteraction)
            .where(InterviewInteraction.id == id)
            .values(is_deleted=True)
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0
    
    async def delete_by_session_id_async(self, session_id: int) -> bool:
        """
        删除会话的所有交互记录
        
        Args:
            session_id: 会话ID
            
        Returns:
            删除结果
        """
        stmt = (
            update(InterviewInteraction)
            .where(InterviewInteraction.session_id == session_id)
            .values(is_deleted=True)
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0