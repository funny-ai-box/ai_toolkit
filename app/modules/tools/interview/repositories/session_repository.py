"""
面试会话仓储实现

提供面试会话实体的数据访问操作，包括添加、查询、更新和删除等功能。
"""
import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.utils.snowflake import generate_id
from app.modules.tools.interview.models import InterviewSession
from app.modules.tools.interview.enums import InterviewSessionStatus, InterviewSessionEvaluateStatusType


class InterviewSessionRepository:
    """面试会话仓储"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化面试会话仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def add_async(self, session: InterviewSession) -> InterviewSession:
        """
        添加会话
        
        Args:
            session: 会话实体
            
        Returns:
            成功添加的会话实体
        """
        session.id = generate_id()
        now = datetime.datetime.now()
        session.create_date = now
        session.last_modify_date = now
        
        self.db.add(session)
        await self.db.flush()
        return session
    
    async def get_by_id_async(self, id: int) -> Optional[InterviewSession]:
        """
        获取指定ID的会话
        
        Args:
            id: 会话ID
            
        Returns:
            会话实体
        """
        query = select(InterviewSession).where(InterviewSession.id == id)
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def get_user_sessions_async(
        self,
        user_id: int,
        scenario_id: Optional[int] = None,
        job_position_id: Optional[int] = None,
        status: Optional[InterviewSessionStatus] = None,
        page_index: int = 1,
        page_size: int = 20
    ) -> Tuple[List[InterviewSession], int]:
        """
        获取用户的会话列表
        
        Args:
            user_id: 用户ID
            scenario_id: 场景ID（可选）
            job_position_id: 职位ID（可选）
            status: 会话状态（可选）
            page_index: 页码
            page_size: 每页数量
            
        Returns:
            会话列表和总数
        """
        # 确保页码和每页数量有效
        if page_index < 1:
            page_index = 1
        if page_size < 1:
            page_size = 20
        
        # 计算跳过的记录数
        skip = (page_index - 1) * page_size
        
        # 构建查询条件
        query = select(InterviewSession).where(InterviewSession.interviewee_id == user_id)
        
        if scenario_id:
            query = query.where(InterviewSession.scenario_id == scenario_id)
        
        if job_position_id:
            query = query.where(InterviewSession.job_position_id == job_position_id)
        
        if status is not None:
            query = query.where(InterviewSession.status == status)
        
        # 查询满足条件的记录总数
        count_query = select(func.count()).select_from(query.subquery())
        total_count = await self.db.scalar(count_query)
        
        # 查询分页数据
        query = query.order_by(InterviewSession.id.desc()).offset(skip).limit(page_size)
        result = await self.db.execute(query)
        items = result.scalars().all()
        
        return list(items), total_count or 0
    
    async def update_async(self, session: InterviewSession) -> bool:
        """
        更新会话
        
        Args:
            session: 会话实体
            
        Returns:
            更新结果
        """
        session.last_modify_date = datetime.datetime.now()
        await self.db.flush()
        return True
    
    async def delete_async(self, id: int) -> bool:
        """
        删除会话
        
        Args:
            id: 会话ID
            
        Returns:
            删除结果
        """
        stmt = (
            update(InterviewSession)
            .where(InterviewSession.id == id)
            .values(is_deleted=True)
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0
    
    async def lock_processing_status_async(self, id: int) -> bool:
        """
        执行面试结果评估前的锁定更新
        
        Args:
            id: 会话Id
            
        Returns:
            操作结果
        """
        stmt = (
            update(InterviewSession)
            .where(
                InterviewSession.id == id,
                InterviewSession.evaluate_status == InterviewSessionEvaluateStatusType.PENDING
            )
            .values(
                evaluate_status=InterviewSessionEvaluateStatusType.PROCESSING,
                last_modify_date=datetime.datetime.now()
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0
    
    async def start_evaluate_session_async(self, id: int) -> bool:
        """
        开始评估面试结果
        
        Args:
            id: 会话Id
            
        Returns:
            操作结果
        """
        stmt = (
            update(InterviewSession)
            .where(InterviewSession.id == id)
            .values(
                evaluate_status=InterviewSessionEvaluateStatusType.PENDING,
                error_message=None,
                evaluate_count=InterviewSession.evaluate_count + 1,
                last_modify_date=datetime.datetime.now()
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0
    
    async def update_evaluate_status_async(
        self, 
        id: int, 
        status: InterviewSessionEvaluateStatusType, 
        error_message: Optional[str] = None
    ) -> bool:
        """
        更新面试结果评估的记录状态
        
        Args:
            id: Id
            status: 状态
            error_message: 错误消息
            
        Returns:
            操作结果
        """
        stmt = (
            update(InterviewSession)
            .where(InterviewSession.id == id)
            .values(
                evaluate_status=status,
                error_message=error_message,
                last_modify_date=datetime.datetime.now()
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0
    
    async def get_pending_evaluate_sessions_async(self, limit: int = 10) -> List[InterviewSession]:
        """
        获取待处理的面试结果评估列表
        
        Args:
            limit: 限制数量
            
        Returns:
            待处理的列表
        """
        query = (
            select(InterviewSession)
            .where(InterviewSession.evaluate_status == InterviewSessionEvaluateStatusType.PENDING)
            .order_by(InterviewSession.create_date)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())