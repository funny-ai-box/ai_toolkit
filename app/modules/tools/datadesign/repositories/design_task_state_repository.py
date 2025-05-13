import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, update

from app.modules.tools.datadesign.entities import DesignTaskState
from app.core.utils.snowflake import generate_id

class DesignTaskStateRepository:
    """设计任务状态仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        构造函数

        Args:
            db (AsyncSession): 数据库会话
        """
        self.db = db

    async def get_by_task_id_async(self, task_id: int) -> Optional[DesignTaskState]:
        """
        获取任务状态

        Args:
            task_id (int): 任务ID

        Returns:
            Optional[DesignTaskState]: 任务状态实体
        """
        result = await self.db.execute(select(DesignTaskState).filter(DesignTaskState.task_id == task_id))
        return result.scalars().first()

    async def create_or_update_async(self, task_state: DesignTaskState) -> bool:
        """
        创建或更新任务状态

        Args:
            task_state (DesignTaskState): 任务状态实体

        Returns:
            bool: 操作结果
        """
        existing_state = await self.get_by_task_id_async(task_state.task_id)
        now = datetime.datetime.now()

        if existing_state is None:
            task_state.id = generate_id()
            task_state.create_date = now
            task_state.last_modify_date = now
            self.db.add(task_state)
            await self.db.flush()
            return True
        else:
            existing_state.latest_business_analysis_id = task_state.latest_business_analysis_id if task_state.latest_business_analysis_id is not None else existing_state.latest_business_analysis_id
            existing_state.latest_database_design_id = task_state.latest_database_design_id if task_state.latest_database_design_id is not None else existing_state.latest_database_design_id
            existing_state.latest_json_structure_id = task_state.latest_json_structure_id if task_state.latest_json_structure_id is not None else existing_state.latest_json_structure_id
            existing_state.last_modify_date = now
            
            stmt = (
                update(DesignTaskState)
                .where(DesignTaskState.id == existing_state.id)
                .values(
                    latest_business_analysis_id=existing_state.latest_business_analysis_id,
                    latest_database_design_id=existing_state.latest_database_design_id,
                    latest_json_structure_id=existing_state.latest_json_structure_id,
                    last_modify_date=existing_state.last_modify_date
                )
            )
            result = await self.db.execute(stmt)
            return result.rowcount > 0

    async def _update_latest_id_async(self, task_id: int, new_id: int, field_name: str) -> bool:
        """辅助方法更新特定ID"""
        state = await self.get_by_task_id_async(task_id)
        now = datetime.datetime.now()

        if state is None:
            state = DesignTaskState(
                id=generate_id(),
                task_id=task_id,
                create_date=now,
                last_modify_date=now
            )
            setattr(state, field_name, new_id)
            self.db.add(state)
            await self.db.flush()
            return True
        else:
            setattr(state, field_name, new_id)
            state.last_modify_date = now
            
            update_values = {field_name: new_id, "last_modify_date": now}
            stmt = (
                update(DesignTaskState)
                .where(DesignTaskState.id == state.id)
                .values(**update_values)
            )
            result = await self.db.execute(stmt)
            return result.rowcount > 0


    async def update_latest_business_analysis_id_async(self, task_id: int, business_analysis_id: int) -> bool:
        """更新任务最新业务分析ID"""
        return await self._update_latest_id_async(task_id, business_analysis_id, "latest_business_analysis_id")

    async def update_latest_database_design_id_async(self, task_id: int, database_design_id: int) -> bool:
        """更新任务最新数据库设计ID"""
        return await self._update_latest_id_async(task_id, database_design_id, "latest_database_design_id")

    async def update_latest_json_structure_id_async(self, task_id: int, json_structure_id: int) -> bool:
        """更新任务最新JSON结构ID"""
        return await self._update_latest_id_async(task_id, json_structure_id, "latest_json_structure_id")

    async def delete_by_task_id_async(self, task_id: int) -> bool:
        """
        删除任务状态

        Args:
            task_id (int): 任务ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(DesignTaskState).where(DesignTaskState.task_id == task_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0