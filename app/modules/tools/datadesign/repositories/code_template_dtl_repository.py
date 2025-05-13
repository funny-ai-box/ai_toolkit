import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, update

from app.modules.tools.datadesign.entities import CodeTemplateDtl
from app.core.utils.snowflake import generate_id

class CodeTemplateDtlRepository:
    """代码模板明细仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        构造函数

        Args:
            db (AsyncSession): 数据库会话
        """
        self.db = db

    async def get_by_id_async(self, id: int) -> Optional[CodeTemplateDtl]:
        """
        获取代码模板明细

        Args:
            id (int): 模板明细ID

        Returns:
            Optional[CodeTemplateDtl]: 代码模板明细实体
        """
        result = await self.db.execute(select(CodeTemplateDtl).filter(CodeTemplateDtl.id == id))
        return result.scalars().first()

    async def get_by_template_async(self, template_id: int) -> List[CodeTemplateDtl]:
        """
        按照模板Id获取代码模板明细

        Args:
            template_id (int): 模板Id

        Returns:
            List[CodeTemplateDtl]: 代码模板明细实体列表
        """
        result = await self.db.execute(select(CodeTemplateDtl).filter(CodeTemplateDtl.template_id == template_id))
        return result.scalars().all()

    async def add_async(self, template_dtl: CodeTemplateDtl) -> int:
        """
        新增代码模板明细

        Args:
            template_dtl (CodeTemplateDtl): 代码模板明细实体

        Returns:
            int: 新增记录的ID
        """
        template_dtl.id = generate_id()
        now = datetime.datetime.now()
        template_dtl.create_date = now
        template_dtl.last_modify_date = now
        self.db.add(template_dtl)
        await self.db.flush()
        return template_dtl.id

    async def batch_add_async(self, templates_dtl: List[CodeTemplateDtl]) -> bool:
        """
        批量新增代码模板明细

        Args:
            templates_dtl (List[CodeTemplateDtl]): 代码模板明细实体列表

        Returns:
            bool: 操作结果
        """
        now = datetime.datetime.now()
        for dtl in templates_dtl:
            dtl.id = generate_id() # Ensure each has a unique ID if not already set
            dtl.create_date = now
            dtl.last_modify_date = now
        
        self.db.add_all(templates_dtl)
        await self.db.flush() # Ensure IDs are populated if DB generates them, and data is persisted
        return True # Assuming flush() raises an exception on failure

    async def update_async(self, template_dtl: CodeTemplateDtl) -> bool:
        """
        更新代码模板明细

        Args:
            template_dtl (CodeTemplateDtl): 代码模板明细实体

        Returns:
            bool: 操作结果, True表示成功
        """
        template_dtl.last_modify_date = datetime.datetime.now()
        # self.db.add(template_dtl) # For detached objects or if you want to merge
        # await self.db.flush()
        # For already attached objects, SQLAlchemy tracks changes.
        # If you want explicit update statement:
        stmt = (
            update(CodeTemplateDtl)
            .where(CodeTemplateDtl.id == template_dtl.id)
            .values(
                template_dtl_name=template_dtl.template_dtl_name,
                file_name=template_dtl.file_name,
                template_content=template_dtl.template_content,
                last_modify_date=template_dtl.last_modify_date
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0


    async def delete_async(self, id: int) -> bool:
        """
        删除代码模板明细

        Args:
            id (int): 模板明细ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(CodeTemplateDtl).where(CodeTemplateDtl.id == id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_by_template_async(self, template_id: int) -> bool:
        """
        根据模板ID删除代码模板明细

        Args:
            template_id (int): 模板ID

        Returns:
            bool: 操作结果
        """
        stmt = delete(CodeTemplateDtl).where(CodeTemplateDtl.template_id == template_id)
        result = await self.db.execute(stmt)
        return result.rowcount > 0