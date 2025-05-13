import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, update

from app.modules.tools.datadesign.entities import IndexField, IndexDesign # IndexDesign for DeleteByTaskIdAsync
from app.core.utils.snowflake import generate_id

class IndexFieldRepository:
    """索引字段仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        构造函数

        Args:
            db (AsyncSession): 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[IndexField]:
        """
        获取索引字段

        Args:
            id (int): 索引字段ID

        Returns:
            Optional[IndexField]: 索引字段实体
        """
        result = await self.db.execute(select(IndexField).filter(IndexField.id == id))
        return result.scalars().first()

    async def get_by_index_id_async(self, index_id: int) -> List[IndexField]:
        """
        获取索引的所有字段

        Args:
            index_id (int): 索引ID

        Returns:
            List[IndexField]: 索引字段实体列表 (按sort_order排序)
        """
        stmt = select(IndexField).filter(IndexField.index_id == index_id).order_by(IndexField.sort_order)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def add_async(self, index_field: IndexField) -> int:
        """
        新增索引字段

        Args:
            index_field (IndexField): 索引字段实体

        Returns:
            int: 新增索引字段的ID
        """
        index_field.id = generate_id()
        now = datetime.datetime.now()
        index_field.create_date = now
        index_field.last_modify_date = now
        self.db.add(index_field)
        await self.db.flush()
        return index_field.id

    async def add_batch_async(self, index_fields: List[IndexField]) -> bool:
        """
        批量新增索引字段 (ID通常在外部已通过 generate_id() 赋值)

        Args:
            index_fields (List[IndexField]): 索引字段实体列表

        Returns:
            bool: 操作结果
        """
        now = datetime.datetime.now()
        for item in index_fields:
            if not item.id: # Ensure ID is set
                 item.id = generate_id()
            item.create_date = now
            item.last_modify_date = now
        
        self.db.add_all(index_fields)
        await self.db.flush()
        return True

    async def update_async(self, index_field: IndexField) -> bool:
        """
        更新索引字段

        Args:
            index_field (IndexField): 索引字段实体

        Returns:
            bool: 操作结果
        """
        index_field.last_modify_date = datetime.datetime.now()
        # self.db.add(index_field) # For detached objects
        # await self.db.flush()
        stmt = (
            update(IndexField)
            .where(IndexField.id == index_field.id)
            .values(
                index_id=index_field.index_id,
                field_id=index_field.field_id,
                sort_order=index_field.sort_order,
                sort_direction=index_field.sort_direction,
                last_modify_date=index_field.last_modify_date
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_async(self, id: int) -> bool:
        """
        删除索引字段

        Args:
            id (int): 索引字段ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(IndexField).where(IndexField.id == id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_by_index_id_async(self, index_id: int) -> bool:
        """
        删除索引的所有字段

        Args:
            index_id (int): 索引ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(IndexField).where(IndexField.index_id == index_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_by_task_id_async(self, task_id: int) -> bool:
        """
        删除任务的所有索引字段

        Args:
            task_id (int): 任务ID

        Returns:
            bool: 操作结果
        """
        # First, get all index IDs for the task
        index_ids_stmt = select(IndexDesign.id).filter(IndexDesign.task_id == task_id)
        index_ids_result = await self.db.execute(index_ids_stmt)
        index_ids = index_ids_result.scalars().all()

        if not index_ids:
            return True # No indexes, so no index fields to delete

        # Delete IndexField entries where IndexId is in the retrieved list
        stmt = delete(IndexField).where(IndexField.index_id.in_(index_ids))
        result = await self.db.execute(stmt)
        return result.rowcount >= 0 # True if deleted or none to delete