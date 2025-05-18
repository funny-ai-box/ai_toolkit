# app/modules/dataanalysis/repositories/table_column_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
import datetime

from app.core.utils.snowflake import generate_id
from app.modules.tools.dataanalysis.models import TableColumn

class TableColumnRepository:
    """表列信息仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化表列信息仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def add_async(self, table_column: TableColumn) -> TableColumn:
        """
        添加表列信息
        
        Args:
            table_column: 表列信息实体
        
        Returns:
            添加后的实体
        """
        # 使用雪花ID
        table_column.id = generate_id()
        
        # 设置创建和修改时间
        now = datetime.datetime.now()
        table_column.create_date = now
        table_column.last_modify_date = now
        
        # 插入数据
        self.db.add(table_column)
        await self.db.flush()
        await self.db.commit()  # 添加commit确保数据持久化
        
        return table_column
    
    async def add_batch_async(self, table_columns: List[TableColumn]) -> bool:
        """
        批量添加表列信息
        
        Args:
            table_columns: 表列信息实体列表
        
        Returns:
            是否成功
        """
        if not table_columns:
            return True
        
        # 设置雪花ID、创建和修改时间
        now = datetime.datetime.now()
        for column in table_columns:
            column.id = generate_id()
            column.create_date = now
            column.last_modify_date = now
        
        # 批量插入
        self.db.add_all(table_columns)
        await self.db.flush()
        await self.db.commit()  # 添加commit确保数据持久化
        
        return True
    
    async def update_async(self, table_column: TableColumn) -> TableColumn:
        """
        更新表列信息
        
        Args:
            table_column: 表列信息实体
        
        Returns:
            更新后的实体
        """
        # 更新最后修改时间
        table_column.last_modify_date = datetime.datetime.now()
        
        # 更新数据
        self.db.add(table_column)
        await self.db.flush()
        await self.db.commit()  # 添加commit确保数据持久化
        
        return table_column
    
    async def get_by_id_async(self, id: int) -> Optional[TableColumn]:
        """
        获取表列信息
        
        Args:
            id: 表列信息ID
        
        Returns:
            表列信息实体
        """
        result = await self.db.execute(
            select(TableColumn).filter(TableColumn.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_table_columns_async(self, table_id: int) -> List[TableColumn]:
        """
        获取数据表的所有列信息
        
        Args:
            table_id: 数据表ID
        
        Returns:
            表列信息实体列表
        """
        result = await self.db.execute(
            select(TableColumn)
            .filter(TableColumn.table_id == table_id)
            .order_by(TableColumn.column_index)
        )
        return list(result.scalars().all())
    
    async def delete_async(self, id: int) -> bool:
        """
        删除表列信息
        
        Args:
            id: 表列信息ID
        
        Returns:
            是否成功
        """
        result = await self.db.execute(
            delete(TableColumn).filter(TableColumn.id == id)
        )
        await self.db.commit()  # 添加commit确保数据持久化
        return result.rowcount > 0
    
    async def delete_by_table_id_async(self, table_id: int) -> bool:
        """
        按照TableId删除表列信息
        
        Args:
            table_id: 表信息ID
        
        Returns:
            是否成功
        """
        result = await self.db.execute(
            delete(TableColumn).filter(TableColumn.table_id == table_id)
        )
        await self.db.commit()  # 添加commit确保数据持久化
        return result.rowcount > 0