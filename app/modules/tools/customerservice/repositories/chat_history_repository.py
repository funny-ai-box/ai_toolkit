"""
聊天历史仓储实现
"""
import datetime
import logging
from typing import List, Tuple, Optional

from sqlalchemy import select, update, delete, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.snowflake import generate_id
from app.modules.tools.customerservice.entities import ChatHistory

logger = logging.getLogger(__name__)


class ChatHistoryRepository:
    """聊天历史仓储"""

    def __init__(self, db: AsyncSession):
        """
        初始化聊天历史仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[ChatHistory]:
        """
        获取聊天记录
        
        Args:
            id: 记录ID
            
        Returns:
            聊天记录实体
        """
        try:
            result = await self.db.execute(
                select(ChatHistory).where(ChatHistory.id == id)
            )
            return result.scalar_one_or_none()
        except Exception as ex:
            logger.error(f"获取聊天记录失败, ID: {id}", exc_info=ex)
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
            result = await self.db.execute(
                select(ChatHistory)
                .where(ChatHistory.session_id == session_id)
                .order_by(desc(ChatHistory.create_date))
                .limit(limit)
            )
            return list(result.scalars().all())
        except Exception as ex:
            logger.error(f"获取会话聊天记录失败, 会话ID: {session_id}", exc_info=ex)
            raise

    async def get_session_history_paginated_async(
        self, session_id: int, page_index: int = 1, page_size: int = 20
    ) -> Tuple[List[ChatHistory], int]:
        """
        分页获取会话的聊天记录，前端展示使用
        
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
            count_query = select(ChatHistory.id).where(ChatHistory.session_id == session_id)
            count_result = await self.db.execute(count_query)
            total_count = len(count_result.all())
            
            # 查询分页数据
            query = (
                select(ChatHistory)
                .where(ChatHistory.session_id == session_id)
                .order_by(desc(ChatHistory.create_date))
                .offset(skip)
                .limit(page_size)
            )
            
            result = await self.db.execute(query)
            items = list(result.scalars().all())
            
            # 返回的结果按照ID升序排序（时间顺序）
            items.sort(key=lambda x: x.id)
            
            return items, total_count
        except Exception as ex:
            logger.error(f"分页获取会话聊天记录失败, 会话ID: {session_id}", exc_info=ex)
            raise

    async def get_recent_history_async(self, session_id: int, count: int = 10) -> List[ChatHistory]:
        """
        获取最近的聊天记录，会话上下文中附加
        
        Args:
            session_id: 会话ID
            count: 记录数量
            
        Returns:
            聊天记录列表
        """
        try:
            result = await self.db.execute(
                select(ChatHistory)
                .where(ChatHistory.session_id == session_id)
                .order_by(desc(ChatHistory.create_date))  # 降序，取最近的会话内容
                .limit(count)
            )
            records = list(result.scalars().all())
            # 按照ID（时间顺序）排序，旧的先加
            return sorted(records, key=lambda x: x.id)
        except Exception as ex:
            logger.error(f"获取最近聊天记录失败, 会话ID: {session_id}", exc_info=ex)
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
            now = datetime.datetime.now()
            history.create_date = now
            history.last_modify_date = now
            
            self.db.add(history)
            await self.db.flush()
            return True
        except Exception as ex:
            logger.error("添加聊天记录失败", exc_info=ex)
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
            now = datetime.datetime.now()
            for history in history_list:
                history.id = generate_id()
                history.create_date = now
                history.last_modify_date = now
                self.db.add(history)
                
            await self.db.flush()
            return True
        except Exception as ex:
            logger.error("批量添加聊天记录失败", exc_info=ex)
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
            history.last_modify_date = datetime.datetime.now()
            
            await self.db.execute(
                update(ChatHistory)
                .where(ChatHistory.id == history.id)
                .values(
                    content=history.content,
                    intent=history.intent,
                    call_datas=history.call_datas,
                    image_url=history.image_url,
                    last_modify_date=history.last_modify_date
                )
            )
            await self.db.flush()
            return True
        except Exception as ex:
            logger.error(f"更新聊天记录失败, ID: {history.id}", exc_info=ex)
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
            await self.db.execute(
                delete(ChatHistory).where(ChatHistory.id == id)
            )
            await self.db.flush()
            return True
        except Exception as ex:
            logger.error(f"删除聊天记录失败, ID: {id}", exc_info=ex)
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
            await self.db.execute(
                delete(ChatHistory).where(ChatHistory.session_id == session_id)
            )
            await self.db.flush()
            return True
        except Exception as ex:
            logger.error(f"删除会话所有聊天记录失败, 会话ID: {session_id}", exc_info=ex)
            raise