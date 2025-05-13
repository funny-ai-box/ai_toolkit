"""
聊天连接仓储实现
"""
import datetime
import logging
from typing import List, Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.snowflake import generate_id
from app.modules.tools.customerservice.entities import ChatConnection

logger = logging.getLogger(__name__)


class ChatConnectionRepository:
    """聊天连接仓储"""

    def __init__(self, db: AsyncSession):
        """
        初始化聊天连接仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[ChatConnection]:
        """
        获取连接
        
        Args:
            id: 连接ID
            
        Returns:
            连接实体
        """
        try:
            result = await self.db.execute(
                select(ChatConnection).where(ChatConnection.id == id)
            )
            return result.scalar_one_or_none()
        except Exception as ex:
            logger.error(f"获取聊天连接失败, ID: {id}", exc_info=ex)
            raise

    async def get_by_connection_id_async(self, connection_id: str) -> Optional[ChatConnection]:
        """
        根据连接ID获取连接
        
        Args:
            connection_id: 连接ID
            
        Returns:
            连接实体
        """
        try:
            result = await self.db.execute(
                select(ChatConnection).where(ChatConnection.connection_id == connection_id)
            )
            return result.scalar_one_or_none()
        except Exception as ex:
            logger.error(f"根据连接ID获取聊天连接失败, ConnectionId: {connection_id}", exc_info=ex)
            raise

    async def get_session_connections_async(self, session_id: int, active_only: bool = True) -> List[ChatConnection]:
        """
        获取会话的连接
        
        Args:
            session_id: 会话ID
            active_only: 是否只返回活跃连接
            
        Returns:
            连接列表
        """
        try:
            query = select(ChatConnection).where(ChatConnection.session_id == session_id)
            
            if active_only:
                query = query.where(ChatConnection.is_active == 1)
                
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as ex:
            logger.error(f"获取会话连接失败, 会话ID: {session_id}", exc_info=ex)
            raise

    async def add_async(self, connection: ChatConnection) -> bool:
        """
        添加连接
        
        Args:
            connection: 连接实体
            
        Returns:
            操作结果
        """
        try:
            connection.id = generate_id()
            now = datetime.datetime.now()
            connection.last_active_time = now
            connection.create_date = now
            connection.last_modify_date = now
            
            self.db.add(connection)
            await self.db.flush()
            return True
        except Exception as ex:
            logger.error("添加聊天连接失败", exc_info=ex)
            raise

    async def update_async(self, connection: ChatConnection) -> bool:
        """
        更新连接
        
        Args:
            connection: 连接实体
            
        Returns:
            操作结果
        """
        try:
            connection.last_modify_date = datetime.datetime.now()
            
            await self.db.execute(
                update(ChatConnection)
                .where(ChatConnection.id == connection.id)
                .values(
                    connection_id=connection.connection_id,
                    client_type=connection.client_type,
                    is_active=connection.is_active,
                    last_active_time=connection.last_active_time,
                    last_modify_date=connection.last_modify_date
                )
            )
            await self.db.flush()
            return True
        except Exception as ex:
            logger.error(f"更新聊天连接失败, ID: {connection.id}", exc_info=ex)
            raise

    async def update_connection_status_async(self, connection_id: str, is_active: bool) -> bool:
        """
        更新连接活跃状态
        
        Args:
            connection_id: 连接ID
            is_active: 是否活跃
            
        Returns:
            操作结果
        """
        try:
            now = datetime.datetime.now()
            await self.db.execute(
                update(ChatConnection)
                .where(ChatConnection.connection_id == connection_id)
                .values(
                    is_active=1 if is_active else 0,
                    last_active_time=now,
                    last_modify_date=now
                )
            )
            await self.db.flush()
            return True
        except Exception as ex:
            logger.error(f"更新聊天连接状态失败, ConnectionId: {connection_id}", exc_info=ex)
            raise

    async def update_last_active_time_async(self, connection_id: str) -> bool:
        """
        更新连接最后活跃时间
        
        Args:
            connection_id: 连接ID
            
        Returns:
            操作结果
        """
        try:
            now = datetime.datetime.now()
            await self.db.execute(
                update(ChatConnection)
                .where(ChatConnection.connection_id == connection_id)
                .values(
                    last_active_time=now,
                    last_modify_date=now
                )
            )
            await self.db.flush()
            return True
        except Exception as ex:
            logger.error(f"更新聊天连接最后活跃时间失败, ConnectionId: {connection_id}", exc_info=ex)
            raise

    async def delete_async(self, connection_id: str) -> bool:
        """
        删除连接
        
        Args:
            connection_id: 连接ID
            
        Returns:
            操作结果
        """
        try:
            await self.db.execute(
                delete(ChatConnection).where(ChatConnection.connection_id == connection_id)
            )
            await self.db.flush()
            return True
        except Exception as ex:
            logger.error(f"删除聊天连接失败, ConnectionId: {connection_id}", exc_info=ex)
            raise

    async def delete_session_connections_async(self, session_id: int) -> bool:
        """
        删除会话的所有连接
        
        Args:
            session_id: 会话ID
            
        Returns:
            操作结果
        """
        try:
            await self.db.execute(
                delete(ChatConnection).where(ChatConnection.session_id == session_id)
            )
            await self.db.flush()
            return True
        except Exception as ex:
            logger.error(f"删除会话所有连接失败, 会话ID: {session_id}", exc_info=ex)
            raise

    async def cleanup_expired_connections_async(self, expiry_minutes: int = 30) -> int:
        """
        清理过期连接
        
        Args:
            expiry_minutes: 过期时间（分钟）
            
        Returns:
            操作结果
        """
        try:
            now = datetime.datetime.now()
            expiry_time = now - datetime.timedelta(minutes=expiry_minutes)
            
            result = await self.db.execute(
                update(ChatConnection)
                .where(
                    (ChatConnection.last_active_time < expiry_time) & 
                    (ChatConnection.is_active == 1)
                )
                .values(
                    is_active=0,
                    last_modify_date=now
                )
            )
            
            await self.db.flush()
            return result.rowcount
        except Exception as ex:
            logger.error(f"清理过期连接失败, 过期时间: {expiry_minutes}分钟", exc_info=ex)
            raise