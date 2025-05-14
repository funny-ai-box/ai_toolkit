import datetime
from typing import List, Tuple, Optional, Dict, Any, Union
from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.core.utils.snowflake import generate_id
from app.modules.tools.survey.models import (
    SurveyTask, SurveyTab, SurveyField, SurveyResponse, 
    SurveyResponseDetail, SurveyDesignHistory
)
from app.modules.tools.survey.enums import SurveyTaskStatus, ChatRoleType


class SurveyTaskRepository:
    """问卷任务仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        初始化问卷任务仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, task_id: int) -> Optional[SurveyTask]:
        """
        获取问卷任务
        
        Args:
            task_id: 问卷任务ID
            
        Returns:
            问卷任务对象或None
        """
        result = await self.db.execute(
            select(SurveyTask).where(SurveyTask.id == task_id)
        )
        return result.scalars().first()

    async def get_by_user_id_async(self, user_id: int, page_index: int = 1, page_size: int = 20) -> Tuple[List[SurveyTask], int]:
        """
        获取用户的所有问卷任务

        Args:
            user_id: 用户ID
            page_index: 页码，从1开始
            page_size: 每页大小
            
        Returns:
            问卷任务列表和总数
        """
        # 确保页码和每页数量有效
        if page_index < 1:
            page_index = 1
        if page_size < 1:
            page_size = 20

        # 计算跳过的记录数
        skip = (page_index - 1) * page_size

        # 查询满足条件的记录总数
        count_stmt = select(func.count()).select_from(SurveyTask).where(SurveyTask.user_id == user_id)
        total_count_result = await self.db.execute(count_stmt)
        total_count = total_count_result.scalar()

        # 查询分页数据
        stmt = (
            select(SurveyTask)
            .where(SurveyTask.user_id == user_id)
            .order_by(SurveyTask.id.desc())
            .offset(skip)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = result.scalars().all()

        return list(items), total_count

    async def add_async(self, task: SurveyTask) -> bool:
        """
        新增问卷任务
        
        Args:
            task: 问卷任务对象
            
        Returns:
            操作结果
        """
        if not task.id:
            task.id = generate_id()
        now = datetime.datetime.now()
        task.create_date = now
        task.last_modify_date = now
        
        self.db.add(task)
        await self.db.flush()
        return True

    async def update_async(self, task: SurveyTask) -> bool:
        """
        更新问卷任务
        
        Args:
            task: 问卷任务对象
            
        Returns:
            操作结果
        """
        task.last_modify_date = datetime.datetime.now()
        
        await self.db.merge(task)
        await self.db.flush()
        return True

    async def delete_async(self, task_id: int) -> bool:
        """
        删除问卷任务
        
        Args:
            task_id: 问卷任务ID
            
        Returns:
            操作结果
        """
        stmt = delete(SurveyTask).where(SurveyTask.id == task_id)
        await self.db.execute(stmt)
        await self.db.flush()
        return True

    async def get_by_share_code_async(self, share_code: str) -> Optional[SurveyTask]:
        """
        根据共享码获取问卷任务
        
        Args:
            share_code: 共享码
            
        Returns:
            问卷任务对象或None
        """
        result = await self.db.execute(
            select(SurveyTask).where(SurveyTask.share_code == share_code)
        )
        return result.scalars().first()

    async def update_status_async(self, task_id: int, status: SurveyTaskStatus) -> bool:
        """
        更新问卷任务状态
        
        Args:
            task_id: 问卷任务ID
            status: 状态
            
        Returns:
            操作结果
        """
        now = datetime.datetime.now()
        stmt = (
            update(SurveyTask)
            .where(SurveyTask.id == task_id)
            .values(status=status, last_modify_date=now)
        )
        await self.db.execute(stmt)
        await self.db.flush()
        return True


class SurveyTabRepository:
    """问卷Tab页仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        初始化问卷Tab页仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, tab_id: int) -> Optional[SurveyTab]:
        """
        获取问卷Tab页
        
        Args:
            tab_id: Tab页ID
            
        Returns:
            Tab页对象或None
        """
        result = await self.db.execute(
            select(SurveyTab).where(SurveyTab.id == tab_id)
        )
        return result.scalars().first()

    async def get_by_task_id_async(self, task_id: int) -> List[SurveyTab]:
        """
        获取问卷的所有Tab页
        
        Args:
            task_id: 问卷任务ID
            
        Returns:
            Tab页列表
        """
        result = await self.db.execute(
            select(SurveyTab)
            .where(SurveyTab.task_id == task_id)
            .order_by(SurveyTab.order_no)
        )
        return list(result.scalars().all())

    async def add_async(self, tab: SurveyTab) -> bool:
        """
        新增Tab页
        
        Args:
            tab: Tab页对象
            
        Returns:
            操作结果
        """
        if not tab.id:
            tab.id = generate_id()
        now = datetime.datetime.now()
        tab.create_date = now
        tab.last_modify_date = now
        
        self.db.add(tab)
        await self.db.flush()
        return True

    async def add_batch_async(self, tabs: List[SurveyTab]) -> bool:
        """
        批量新增Tab页
        
        Args:
            tabs: Tab页列表
            
        Returns:
            操作结果
        """
        # 确保所有Tab页都有ID和时间戳
        now = datetime.datetime.now()
        for tab in tabs:
            if not tab.id:
                tab.id = generate_id()
            tab.create_date = now
            tab.last_modify_date = now
        
        self.db.add_all(tabs)
        await self.db.flush()
        return True

    async def update_async(self, tab: SurveyTab) -> bool:
        """
        更新Tab页
        
        Args:
            tab: Tab页对象
            
        Returns:
            操作结果
        """
        tab.last_modify_date = datetime.datetime.now()
        
        await self.db.merge(tab)
        await self.db.flush()
        return True

    async def delete_async(self, tab_id: int) -> bool:
        """
        删除Tab页
        
        Args:
            tab_id: Tab页ID
            
        Returns:
            操作结果
        """
        stmt = delete(SurveyTab).where(SurveyTab.id == tab_id)
        await self.db.execute(stmt)
        await self.db.flush()
        return True

    async def delete_by_task_id_async(self, task_id: int) -> bool:
        """
        删除问卷的所有Tab页
        
        Args:
            task_id: 问卷任务ID
            
        Returns:
            操作结果
        """
        stmt = delete(SurveyTab).where(SurveyTab.task_id == task_id)
        await self.db.execute(stmt)
        await self.db.flush()
        return True


class SurveyFieldRepository:
    """问卷字段仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        初始化问卷字段仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, field_id: int) -> Optional[SurveyField]:
        """
        获取问卷字段
        
        Args:
            field_id: 字段ID
            
        Returns:
            字段对象或None
        """
        result = await self.db.execute(
            select(SurveyField).where(SurveyField.id == field_id)
        )
        return result.scalars().first()

    async def get_by_task_id_async(self, task_id: int) -> List[SurveyField]:
        """
        获取问卷的所有字段
        
        Args:
            task_id: 问卷任务ID
            
        Returns:
            字段列表
        """
        result = await self.db.execute(
            select(SurveyField)
            .where(SurveyField.task_id == task_id)
            .order_by(SurveyField.tab_id, SurveyField.order_no)
        )
        return list(result.scalars().all())

    async def get_by_tab_id_async(self, tab_id: int) -> List[SurveyField]:
        """
        获取Tab页的所有字段
        
        Args:
            tab_id: Tab页ID
            
        Returns:
            字段列表
        """
        result = await self.db.execute(
            select(SurveyField)
            .where(SurveyField.tab_id == tab_id)
            .order_by(SurveyField.order_no)
        )
        return list(result.scalars().all())

    async def add_async(self, field: SurveyField) -> bool:
        """
        新增字段
        
        Args:
            field: 字段对象
            
        Returns:
            操作结果
        """
        if not field.id:
            field.id = generate_id()
        now = datetime.datetime.now()
        field.create_date = now
        field.last_modify_date = now
        
        self.db.add(field)
        await self.db.flush()
        return True

    async def add_batch_async(self, fields: List[SurveyField]) -> bool:
        """
        批量新增字段
        
        Args:
            fields: 字段列表
            
        Returns:
            操作结果
        """
        # 确保所有字段都有ID和时间戳
        now = datetime.datetime.now()
        for field in fields:
            if not field.id:
                field.id = generate_id()
            field.create_date = now
            field.last_modify_date = now
        
        self.db.add_all(fields)
        await self.db.flush()
        return True

    async def update_async(self, field: SurveyField) -> bool:
        """
        更新字段
        
        Args:
            field: 字段对象
            
        Returns:
            操作结果
        """
        field.last_modify_date = datetime.datetime.now()
        
        await self.db.merge(field)
        await self.db.flush()
        return True

    async def delete_async(self, field_id: int) -> bool:
        """
        删除字段
        
        Args:
            field_id: 字段ID
            
        Returns:
            操作结果
        """
        stmt = delete(SurveyField).where(SurveyField.id == field_id)
        await self.db.execute(stmt)
        await self.db.flush()
        return True

    async def delete_by_task_id_async(self, task_id: int) -> bool:
        """
        删除问卷的所有字段
        
        Args:
            task_id: 问卷任务ID
            
        Returns:
            操作结果
        """
        stmt = delete(SurveyField).where(SurveyField.task_id == task_id)
        await self.db.execute(stmt)
        await self.db.flush()
        return True

    async def delete_by_tab_id_async(self, tab_id: int) -> bool:
        """
        删除Tab页的所有字段
        
        Args:
            tab_id: Tab页ID
            
        Returns:
            操作结果
        """
        stmt = delete(SurveyField).where(SurveyField.tab_id == tab_id)
        await self.db.execute(stmt)
        await self.db.flush()
        return True


class SurveyDesignHistoryRepository:
    """问卷设计历史仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        初始化问卷设计历史仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db

    async def get_by_task_id_async(self, task_id: int) -> List[SurveyDesignHistory]:
        """
        获取问卷设计历史
        
        Args:
            task_id: 问卷任务ID
            
        Returns:
            设计历史列表
        """
        result = await self.db.execute(
            select(SurveyDesignHistory)
            .where(SurveyDesignHistory.task_id == task_id)
            .order_by(SurveyDesignHistory.create_date)
        )
        return list(result.scalars().all())

    async def get_by_task_id_paginated_async(self, task_id: int, page_index: int = 1, page_size: int = 20) -> Tuple[List[SurveyDesignHistory], int]:
        """
        获取问卷设计历史（分页）
        
        Args:
            task_id: 问卷任务ID
            page_index: 页码，从1开始
            page_size: 每页大小
            
        Returns:
            设计历史列表和总数
        """
        # 确保页码和每页数量有效
        if page_index < 1:
            page_index = 1
        if page_size < 1:
            page_size = 20

        # 计算跳过的记录数
        skip = (page_index - 1) * page_size

        # 查询满足条件的记录总数
        count_stmt = select(func.count()).select_from(SurveyDesignHistory).where(SurveyDesignHistory.task_id == task_id)
        total_count_result = await self.db.execute(count_stmt)
        total_count = total_count_result.scalar()

        # 查询分页数据
        stmt = (
            select(SurveyDesignHistory)
            .where(SurveyDesignHistory.task_id == task_id)
            .order_by(SurveyDesignHistory.create_date.desc())
            .offset(skip)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = result.scalars().all()

        # 再次排序，确保按ID升序返回
        return sorted(list(items), key=lambda x: x.id), total_count

    async def add_async(self, history: SurveyDesignHistory) -> bool:
        """
        添加设计历史
        
        Args:
            history: 设计历史对象
            
        Returns:
            操作结果
        """
        if not history.id:
            history.id = generate_id()
        now = datetime.datetime.now()
        history.create_date = now
        
        self.db.add(history)
        await self.db.flush()
        return True

    async def delete_by_task_id_async(self, task_id: int) -> bool:
        """
        删除问卷的所有设计历史
        
        Args:
            task_id: 问卷任务ID
            
        Returns:
            操作结果
        """
        stmt = delete(SurveyDesignHistory).where(SurveyDesignHistory.task_id == task_id)
        await self.db.execute(stmt)
        await self.db.flush()
        return True

    async def get_latest_complete_json_config_async(self, task_id: int) -> Optional[str]:
        """
        获取问卷的最新完整JSON配置
        
        Args:
            task_id: 问卷任务ID
            
        Returns:
            JSON配置，如果不存在则返回None
        """
        # 查找包含完整JSON配置的最新记录
        stmt = (
            select(SurveyDesignHistory)
            .where(
                SurveyDesignHistory.task_id == task_id,
                SurveyDesignHistory.complete_json_config.is_not(None),
                SurveyDesignHistory.complete_json_config != ""
            )
            .order_by(SurveyDesignHistory.create_date.desc())
        )
        result = await self.db.execute(stmt)
        history = result.scalars().first()
        
        return history.complete_json_config if history else None

    async def get_recent_history_async(self, task_id: int, count: int) -> List[SurveyDesignHistory]:
        """
        获取问卷的最近N条对话历史
        
        Args:
            task_id: 问卷任务ID
            count: 返回的历史记录数量
            
        Returns:
            对话历史列表，按时间正序排列
        """
        stmt = (
            select(SurveyDesignHistory)
            .where(SurveyDesignHistory.task_id == task_id)
            .order_by(SurveyDesignHistory.create_date.desc())
            .limit(count)
        )
        result = await self.db.execute(stmt)
        histories = list(result.scalars().all())
        
        # 按时间正序排列
        return sorted(histories, key=lambda x: x.create_date)

    async def update_complete_json_config_async(self, history_id: int, json_config: str) -> bool:
        """
        更新设计历史的完整JSON配置
        
        Args:
            history_id: 历史记录ID
            json_config: 完整JSON配置
            
        Returns:
            操作结果
        """
        stmt = (
            update(SurveyDesignHistory)
            .where(SurveyDesignHistory.id == history_id)
            .values(complete_json_config=json_config)
        )
        await self.db.execute(stmt)
        await self.db.flush()
        return True


class SurveyResponseRepository:
    """问卷回答仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        初始化问卷回答仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, response_id: int) -> Optional[SurveyResponse]:
        """
        获取问卷回答
        
        Args:
            response_id: 回答ID
            
        Returns:
            回答对象或None
        """
        result = await self.db.execute(
            select(SurveyResponse).where(SurveyResponse.id == response_id)
        )
        return result.scalars().first()

    async def get_by_task_id_async(self, task_id: int, page_index: int = 1, page_size: int = 20) -> Tuple[List[SurveyResponse], int]:
        """
        获取问卷的所有回答
        
        Args:
            task_id: 问卷任务ID
            page_index: 页码，从1开始
            page_size: 每页大小
            
        Returns:
            回答列表和总数
        """
        # 确保页码和每页数量有效
        if page_index < 1:
            page_index = 1
        if page_size < 1:
            page_size = 20

        # 计算跳过的记录数
        skip = (page_index - 1) * page_size

        # 查询满足条件的记录总数
        count_stmt = select(func.count()).select_from(SurveyResponse).where(SurveyResponse.task_id == task_id)
        total_count_result = await self.db.execute(count_stmt)
        total_count = total_count_result.scalar()

        # 查询分页数据
        stmt = (
            select(SurveyResponse)
            .where(SurveyResponse.task_id == task_id)
            .order_by(SurveyResponse.submit_date.desc())
            .offset(skip)
            .limit(page_size)
        )
        result = await self.db.execute(stmt)
        items = result.scalars().all()

        return list(items), total_count

    async def add_async(self, response: SurveyResponse) -> bool:
        """
        添加回答
        
        Args:
            response: 回答对象
            
        Returns:
            操作结果
        """
        if not response.id:
            response.id = generate_id()
        
        self.db.add(response)
        await self.db.flush()
        return True

    async def delete_by_id_async(self, response_id: int) -> bool:
        """
        删除回答
        
        Args:
            response_id: 回答ID
            
        Returns:
            操作结果
        """
        stmt = delete(SurveyResponse).where(SurveyResponse.id == response_id)
        await self.db.execute(stmt)
        await self.db.flush()
        return True

    async def delete_by_task_id_async(self, task_id: int) -> bool:
        """
        删除问卷的所有回答
        
        Args:
            task_id: 问卷任务ID
            
        Returns:
            操作结果
        """
        stmt = delete(SurveyResponse).where(SurveyResponse.task_id == task_id)
        await self.db.execute(stmt)
        await self.db.flush()
        return True

    async def get_response_count_async(self, task_id: int) -> int:
        """
        获取问卷回答统计
        
        Args:
            task_id: 问卷任务ID
            
        Returns:
            回答总数
        """
        stmt = select(func.count()).select_from(SurveyResponse).where(SurveyResponse.task_id == task_id)
        result = await self.db.execute(stmt)
        return result.scalar()


class SurveyResponseDetailRepository:
    """问卷回答详情仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        初始化问卷回答详情仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db

    async def get_by_response_id_async(self, response_id: int) -> List[SurveyResponseDetail]:
        """
        获取回答详情
        
        Args:
            response_id: 回答ID
            
        Returns:
            回答详情列表
        """
        result = await self.db.execute(
            select(SurveyResponseDetail).where(SurveyResponseDetail.response_id == response_id)
        )
        return list(result.scalars().all())

    async def get_by_task_id_async(self, task_id: int) -> List[SurveyResponseDetail]:
        """
        获取问卷的所有回答详情
        
        Args:
            task_id: 问卷任务ID
            
        Returns:
            回答详情列表
        """
        result = await self.db.execute(
            select(SurveyResponseDetail).where(SurveyResponseDetail.task_id == task_id)
        )
        return list(result.scalars().all())

    async def add_batch_async(self, details: List[SurveyResponseDetail]) -> bool:
        """
        批量添加回答详情
        
        Args:
            details: 回答详情列表
            
        Returns:
            操作结果
        """
        # 确保所有详情都有ID和时间戳
        now = datetime.datetime.now()
        for detail in details:
            if not detail.id:
                detail.id = generate_id()
            detail.create_date = now
        
        self.db.add_all(details)
        await self.db.flush()
        return True

    async def get_field_values_async(self, task_id: int, field_id: int) -> List[Optional[str]]:
        """
        获取字段的所有回答值
        
        Args:
            task_id: 问卷任务ID
            field_id: 字段ID
            
        Returns:
            回答值列表
        """
        stmt = (
            select(SurveyResponseDetail.value)
            .where(
                SurveyResponseDetail.task_id == task_id,
                SurveyResponseDetail.field_id == field_id
            )
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    async def delete_by_response_id_async(self, response_id: int) -> bool:
        """
        删除回答的所有详情
        
        Args:
            response_id: 回答ID
            
        Returns:
            操作结果
        """
        stmt = delete(SurveyResponseDetail).where(SurveyResponseDetail.response_id == response_id)
        await self.db.execute(stmt)
        await self.db.flush()
        return True

    async def delete_by_task_id_async(self, task_id: int) -> bool:
        """
        删除问卷的所有回答详情
        
        Args:
            task_id: 问卷任务ID
            
        Returns:
            操作结果
        """
        stmt = delete(SurveyResponseDetail).where(SurveyResponseDetail.task_id == task_id)
        await self.db.execute(stmt)
        await self.db.flush()
        return True