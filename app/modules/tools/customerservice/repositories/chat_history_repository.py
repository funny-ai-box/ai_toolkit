"""
聊天历史仓储实现
"""
from typing import List, Tuple, Optional
import logging
from datetime import datetime
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.snowflake import generate_id
from app.modules.tools.customerservice.entities.chat import ChatHistory
from app.modules.tools.customerservice.repositories.iface.chat_history_repository import IChatHistoryRepository

class ChatHistoryRepository(IChatHistoryRepository):
    """聊天历史仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化聊天历史仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    async def get_by_id_async(self, id: int) -> Optional[ChatHistory]:
        """
        获取聊天记录
        
        Args:
            id: 记录ID
            
        Returns:
            聊天记录实体
        """
        try:
            query = select(ChatHistory).where(ChatHistory.id == id)
            result = await self.db.execute(query)
            return result.scalars().first()
        except Exception as ex:
            self.logger.error(f"获取聊天记录失败, ID: {id}, 错误: {str(ex)}")
            raise
    
    async def get_session_history_async(self, session_id: int, limit: int = 20) -> List[ChatHistory]:
        """
        获取会话的聊天记录
        
        Args:
            session_id: 会话ID
            limit: 数量限制
            
        Returns:
            聊天记录列表
        """
        try:
            query = select(ChatHistory).where(
                ChatHistory.session_id == session_id
            ).order_by(desc(ChatHistory.create_date)).limit(limit)
            
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as ex:
            self.logger.error(f"获取会话聊天记录失败, 会话ID: {session_id}, 错误: {str(ex)}")
            raise
    
    async def get_session_history_paginated_async(
        self, session_id: int, page_index: int = 1, page_size: int = 20
    ) -> Tuple[List[ChatHistory], int]:
        """
        分页获取会话的聊天记录
        
        Args:
            session_id: 会话ID
            page_index: 页码
            page_size: 每页数量
            
        Returns:
            聊天记录列表和总数
        """
        try:
            # 确保页码和每页数量有效
            if page_index < 1:
                page_index = 1
            if page_size < 1:
                page_size = 20
            
            # 计算跳过的记录数
            skip = (page_index - 1) * page_size
            
            # 查询满足条件的记录总数
            count_query = select(func.count()).where(ChatHistory.session_id == session_id)
            total_count = await self.db.scalar(count_query) or 0
            
            # 查询分页数据
            query = select(ChatHistory).where(
                ChatHistory.session_id == session_id
            ).order_by(desc(ChatHistory.create_date)).offset(skip).limit(page_size)
            
            result = await self.db.execute(query)
            items = result.scalars().all()
            
            # 返回结果按照时间升序排序
            sorted_items = sorted(items, key=lambda x: x.create_date)
            
            return sorted_items, total_count
        except Exception as ex:
            self.logger.error(f"分页获取会话聊天记录失败, 会话ID: {session_id}, 错误: {str(ex)}")
            raise
    
    async def get_recent_history_async(self, session_id: int, count: int = 10) -> List[ChatHistory]:
        """
        获取最近的聊天记录
        
        Args:
            session_id: 会话ID
            count: 记录数量
            
        Returns:
            聊天记录列表
        """
        try:
            query = select(ChatHistory).where(
                ChatHistory.session_id == session_id
            ).order_by(desc(ChatHistory.create_date)).limit(count)
            
            result = await self.db.execute(query)
            items = result.scalars().all()
            
            # 返回结果按照时间升序排序
            return sorted(items, key=lambda x: x.create_date)
        except Exception as ex:
            self.logger.error(f"获取最近聊天记录失败, 会话ID: {session_id}, 错误: {str(ex)}")
            raise
    
    async def add_async(self, history: ChatHistory) -> bool:
        """
        添加聊天记录
        
        Args:
            history: 聊天记录实体
            
        Returns:
            操作结果
        """
        try:
            history.id = generate_id()
            now = datetime.now()
            history.create_date = now
            history.last_modify_date = now
            
            self.db.add(history)
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"添加聊天记录失败, 错误: {str(ex)}")
            raise
    
    async def add_range_async(self, history_list: List[ChatHistory]) -> bool:
        """
        批量添加聊天记录
        
        Args:
            history_list: 聊天记录列表
            
        Returns:
            操作结果
        """
        try:
            now = datetime.now()
            for history in history_list:
                history.id = generate_id()
                history.create_date = now
                history.last_modify_date = now
                self.db.add(history)
            
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"批量添加聊天记录失败, 错误: {str(ex)}")
            raise
    
    async def update_async(self, history: ChatHistory) -> bool:
        """
        更新聊天记录
        
        Args:
            history: 聊天记录实体
            
        Returns:
            操作结果
        """
        try:
            history.last_modify_date = datetime.now()
            await self.db.merge(history)
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"更新聊天记录失败, ID: {history.id}, 错误: {str(ex)}")
            raise
    
    async def delete_async(self, id: int) -> bool:
        """
        删除聊天记录
        
        Args:
            id: 记录ID
            
        Returns:
            操作结果
        """
        try:
            history = await self.get_by_id_async(id)
            if not history:
                return False
            
            await self.db.delete(history)
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"删除聊天记录失败, ID: {id}, 错误: {str(ex)}")
            raise
    
    async def delete_session_history_async(self, session_id: int) -> bool:
        """
        删除会话的所有聊天记录
        
        Args:
            session_id: 会话ID
            
        Returns:
            操作结果
        """
        try:
            query = select(ChatHistory).where(ChatHistory.session_id == session_id)
            result = await self.db.execute(query)
            items = result.scalars().all()
            
            for item in items:
                await self.db.delete(item)
            
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"删除会话所有聊天记录失败, 会话ID: {session_id}, 错误: {str(ex)}")
            raise