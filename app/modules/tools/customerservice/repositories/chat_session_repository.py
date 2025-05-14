"""
聊天会话仓储实现
"""
from typing import List, Tuple, Optional
import logging
import uuid
from datetime import datetime
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.snowflake import generate_id
from app.modules.tools.customerservice.entities.chat import ChatSession, ChatSessionStatus
from app.modules.tools.customerservice.repositories.iface.chat_session_repository import IChatSessionRepository

class ChatSessionRepository(IChatSessionRepository):
    """聊天会话仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化聊天会话仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    async def get_by_id_async(self, id: int) -> Optional[ChatSession]:
        """
        获取聊天会话
        
        Args:
            id: 会话ID
            
        Returns:
            会话实体
        """
        try:
            query = select(ChatSession).where(ChatSession.id == id)
            result = await self.db.execute(query)
            return result.scalars().first()
        except Exception as ex:
            self.logger.error(f"获取聊天会话失败, ID: {id}, 错误: {str(ex)}")
            raise
    
    async def get_by_session_key_async(self, session_key: str) -> Optional[ChatSession]:
        """
        根据会话Key获取会话
        
        Args:
            session_key: 会话Key
            
        Returns:
            会话实体
        """
        try:
            query = select(ChatSession).where(ChatSession.session_key == session_key)
            result = await self.db.execute(query)
            return result.scalars().first()
        except Exception as ex:
            self.logger.error(f"根据会话Key获取会话失败, SessionKey: {session_key}, 错误: {str(ex)}")
            raise
    
    async def get_user_sessions_async(self, user_id: int, include_ended: bool = False) -> List[ChatSession]:
        """
        获取用户的所有会话
        
        Args:
            user_id: 用户ID
            include_ended: 是否包含已结束的会话
            
        Returns:
            会话列表
        """
        try:
            query = select(ChatSession).where(ChatSession.user_id == user_id)
            
            if not include_ended:
                query = query.where(ChatSession.status == ChatSessionStatus.ACTIVE)
            
            query = query.order_by(desc(ChatSession.last_modify_date))
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as ex:
            self.logger.error(f"获取用户会话列表失败, 用户ID: {user_id}, 错误: {str(ex)}")
            raise
    
    async def get_user_sessions_paginated_async(
        self, user_id: int, page_index: int = 1, page_size: int = 20, include_ended: bool = True
    ) -> Tuple[List[ChatSession], int]:
        """
        分页获取用户的所有会话
        
        Args:
            user_id: 用户ID
            page_index: 页码
            page_size: 每页数量
            include_ended: 是否包含已结束的会话
            
        Returns:
            会话列表和总数
        """
        try:
            # 确保页码和每页数量有效
            if page_index < 1:
                page_index = 1
            if page_size < 1:
                page_size = 20
            
            # 计算跳过的记录数
            skip = (page_index - 1) * page_size
            
            # 构建查询
            query = select(ChatSession).where(ChatSession.user_id == user_id)
            
            if not include_ended:
                query = query.where(ChatSession.status == ChatSessionStatus.ACTIVE)
            
            # 查询满足条件的记录总数
            count_query = select(func.count()).select_from(query.subquery())
            total_count = await self.db.scalar(count_query) or 0
            
            # 查询分页数据
            query = query.order_by(desc(ChatSession.last_modify_date)).offset(skip).limit(page_size)
            result = await self.db.execute(query)
            items = result.scalars().all()
            
            return list(items), total_count
        except Exception as ex:
            self.logger.error(f"分页获取用户会话列表失败, 用户ID: {user_id}, 错误: {str(ex)}")
            raise
    
    async def create_async(self, session: ChatSession) -> bool:
        """
        创建会话
        
        Args:
            session: 会话实体
            
        Returns:
            操作结果
        """
        try:
            session.id = generate_id()
            session.session_key = str(uuid.uuid4()).replace("-", "")
            now = datetime.now()
            session.create_date = now
            session.last_modify_date = now
            
            self.db.add(session)
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"创建聊天会话失败, 错误: {str(ex)}")
            raise
    
    async def update_async(self, session: ChatSession) -> bool:
        """
        更新会话
        
        Args:
            session: 会话实体
            
        Returns:
            操作结果
        """
        try:
            session.last_modify_date = datetime.now()
            await self.db.merge(session)
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"更新聊天会话失败, ID: {session.id}, 错误: {str(ex)}")
            raise
    
    async def end_session_async(self, id: int) -> bool:
        """
        结束会话
        
        Args:
            id: 会话ID
            
        Returns:
            操作结果
        """
        try:
            session = await self.get_by_id_async(id)
            if not session:
                return False
            
            session.status = ChatSessionStatus.ENDED
            session.last_modify_date = datetime.now()
            
            await self.db.merge(session)
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"结束聊天会话失败, ID: {id}, 错误: {str(ex)}")
            raise
    
    async def delete_async(self, id: int) -> bool:
        """
        删除会话
        
        Args:
            id: 会话ID
            
        Returns:
            操作结果
        """
        try:
            session = await self.get_by_id_async(id)
            if not session:
                return False
            
            await self.db.delete(session)
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"删除聊天会话失败, ID: {id}, 错误: {str(ex)}")
            raise