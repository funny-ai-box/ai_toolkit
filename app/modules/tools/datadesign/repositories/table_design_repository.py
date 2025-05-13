import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, update

from app.modules.tools.datadesign.entities import TableDesign
from app.core.utils.snowflake import generate_id

class TableDesignRepository:
    """表设计仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        构造函数

        Args:
            db (AsyncSession): 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[TableDesign]:
        """
        获取表设计

        Args:
            id (int): 表设计ID

        Returns:
            Optional[TableDesign]: 表设计实体
        """
        result = await self.db.execute(select(TableDesign).filter(TableDesign.id == id))
        return result.scalars().first()

    async def get_by_task_id_async(self, task_id: int) -> List[TableDesign]:
        """
        获取任务的所有表设计

        Args:
            task_id (int): 任务ID

        Returns:
            List[TableDesign]: 表设计实体列表 (按sort_order排序)
        """
        stmt = select(TableDesign).filter(TableDesign.task_id == task_id).order_by(TableDesign.sort_order)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def add_async(self, table: TableDesign) -> int:
        """
        新增表设计

        Args:
            table (TableDesign): 表设计实体

        Returns:
            int: 新增表的ID
        """
        table.id = generate_id()
        now = datetime.datetime.now()
        table.create_date = now
        table.last_modify_date = now
        self.db.add(table)
        await self.db.flush()
        return table.id

    async def add_batch_async(self, tables: List[TableDesign]) -> bool:
        """
        批量新增表设计 (ID通常在外部已通过 generate_id() 赋值)

        Args:
            tables (List[TableDesign]): 表设计实体列表

        Returns:
            bool: 操作结果
        """
        now = datetime.datetime.now()
        for table_item in tables:
            if not table_item.id: # Ensure ID is set
                 table_item.id = generate_id()
            table_item.create_date = now
            table_item.last_modify_date = now
        
        self.db.add_all(tables)
        await self.db.flush()
        return True

    async def update_async(self, table: TableDesign) -> bool:
        """
        更新表设计

        Args:
            table (TableDesign): 表设计实体

        Returns:
            bool: 操作结果
        """
        table.last_modify_date = datetime.datetime.now()
        # self.db.add(table) # For detached objects
        # await self.db.flush()
        stmt = (
            update(TableDesign)
            .where(TableDesign.id == table.id)
            .values(
                task_id=table.task_id,
                table_name=table.table_name,
                comment=table.comment,
                business_description=table.business_description,
                business_group=table.business_group,
                field_count=table.field_count,
                sort_order=table.sort_order,
                last_modify_date=table.last_modify_date
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_async(self, id: int) -> bool:
        """
        删除表设计

        Args:
            id (int): 表设计ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(TableDesign).where(TableDesign.id == id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_by_task_id_async(self, task_id: int) -> bool:
        """
        删除任务的所有表设计

        Args:
            task_id (int): 任务ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(TableDesign).where(TableDesign.task_id == task_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0
