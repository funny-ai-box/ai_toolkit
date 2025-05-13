# app/modules/dataanalysis/repositories/conversation_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional, Tuple
import datetime


from app.core.utils.snowflake import generate_id
from app.modules.tools.dataanalysis.models import Conversation

class ConversationRepository:
    """对话记录仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化对话记录仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def add_async(self, conversation: Conversation) -> Conversation:
        """
        添加对话记录
        
        Args:
            conversation: 对话记录实体
        
        Returns:
            添加后的实体
        """
        # 使用雪花ID
        conversation.id = generate_id()
        
        # 设置创建和修改时间
        now = datetime.datetime.now()
        conversation.create_date = now
        conversation.last_modify_date = now
        
        # 插入数据
        self.db.add(conversation)
        await self.db.flush()
        
        return conversation
    
    async def update_async(self, conversation: Conversation) -> Conversation:
        """
        更新对话记录
        
        Args:
            conversation: 对话记录实体
        
        Returns:
            更新后的实体
        """
        # 更新最后修改时间
        conversation.last_modify_date = datetime.datetime.now()
        
        # 更新数据
        self.db.add(conversation)
        await self.db.flush()
        
        return conversation
    
    async def get_by_id_async(self, id: int) -> Optional[Conversation]:
        """
        获取对话记录
        
        Args:
            id: 对话记录ID
        
        Returns:
            对话记录实体
        """
        result = await self.db.execute(
            select(Conversation).filter(Conversation.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_session_conversations_async(self, session_id: int) -> List[Conversation]:
        """
        获取会话的所有对话记录
        
        Args:
            session_id: 会话ID
        
        Returns:
            对话记录实体列表
        """
        result = await self.db.execute(
            select(Conversation)
            .filter(Conversation.session_id == session_id)
            .order_by(Conversation.create_date.desc())
        )
        return list(result.scalars().all())
    
    async def get_paginated_session_conversations_async(self, session_id: int, page_index: int, page_size: int) -> Tuple[List[Conversation], int]:
        """
        根据分页获取会话的对话记录
        
        Args:
            session_id: 会话ID
            page_index: 页码
            page_size: 每页大小
        
        Returns:
            分页的对话记录列表和总记录数
        """
        # 确保页码和每页数量有效
        if page_index < 1:
            page_index = 1
        if page_size < 1:
            page_size = 20
        
        # 计算跳过的记录数
        skip = (page_index - 1) * page_size
        
        # 查询满足条件的记录总数
        result = await self.db.execute(
            select(Conversation).filter(Conversation.session_id == session_id)
        )
        total_count = len(list(result.scalars().all()))
        
        # 查询分页数据
        result = await self.db.execute(
            select(Conversation)
            .filter(Conversation.session_id == session_id)
            .order_by(Conversation.create_date.desc())
            .offset(skip)
            .limit(page_size)
        )
        items = list(result.scalars().all())
        
        return items, total_count
