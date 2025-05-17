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
            print(f"获取聊天会话失败, ID: {id}, 错误: {str(ex)}")
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
            print(f"根据会话Key获取会话失败, SessionKey: {session_key}, 错误: {str(ex)}")
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
            print(f"获取用户会话列表失败, 用户ID: {user_id}, 错误: {str(ex)}")
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
            print(f"分页获取用户会话列表失败, 用户ID: {user_id}, 错误: {str(ex)}")
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
            print(f"[DEBUG] 开始创建会话实体到数据库: user_id={session.user_id}")
            session.id = generate_id()
            session.session_key = str(uuid.uuid4()).replace("-", "")
            now = datetime.now()
            session.create_date = now
            session.last_modify_date = now
            
            print(f"[DEBUG] 生成的 session.id={session.id}, session_key={session.session_key}")
            self.db.add(session)
            print(f"[DEBUG] 已添加会话到数据库会话，等待flush")
            await self.db.flush()
            print(f"[DEBUG] 数据库flush完成")
            
            # 添加事务提交
            print(f"[DEBUG] 准备提交事务")
            await self.db.commit()
            print(f"[DEBUG] 事务提交完成")
            
            return True
        except Exception as ex:
            print(f"[ERROR] 创建聊天会话失败, 错误: {str(ex)}")
            print(f"[ERROR] 错误类型: {type(ex).__name__}")
            print(f"[ERROR] 准备回滚事务")
            await self.db.rollback()
            print(f"[ERROR] 事务回滚完成")
            import traceback
            print(f"[ERROR] 错误堆栈: {traceback.format_exc()}")
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
            print(f"[DEBUG] 准备更新会话: id={session.id}")
            session.last_modify_date = datetime.now()
            await self.db.merge(session)
            print(f"[DEBUG] 会话合并完成，等待flush")
            await self.db.flush()
            print(f"[DEBUG] 数据库flush完成")
            
            # 添加事务提交
            print(f"[DEBUG] 准备提交事务")
            await self.db.commit()
            print(f"[DEBUG] 事务提交完成")
            
            return True
        except Exception as ex:
            print(f"[ERROR] 更新聊天会话失败, ID: {session.id}, 错误: {str(ex)}")
            print(f"[ERROR] 准备回滚事务")
            await self.db.rollback()
            print(f"[ERROR] 事务回滚完成")
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
            print(f"[DEBUG] 准备结束会话: id={id}")
            session = await self.get_by_id_async(id)
            if not session:
                print(f"[WARNING] 要结束的会话不存在: id={id}")
                return False
            
            session.status = ChatSessionStatus.ENDED
            session.last_modify_date = datetime.now()
            
            await self.db.merge(session)
            print(f"[DEBUG] 会话合并完成，等待flush")
            await self.db.flush()
            print(f"[DEBUG] 数据库flush完成")
            
            # 添加事务提交
            print(f"[DEBUG] 准备提交事务")
            await self.db.commit()
            print(f"[DEBUG] 事务提交完成")
            
            return True
        except Exception as ex:
            print(f"[ERROR] 结束聊天会话失败, ID: {id}, 错误: {str(ex)}")
            print(f"[ERROR] 准备回滚事务")
            await self.db.rollback()
            print(f"[ERROR] 事务回滚完成")
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
            print(f"[DEBUG] 准备删除会话: id={id}")
            session = await self.get_by_id_async(id)
            if not session:
                print(f"[WARNING] 要删除的会话不存在: id={id}")
                return False
            
            await self.db.delete(session)
            print(f"[DEBUG] 会话删除，等待flush")
            await self.db.flush()
            print(f"[DEBUG] 数据库flush完成")
            
            # 添加事务提交
            print(f"[DEBUG] 准备提交事务")
            await self.db.commit()
            print(f"[DEBUG] 事务提交完成")
            
            return True
        except Exception as ex:
            print(f"[ERROR] 删除聊天会话失败, ID: {id}, 错误: {str(ex)}")
            print(f"[ERROR] 准备回滚事务")
            await self.db.rollback()
            print(f"[ERROR] 事务回滚完成")
            raise