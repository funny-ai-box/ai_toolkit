# app/modules/dataanalysis/repositories/analysis_session_repository.py (continued)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
import datetime


from app.core.utils.snowflake import generate_id
from app.modules.tools.dataanalysis.models import AnalysisSession

class AnalysisSessionRepository:
    """分析会话仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化分析会话仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def add_async(self, session: AnalysisSession) -> AnalysisSession:
        """
        添加分析会话
        
        Args:
            session: 分析会话实体
        
        Returns:
            添加后的实体
        """
        # 使用雪花ID
        session.id = generate_id()
        
        # 设置创建和修改时间
        now = datetime.datetime.now()
        session.create_date = now
        session.last_modify_date = now
        
        # 插入数据
        self.db.add(session)
        await self.db.flush()
        
        return session
    
    async def update_async(self, session: AnalysisSession) -> AnalysisSession:
        """
        更新分析会话
        
        Args:
            session: 分析会话实体
        
        Returns:
            更新后的实体
        """
        # 更新最后修改时间
        session.last_modify_date = datetime.datetime.now()
        
        # 更新数据
        self.db.add(session)
        await self.db.flush()
        
        return session
    
    async def get_by_id_async(self, id: int) -> Optional[AnalysisSession]:
        """
        获取分析会话
        
        Args:
            id: 分析会话ID
        
        Returns:
            分析会话实体
        """
        result = await self.db.execute(
            select(AnalysisSession).filter(AnalysisSession.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_sessions_async(self, user_id: int) -> List[AnalysisSession]:
        """
        获取用户的所有分析会话
        
        Args:
            user_id: 用户ID
        
        Returns:
            分析会话实体列表
        """
        result = await self.db.execute(
            select(AnalysisSession)
            .filter(AnalysisSession.user_id == user_id)
            .order_by(AnalysisSession.last_modify_date.desc())
        )
        return list(result.scalars().all())
    
    async def get_user_active_sessions_async(self, user_id: int) -> List[AnalysisSession]:
        """
        获取用户的活跃分析会话
        
        Args:
            user_id: 用户ID
        
        Returns:
            分析会话实体列表
        """
        result = await self.db.execute(
            select(AnalysisSession)
            .filter(AnalysisSession.user_id == user_id, AnalysisSession.status == 1)
            .order_by(AnalysisSession.last_modify_date.desc())
        )
        return list(result.scalars().all())
    
    async def delete_async(self, id: int) -> bool:
        """
        删除分析会话
        
        Args:
            id: 分析会话ID
        
        Returns:
            是否成功
        """
        result = await self.db.execute(
            delete(AnalysisSession).filter(AnalysisSession.id == id)
        )
        return result.rowcount > 0