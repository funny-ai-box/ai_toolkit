"""
聊天历史仓储接口
"""
from typing import List, Tuple, Optional
from app.modules.tools.customerservice.entities.chat import ChatHistory

class IChatHistoryRepository:
    """聊天历史仓储接口"""
    
    async def get_by_id_async(self, id: int) -> Optional[ChatHistory]:
        """
        获取聊天记录
        
        Args:
            id: 记录ID
            
        Returns:
            聊天记录实体
        """
        raise NotImplementedError()
    
    async def get_session_history_async(self, session_id: int, limit: int = 20) -> List[ChatHistory]:
        """
        获取会话的聊天记录
        
        Args:
            session_id: 会话ID
            limit: 数量限制
            
        Returns:
            聊天记录列表
        """
        raise NotImplementedError()
    
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
        raise NotImplementedError()
    
    async def get_recent_history_async(self, session_id: int, count: int = 10) -> List[ChatHistory]:
        """
        获取最近的聊天记录
        
        Args:
            session_id: 会话ID
            count: 记录数量
            
        Returns:
            聊天记录列表
        """
        raise NotImplementedError()
    
    async def add_async(self, history: ChatHistory) -> bool:
        """
        添加聊天记录
        
        Args:
            history: 聊天记录实体
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def add_range_async(self, history_list: List[ChatHistory]) -> bool:
        """
        批量添加聊天记录
        
        Args:
            history_list: 聊天记录列表
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def update_async(self, history: ChatHistory) -> bool:
        """
        更新聊天记录
        
        Args:
            history: 聊天记录实体
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def delete_async(self, id: int) -> bool:
        """
        删除聊天记录
        
        Args:
            id: 记录ID
            
        Returns:
            操作结果
        """
        raise NotImplementedError()
    
    async def delete_session_history_async(self, session_id: int) -> bool:
        """
        删除会话的所有聊天记录
        
        Args:
            session_id: 会话ID
            
        Returns:
            操作结果
        """
        raise NotImplementedError()