import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, update, or_

from app.modules.tools.datadesign.entities import TableRelation
from app.core.utils.snowflake import generate_id

class TableRelationRepository:
    """表关系仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        构造函数

        Args:
            db (AsyncSession): 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[TableRelation]:
        """
        获取表关系

        Args:
            id (int): 表关系ID

        Returns:
            Optional[TableRelation]: 表关系实体
        """
        result = await self.db.execute(select(TableRelation).filter(TableRelation.id == id))
        return result.scalars().first()

    async def get_by_task_id_async(self, task_id: int) -> List[TableRelation]:
        """
        获取任务的所有表关系

        Args:
            task_id (int): 任务ID

        Returns:
            List[TableRelation]: 表关系实体列表
        """
        stmt = select(TableRelation).filter(TableRelation.task_id == task_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_by_table_id_async(self, table_id: int) -> List[TableRelation]:
        """
        获取表的所有关系 (作为父表或子表)

        Args:
            table_id (int): 表ID

        Returns:
            List[TableRelation]: 表关系实体列表
        """
        stmt = select(TableRelation).filter(
            or_(TableRelation.parent_table_id == table_id, TableRelation.child_table_id == table_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def add_async(self, relation: TableRelation) -> int:
        """
        新增表关系

        Args:
            relation (TableRelation): 表关系实体

        Returns:
            int: 新增关系的ID
        """
        relation.id = generate_id()
        now = datetime.datetime.now()
        relation.create_date = now
        relation.last_modify_date = now
        self.db.add(relation)
        await self.db.flush()
        return relation.id

    async def add_batch_async(self, relations: List[TableRelation]) -> bool:
        """
        批量新增表关系 (ID通常在外部已通过 generate_id() 赋值)

        Args:
            relations (List[TableRelation]): 表关系实体列表

        Returns:
            bool: 操作结果
        """
        now = datetime.datetime.now()
        for rel_item in relations:
            if not rel_item.id: # Ensure ID is set
                 rel_item.id = generate_id()
            rel_item.create_date = now
            rel_item.last_modify_date = now
        
        self.db.add_all(relations)
        await self.db.flush()
        return True

    async def update_async(self, relation: TableRelation) -> bool:
        """
        更新表关系

        Args:
            relation (TableRelation): 表关系实体

        Returns:
            bool: 操作结果
        """
        relation.last_modify_date = datetime.datetime.now()
        # self.db.add(relation) # For detached objects
        # await self.db.flush()
        stmt = (
            update(TableRelation)
            .where(TableRelation.id == relation.id)
            .values(
                task_id=relation.task_id,
                parent_table_id=relation.parent_table_id,
                child_table_id=relation.child_table_id,
                relation_type=relation.relation_type,
                description=relation.description,
                last_modify_date=relation.last_modify_date
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_async(self, id: int) -> bool:
        """
        删除表关系

        Args:
            id (int): 表关系ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(TableRelation).where(TableRelation.id == id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_by_task_id_async(self, task_id: int) -> bool:
        """
        删除任务的所有表关系

        Args:
            task_id (int): 任务ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(TableRelation).where(TableRelation.task_id == task_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0
