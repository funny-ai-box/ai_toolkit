"""
聊天连接仓储实现
"""
from typing import List, Optional
import logging
from datetime import datetime
from sqlalchemy import select, and_, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.snowflake import generate_id
from app.modules.tools.customerservice.entities.chat import ChatConnection
from app.modules.tools.customerservice.repositories.iface.chat_connection_repository import IChatConnectionRepository

class ChatConnectionRepository(IChatConnectionRepository):
    """聊天连接仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化聊天连接仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    async def get_by_id_async(self, id: int) -> Optional[ChatConnection]:
        """
        获取连接
        
        Args:
            id: 连接ID
            
        Returns:
            连接实体
        """
        try:
            query = select(ChatConnection).where(ChatConnection.id == id)
            result = await self.db.execute(query)
            return result.scalars().first()
        except Exception as ex:
            self.logger.error(f"获取聊天连接失败, ID: {id}, 错误: {str(ex)}")
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
            query = select(ChatConnection).where(ChatConnection.connection_id == connection_id)
            result = await self.db.execute(query)
            return result.scalars().first()
        except Exception as ex:
            self.logger.error(f"根据连接ID获取聊天连接失败, ConnectionId: {connection_id}, 错误: {str(ex)}")
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
            self.logger.error(f"获取会话连接失败, 会话ID: {session_id}, 错误: {str(ex)}")
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
            now = datetime.now()
            connection.last_active_time = now
            connection.create_date = now
            connection.last_modify_date = now
            
            self.db.add(connection)
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"添加聊天连接失败, 错误: {str(ex)}")
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
            connection.last_modify_date = datetime.now()
            await self.db.merge(connection)
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"更新聊天连接失败, ID: {connection.id}, 错误: {str(ex)}")
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
            connection = await self.get_by_connection_id_async(connection_id)
            if not connection:
                return False
            
            connection.is_active = 1 if is_active else 0
            connection.last_active_time = datetime.now()
            connection.last_modify_date = datetime.now()
            
            await self.db.merge(connection)
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"更新聊天连接状态失败, ConnectionId: {connection_id}, 错误: {str(ex)}")
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
            connection = await self.get_by_connection_id_async(connection_id)
            if not connection:
                return False
            
            now = datetime.now()
            connection.last_active_time = now
            connection.last_modify_date = now
            
            await self.db.merge(connection)
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"更新聊天连接最后活跃时间失败, ConnectionId: {connection_id}, 错误: {str(ex)}")
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
            connection = await self.get_by_connection_id_async(connection_id)
            if not connection:
                return False
            
            await self.db.delete(connection)
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"删除聊天连接失败, ConnectionId: {connection_id}, 错误: {str(ex)}")
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
            connections = await self.get_session_connections_async(session_id, False)
            
            for connection in connections:
                await self.db.delete(connection)
            
            await self.db.flush()
            return True
        except Exception as ex:
            self.logger.error(f"删除会话所有连接失败, 会话ID: {session_id}, 错误: {str(ex)}")
            raise
    
    async def cleanup_expired_connections_async(self, expiry_minutes: int = 30) -> int:
        """
        清理过期连接
        
        Args:
            expiry_minutes: 过期时间（分钟）
            
        Returns:
            清理的连接数
        """
        try:
            expiry_time = datetime.now().timestamp() - (expiry_minutes * 60)
            expiry_datetime = datetime.fromtimestamp(expiry_time)
            
            query = select(ChatConnection).where(
                and_(
                    ChatConnection.last_active_time < expiry_datetime,
                    ChatConnection.is_active == 1
                )
            )
            
            result = await self.db.execute(query)
            connections = result.scalars().all()
            
            for connection in connections:
                connection.is_active = 0
                connection.last_modify_date = datetime.now()
                await self.db.merge(connection)
            
            await self.db.flush()
            return len(connections)
        except Exception as ex:
            self.logger.error(f"清理过期连接失败, 过期时间: {expiry_minutes}分钟, 错误: {str(ex)}")
            raise