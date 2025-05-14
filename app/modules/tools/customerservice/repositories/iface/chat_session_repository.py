"""
聊天会话仓储接口
"""
from typing import List, Tuple, Optional
from app.modules.tools.customerservice.entities.chat import ChatSession

class IChatSessionRepository:
    """聊天会话仓储接口"""
    
    async def get_by_id_async(self, id: int) -> Optional[ChatSession]:
        """
        获取聊天会话
        
        Args:
            id: 会话ID
            
        Returns:
            会话实体
        """
        raise NotImplementedError()
    
    async def get_by_session_key_async(self, session_key: str) -> Optional[ChatSession]:
        """
        根据会话Key获取会话
        
        Args:
            session_key: 会话Key
            
        Returns:
            会话实体
        """
        raise NotImplementedError()
    
    async def get_user_sessions_async(self, user_id: int, include_ended: bool = False) -> List[ChatSession]:
        """
        获取用户的所有会话
        
        Args:
            user_id: 用户ID
            include_ended: 是否包含已结束的会话
            
        Returns:
            会话列表
        """
        raise NotImplementedError()
    
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
        raise NotImplementedError()
    
    async def create_async(self, session: ChatSession) -> bool:
        """
        创建会话
        
        Args:
            session: 会话实体
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def update_async(self, session: ChatSession) -> bool:
        """
        更新会话
        
        Args:
            session: 会话实体
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def end_session_async(self, id: int) -> bool:
        """
        结束会话
        
        Args:
            id: 会话ID
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def delete_async(self, id: int) -> bool:
        """
        删除会话
        
        Args:
            id: 会话ID
            
        Returns:
            操作结果
        """
        raise NotImplementedError()