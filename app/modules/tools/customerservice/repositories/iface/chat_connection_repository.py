"""
聊天连接仓储接口
"""
from typing import List, Optional
from app.modules.tools.customerservice.entities.chat import ChatConnection

class IChatConnectionRepository:
    """聊天连接仓储接口"""
    
    async def get_by_id_async(self, id: int) -> Optional[ChatConnection]:
        """
        获取连接
        
        Args:
            id: 连接ID
            
        Returns:
            连接实体
        """
        raise NotImplementedError()
    
    async def get_by_connection_id_async(self, connection_id: str) -> Optional[ChatConnection]:
        """
        根据连接ID获取连接
        
        Args:
            connection_id: 连接ID
            
        Returns:
            连接实体
        """
        raise NotImplementedError()
    
    async def get_session_connections_async(self, session_id: int, active_only: bool = True) -> List[ChatConnection]:
        """
        获取会话的连接
        
        Args:
            session_id: 会话ID
            active_only: 是否只返回活跃连接
            
        Returns:
            连接列表
        """
        raise NotImplementedError()
    
    async def add_async(self, connection: ChatConnection) -> bool:
        """
        添加连接
        
        Args:
            connection: 连接实体
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def update_async(self, connection: ChatConnection) -> bool:
        """
        更新连接
        
        Args:
            connection: 连接实体
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def update_connection_status_async(self, connection_id: str, is_active: bool) -> bool:
        """
        更新连接活跃状态
        
        Args:
            connection_id: 连接ID
            is_active: 是否活跃
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def update_last_active_time_async(self, connection_id: str) -> bool:
        """
        更新连接最后活跃时间
        
        Args:
            connection_id: 连接ID
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def delete_async(self, connection_id: str) -> bool:
        """
        删除连接
        
        Args:
            connection_id: 连接ID
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def delete_session_connections_async(self, session_id: int) -> bool:
        """
        删除会话的所有连接
        
        Args:
            session_id: 会话ID
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def cleanup_expired_connections_async(self, expiry_minutes: int = 30) -> int:
        """
        清理过期连接
        
        Args:
            expiry_minutes: 过期时间（分钟）
            
        Returns:
            清理的连接数
        """
        raise NotImplementedError()