"""
面试场景仓储实现

提供面试场景实体的数据访问操作，包括添加、查询、更新和删除等功能。
"""
import datetime
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy import select, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.utils.snowflake import generate_id
from app.modules.tools.interview.models import InterviewScenario
from app.modules.tools.interview.enums import InterviewScenarioStatus


class InterviewScenarioRepository:
    """面试场景仓储"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化面试场景仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def add_async(self, scenario: InterviewScenario) -> InterviewScenario:
        """
        添加场景
        
        Args:
            scenario: 场景实体
            
        Returns:
            成功添加的场景实体
        """
        scenario.id = generate_id()
        now = datetime.datetime.now()
        scenario.create_date = now
        scenario.last_modify_date = now
        
        self.db.add(scenario)
        await self.db.flush()
        await self.db.commit()
        return scenario
    
    async def get_by_id_async(self, id: int) -> Optional[InterviewScenario]:
        """
        获取指定ID的场景
        
        Args:
            id: 场景ID
            
        Returns:
            场景实体
        """
        query = select(InterviewScenario).where(InterviewScenario.id == id)
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def get_user_scenarios_async(
        self,
        user_id: int,
        name: Optional[str] = None,
        status: Optional[InterviewScenarioStatus] = None,
        page_index: int = 1,
        page_size: int = 20
    ) -> Tuple[List[InterviewScenario], int]:
        """
        获取用户的场景列表
        
        Args:
            user_id: 用户ID
            name: 场景名称（可选，用于模糊查询）
            status: 场景状态（可选）
            page_index: 页码
            page_size: 每页数量
            
        Returns:
            场景列表和总数
        """
        # 确保页码和每页数量有效
        if page_index < 1:
            page_index = 1
        if page_size < 1:
            page_size = 20
        
        # 计算跳过的记录数
        skip = (page_index - 1) * page_size
        
        # 构建查询条件
        query = select(InterviewScenario).where(InterviewScenario.user_id == user_id)
        
        if name:
            query = query.where(InterviewScenario.name.contains(name))
        
        if status is not None:
            query = query.where(InterviewScenario.status == status)
        
        # 查询满足条件的记录总数
        count_query = select(func.count()).select_from(query.subquery())
        total_count = await self.db.scalar(count_query)
        
        # 查询分页数据
        query = query.order_by(InterviewScenario.id.desc()).offset(skip).limit(page_size)
        result = await self.db.execute(query)
        items = result.scalars().all()
        
        return list(items), total_count or 0
    
    async def update_async(self, scenario: InterviewScenario) -> bool:
        """
        更新场景
        
        Args:
            scenario: 场景实体
            
        Returns:
            更新结果
        """
        scenario.last_modify_date = datetime.datetime.now()
        await self.db.flush()
        await self.db.commit()
        return True
    
    async def start_analysis_question_async(self, id: int) -> bool:
        """
        开始AI分析面试问题和生成
        
        Args:
            id: 场景Id
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        stmt = (
            update(InterviewScenario)
            .where(InterviewScenario.id == id)
            .values(
                status=InterviewScenarioStatus.PENDING,
                error_message=None,
                generate_count=InterviewScenario.generate_count + 1,
                last_modify_date=now
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
    
    async def lock_processing_status_async(self, id: int) -> bool:
        """
        执行面试问题任务生成前的锁定更新
        
        Args:
            id: 面试ID
            
        Returns:
            操作结果
        """
        stmt = (
            update(InterviewScenario)
            .where(
                InterviewScenario.id == id,
                InterviewScenario.status == InterviewScenarioStatus.PENDING
            )
            .values(
                status=InterviewScenarioStatus.ANALYZING,
                last_modify_date=datetime.datetime.now()
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
    
    async def update_status_async(self, id: int, status: InterviewScenarioStatus, error_message: Optional[str] = None) -> bool:
        """
        更新面试任务的记录状态
        
        Args:
            id: Id
            status: 状态
            error_message: 错误消息
            
        Returns:
            操作结果
        """
        stmt = (
            update(InterviewScenario)
            .where(InterviewScenario.id == id)
            .values(
                status=status,
                error_message=error_message,
                last_modify_date=datetime.datetime.now()
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
    
    async def delete_async(self, id: int) -> bool:
        """
        删除场景
        
        Args:
            id: 场景ID
            
        Returns:
            删除结果
        """
        stmt = (
            update(InterviewScenario)
            .where(InterviewScenario.id == id)
            .values(
                is_deleted=True,
                last_modify_date=datetime.datetime.now()
            )
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
    
    async def get_pending_scenarios_async(self, limit: int = 10) -> List[InterviewScenario]:
        """
        获取待处理的面试场景列表
        
        Args:
            limit: 限制数量
            
        Returns:
            待处理的列表
        """
        query = (
            select(InterviewScenario)
            .where(InterviewScenario.status == InterviewScenarioStatus.PENDING)
            .order_by(InterviewScenario.create_date)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())