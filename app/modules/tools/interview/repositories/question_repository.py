"""
面试问题仓储实现

提供面试问题实体的数据访问操作，包括添加、查询、更新和删除等功能。
"""
import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.utils.snowflake import generate_id
from app.modules.tools.interview.models import InterviewQuestion
from app.modules.tools.interview.enums import QuestionDifficulty


class InterviewQuestionRepository:
    """面试问题仓储"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化面试问题仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def add_async(self, question: InterviewQuestion) -> InterviewQuestion:
        """
        添加问题
        
        Args:
            question: 问题实体
            
        Returns:
            成功添加的问题实体
        """
        question.id = generate_id()
        question.create_date = datetime.datetime.now()
        
        self.db.add(question)
        await self.db.flush()
        return question
    
    async def batch_add_async(self, questions: List[InterviewQuestion]) -> bool:
        """
        批量添加问题
        
        Args:
            questions: 问题实体列表
            
        Returns:
            添加结果
        """
        if not questions:
            return False
        
        now = datetime.datetime.now()
        for question in questions:
            question.id = generate_id()
            question.create_date = now
            self.db.add(question)
        
        await self.db.flush()
        return True
    
    async def get_by_id_async(self, id: int) -> Optional[InterviewQuestion]:
        """
        获取指定ID的问题
        
        Args:
            id: 问题ID
            
        Returns:
            问题实体
        """
        query = select(InterviewQuestion).where(InterviewQuestion.id == id)
        result = await self.db.execute(query)
        return result.scalars().first()
    
    async def get_questions_async(
        self,
        scenario_id: int,
        job_position_id: Optional[int] = None,
        difficulty: Optional[QuestionDifficulty] = None,
        page_index: int = 1,
        page_size: int = 20
    ) -> Tuple[List[InterviewQuestion], int]:
        """
        获取场景下的问题列表
        
        Args:
            scenario_id: 场景ID
            job_position_id: 职位ID（可选）
            difficulty: 问题难度（可选）
            page_index: 页码
            page_size: 每页数量
            
        Returns:
            问题列表和总数
        """
        # 确保页码和每页数量有效
        if page_index < 1:
            page_index = 1
        if page_size < 1:
            page_size = 20
        
        # 计算跳过的记录数
        skip = (page_index - 1) * page_size
        
        # 构建查询条件
        query = select(InterviewQuestion).where(InterviewQuestion.scenario_id == scenario_id)
        
        if job_position_id:
            query = query.where(InterviewQuestion.job_position_id == job_position_id)
        
        if difficulty:
            query = query.where(InterviewQuestion.difficulty == difficulty)
        
        # 查询满足条件的记录总数
        count_query = select(func.count()).select_from(query.subquery())
        total_count = await self.db.scalar(count_query)
        
        # 查询分页数据
        query = query.order_by(InterviewQuestion.sort_order).offset(skip).limit(page_size)
        result = await self.db.execute(query)
        items = result.scalars().all()
        
        return list(items), total_count or 0
    
    async def get_questions_by_position_async(self, scenario_id: int, job_position_id: int) -> List[InterviewQuestion]:
        """
        获取场景下某职位的所有问题
        
        Args:
            scenario_id: 场景ID
            job_position_id: 职位ID
            
        Returns:
            问题实体列表
        """
        query = select(InterviewQuestion).where(
            InterviewQuestion.scenario_id == scenario_id,
            InterviewQuestion.job_position_id == job_position_id
        ).order_by(InterviewQuestion.sort_order)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_async(self, question: InterviewQuestion) -> bool:
        """
        更新问题
        
        Args:
            question: 问题实体
            
        Returns:
            更新结果
        """
        await self.db.flush()
        return True
    
    async def delete_async(self, id: int) -> bool:
        """
        删除问题
        
        Args:
            id: 问题ID
            
        Returns:
            删除结果
        """
        stmt = (
            update(InterviewQuestion)
            .where(InterviewQuestion.id == id)
            .values(is_deleted=True)
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0
    
    async def delete_by_scenario_id_async(self, scenario_id: int) -> bool:
        """
        删除场景的所有问题
        
        Args:
            scenario_id: 场景ID
            
        Returns:
            删除结果
        """
        stmt = (
            update(InterviewQuestion)
            .where(InterviewQuestion.scenario_id == scenario_id)
            .values(is_deleted=True)
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0
    
    async def delete_by_scenario_job_id_async(self, scenario_id: int, job_position_id: int) -> bool:
        """
        删除场景对应职位的问题
        
        Args:
            scenario_id: 场景ID
            job_position_id: 职位Id
            
        Returns:
            删除结果
        """
        stmt = (
            update(InterviewQuestion)
            .where(
                InterviewQuestion.scenario_id == scenario_id,
                InterviewQuestion.job_position_id == job_position_id
            )
            .values(is_deleted=True)
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0