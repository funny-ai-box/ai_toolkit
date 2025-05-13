import datetime
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, update, desc, func

from app.modules.tools.datadesign.entities import DesignTask
from app.core.utils.snowflake import generate_id

class DesignTaskRepository:
    """设计任务仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        构造函数

        Args:
            db (AsyncSession): 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[DesignTask]:
        """
        获取设计任务

        Args:
            id (int): 任务ID

        Returns:
            Optional[DesignTask]: 设计任务实体
        """
        result = await self.db.execute(select(DesignTask).filter(DesignTask.id == id))
        return result.scalars().first()

    async def get_by_user_id_async(self, user_id: int) -> List[DesignTask]:
        """
        获取用户的所有设计任务

        Args:
            user_id (int): 用户ID

        Returns:
            List[DesignTask]: 设计任务实体列表, 按最后修改时间降序排列
        """
        stmt = select(DesignTask).filter(DesignTask.user_id == user_id).order_by(desc(DesignTask.last_modify_date))
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_paginated_by_user_id_async(
        self, user_id: int, page_index: int, page_size: int
    ) -> Tuple[List[DesignTask], int]:
        """
        分页获取用户的设计任务

        Args:
            user_id (int): 用户ID
            page_index (int): 页码
            page_size (int): 每页大小

        Returns:
            Tuple[List[DesignTask], int]: 设计任务列表和总数
        """
        if page_index < 1:
            page_index = 1
        if page_size < 1:
            page_size = 20 # Default page size

        offset = (page_index - 1) * page_size

        # Query for total count
        count_stmt = select(func.count(DesignTask.id)).filter(DesignTask.user_id == user_id)
        total_count_result = await self.db.execute(count_stmt)
        total_count = total_count_result.scalar_one()

        # Query for paginated items
        items_stmt = (
            select(DesignTask)
            .filter(DesignTask.user_id == user_id)
            .order_by(desc(DesignTask.last_modify_date))
            .offset(offset)
            .limit(page_size)
        )
        items_result = await self.db.execute(items_stmt)
        items = items_result.scalars().all()

        return items, total_count

    async def add_async(self, task: DesignTask) -> int:
        """
        新增设计任务

        Args:
            task (DesignTask): 设计任务实体

        Returns:
            int: 新增任务的ID
        """
        task.id = generate_id()
        now = datetime.datetime.now()
        task.create_date = now
        task.last_modify_date = now
        self.db.add(task)
        await self.db.flush()
        return task.id

    async def update_async(self, task: DesignTask) -> bool:
        """
        更新设计任务

        Args:
            task (DesignTask): 设计任务实体

        Returns:
            bool: 操作结果
        """
        task.last_modify_date = datetime.datetime.now()
        # self.db.add(task) # For detached object or merge
        # await self.db.flush()
        stmt = (
            update(DesignTask)
            .where(DesignTask.id == task.id)
            .values(
                task_name=task.task_name,
                description=task.description,
                last_modify_date=task.last_modify_date
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0


    async def delete_async(self, id: int) -> bool:
        """
        删除设计任务

        Args:
            id (int): 任务ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(DesignTask).where(DesignTask.id == id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0