import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, update

from app.modules.tools.datadesign.entities import IndexDesign
from app.core.utils.snowflake import generate_id

class IndexDesignRepository:
    """索引设计仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        构造函数

        Args:
            db (AsyncSession): 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[IndexDesign]:
        """
        获取索引设计

        Args:
            id (int): 索引设计ID

        Returns:
            Optional[IndexDesign]: 索引设计实体
        """
        result = await self.db.execute(select(IndexDesign).filter(IndexDesign.id == id))
        return result.scalars().first()

    async def get_by_table_id_async(self, table_id: int) -> List[IndexDesign]:
        """
        获取表的所有索引设计

        Args:
            table_id (int): 表ID

        Returns:
            List[IndexDesign]: 索引设计实体列表
        """
        stmt = select(IndexDesign).filter(IndexDesign.table_id == table_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_by_task_id_async(self, task_id: int) -> List[IndexDesign]:
        """
        获取任务的所有索引设计

        Args:
            task_id (int): 任务ID

        Returns:
            List[IndexDesign]: 索引设计实体列表
        """
        stmt = select(IndexDesign).filter(IndexDesign.task_id == task_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def add_async(self, index: IndexDesign) -> int:
        """
        新增索引设计

        Args:
            index (IndexDesign): 索引设计实体

        Returns:
            int: 新增索引的ID
        """
        index.id = generate_id()
        now = datetime.datetime.now()
        index.create_date = now
        index.last_modify_date = now
        self.db.add(index)
        await self.db.flush()
        return index.id

    async def add_batch_async(self, indexes: List[IndexDesign]) -> bool:
        """
        批量新增索引设计 (ID通常在外部已通过 generate_id() 赋值)

        Args:
            indexes (List[IndexDesign]): 索引设计实体列表

        Returns:
            bool: 操作结果
        """
        now = datetime.datetime.now()
        for index_item in indexes:
            if not index_item.id: # Ensure ID is set
                 index_item.id = generate_id()
            index_item.create_date = now
            index_item.last_modify_date = now
        
        self.db.add_all(indexes)
        await self.db.flush()
        return True

    async def update_async(self, index: IndexDesign) -> bool:
        """
        更新索引设计

        Args:
            index (IndexDesign): 索引设计实体

        Returns:
            bool: 操作结果
        """
        index.last_modify_date = datetime.datetime.now()
        # self.db.add(index) # For detached objects
        # await self.db.flush()
        stmt = (
            update(IndexDesign)
            .where(IndexDesign.id == index.id)
            .values(
                task_id=index.task_id,
                table_id=index.table_id,
                index_name=index.index_name,
                index_type=index.index_type,
                description=index.description,
                last_modify_date=index.last_modify_date
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_async(self, id: int) -> bool:
        """
        删除索引设计

        Args:
            id (int): 索引设计ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(IndexDesign).where(IndexDesign.id == id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_by_table_id_async(self, table_id: int) -> bool:
        """
        删除表的所有索引设计

        Args:
            table_id (int): 表ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(IndexDesign).where(IndexDesign.table_id == table_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_by_task_id_async(self, task_id: int) -> bool:
        """
        删除任务的所有索引设计

        Args:
            task_id (int): 任务ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(IndexDesign).where(IndexDesign.task_id == task_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0
