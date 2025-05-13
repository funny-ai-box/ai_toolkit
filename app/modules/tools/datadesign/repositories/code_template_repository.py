import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, update, func

from app.modules.tools.datadesign.entities import CodeTemplate, CodeTemplateDtl
from app.core.utils.snowflake import generate_id

class CodeTemplateRepository:
    """代码模板仓储实现"""

    def __init__(self, db: AsyncSession):
        """
        构造函数

        Args:
            db (AsyncSession): 数据库会话
        """
        self.db = db

    async def exist_system_template_async(self) -> bool:
        """
        检查是否存在系统模板

        Returns:
            bool: True如果存在，否则False
        """
        # Assuming user_id == 0 indicates a system template
        result = await self.db.execute(
            select(func.count(CodeTemplate.id)).filter(CodeTemplate.user_id == 0)
        )
        count = result.scalar_one_or_none()
        return count is not None and count > 0

    async def get_by_id_async(self, id: int) -> Optional[CodeTemplate]:
        """
        获取代码模板

        Args:
            id (int): 模板ID

        Returns:
            Optional[CodeTemplate]: 代码模板实体
        """
        result = await self.db.execute(select(CodeTemplate).filter(CodeTemplate.id == id))
        return result.scalars().first()

    async def get_system_and_user_template_async(self, user_id: int) -> List[CodeTemplate]:
        """
        获取系统默认和用户维护的代码模板

        Args:
            user_id (int): 用户ID

        Returns:
            List[CodeTemplate]: 代码模板实体列表
        """
        # user_id == 0 for system templates
        stmt = select(CodeTemplate).filter(
            (CodeTemplate.user_id == 0) | (CodeTemplate.user_id == user_id)
        ).order_by(CodeTemplate.id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def add_template_and_dtls_async(self, template: CodeTemplate, dtls: List[CodeTemplateDtl]) -> bool:
        """
        新增代码模板和明细 (事务性操作，依赖外部commit)

        Args:
            template (CodeTemplate): 代码模板实体
            dtls (List[CodeTemplateDtl]): 代码模板明细实体列表

        Returns:
            bool: 操作结果
        """
        template.id = generate_id()
        now = datetime.datetime.now()
        template.create_date = now
        template.last_modify_date = now
        self.db.add(template)

        for dtl in dtls:
            dtl.id = generate_id()
            dtl.template_id = template.id # Link to the parent template
            dtl.create_date = now
            dtl.last_modify_date = now
        
        self.db.add_all(dtls)
        await self.db.flush() # Persist changes to DB
        return True

    async def add_async(self, template: CodeTemplate) -> int:
        """
        新增代码模板

        Args:
            template (CodeTemplate): 代码模板实体

        Returns:
            int: 新增模板的ID
        """
        template.id = generate_id()
        now = datetime.datetime.now()
        template.create_date = now
        template.last_modify_date = now
        self.db.add(template)
        await self.db.flush()
        return template.id

    async def update_async(self, template: CodeTemplate) -> bool:
        """
        更新代码模板

        Args:
            template (CodeTemplate): 代码模板实体

        Returns:
            bool: 操作结果
        """
        template.last_modify_date = datetime.datetime.now()
        # self.db.add(template) # For detached object or merge
        # await self.db.flush()
        stmt = (
            update(CodeTemplate)
            .where(CodeTemplate.id == template.id)
            .values(
                template_name=template.template_name,
                language=template.language,
                database_type=template.database_type,
                prompt_content=template.prompt_content,
                last_modify_date=template.last_modify_date
            )
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0


    async def update_prompt_content_async(self, id: int, prompt_content: str) -> bool:
        """
        更新代码模板的提示词内容

        Args:
            id (int): 模板ID
            prompt_content (str): 提示词内容

        Returns:
            bool: 操作结果
        """
        stmt = (
            update(CodeTemplate)
            .where(CodeTemplate.id == id)
            .values(prompt_content=prompt_content, last_modify_date=datetime.datetime.now())
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def delete_async(self, id: int) -> bool:
        """
        删除代码模板 (包括其明细)

        Args:
            id (int): 模板ID

        Returns:
            bool: 操作结果
        """
        # First, delete details
        stmt_dtl = delete(CodeTemplateDtl).where(CodeTemplateDtl.template_id == id)
        await self.db.execute(stmt_dtl)
        
        # Then, delete the template itself
        stmt_template = delete(CodeTemplate).where(CodeTemplate.id == id)
        result = await self.db.execute(stmt_template)
        return result.rowcount > 0