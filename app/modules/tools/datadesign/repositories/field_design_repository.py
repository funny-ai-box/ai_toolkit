import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, update

from app.modules.tools.datadesign.entities import FieldDesign
from app.core.utils.snowflake import generate_id

class FieldDesignRepository:
    """字段设计仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        构造函数

        Args:
            db (AsyncSession): 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[FieldDesign]:
        """
        获取字段设计

        Args:
            id (int): 字段设计ID

        Returns:
            Optional[FieldDesign]: 字段设计实体
        """
        result = await self.db.execute(select(FieldDesign).filter(FieldDesign.id == id))
        return result.scalars().first()

    async def get_by_table_id_async(self, table_id: int) -> List[FieldDesign]:
        """
        获取表的所有字段设计

        Args:
            table_id (int): 表ID

        Returns:
            List[FieldDesign]: 字段设计实体列表 (按sort_order排序)
        """
        stmt = select(FieldDesign).filter(FieldDesign.table_id == table_id).order_by(FieldDesign.sort_order)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_by_task_id_async(self, task_id: int) -> List[FieldDesign]:
        """
        获取任务的所有字段设计

        Args:
            task_id (int): 任务ID

        Returns:
            List[FieldDesign]: 字段设计实体列表
        """
        stmt = select(FieldDesign).filter(FieldDesign.task_id == task_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def add_async(self, field: FieldDesign) -> int:
        """
        新增字段设计

        Args:
            field (FieldDesign): 字段设计实体

        Returns:
            int: 新增字段的ID
        """
        field.id = generate_id()
        now = datetime.datetime.now()
        field.create_date = now
        field.last_modify_date = now
        self.db.add(field)
        await self.db.flush()
        return field.id

    async def add_batch_async(self, fields: List[FieldDesign]) -> bool:
        """
        批量新增字段设计 (ID通常在外部已通过 generate_id() 赋值)

        Args:
            fields (List[FieldDesign]): 字段设计实体列表

        Returns:
            bool: 操作结果
        """
        now = datetime.datetime.now()
        for field_item in fields:
            # Assuming ID is pre-assigned if needed, or let DB assign if autoincrement
            # If ID is from snowflake, it should be assigned before calling this
            if not field_item.id: # Ensure ID is set if not auto-incrementing PK from DB
                 field_item.id = generate_id()
            field_item.create_date = now
            field_item.last_modify_date = now
        
        self.db.add_all(fields)
        await self.db.flush()
        return True

    async def update_async(self, field: FieldDesign) -> bool:
        """
        更新字段设计

        Args:
            field (FieldDesign): 字段设计实体

        Returns:
            bool: 操作结果
        """
        field.last_modify_date = datetime.datetime.now()
        # self.db.add(field) # For detached objects
        # await self.db.flush()
        stmt = (
            update(FieldDesign)
            .where(FieldDesign.id == field.id)
            .values(
                task_id=field.task_id,
                table_id=field.table_id,
                field_name=field.field_name,
                comment=field.comment,
                data_type=field.data_type,
                length=field.length,
                precision=field.precision,
                scale=field.scale,
                default_value=field.default_value,
                is_primary_key=field.is_primary_key,
                is_nullable=field.is_nullable,
                is_auto_increment=field.is_auto_increment,
                sort_order=field.sort_order,
                last_modify_date=field.last_modify_date
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0


    async def delete_async(self, id: int) -> bool:
        """
        删除字段设计

        Args:
            id (int): 字段设计ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(FieldDesign).where(FieldDesign.id == id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_by_table_id_async(self, table_id: int) -> bool:
        """
        删除表的所有字段设计

        Args:
            table_id (int): 表ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(FieldDesign).where(FieldDesign.table_id == table_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_by_task_id_async(self, task_id: int) -> bool:
        """
        删除任务的所有字段设计

        Args:
            task_id (int): 任务ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(FieldDesign).where(FieldDesign.task_id == task_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0