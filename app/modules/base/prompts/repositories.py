# app/modules/base/prompts/repositories.py
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.base.prompts.models import PromptTemplate
from app.core.utils.snowflake import generate_id # 导入雪花 ID 生成函数
import datetime

class PromptTemplateRepository:
    """
    提示词模板仓库，负责数据库交互。
    对应 C# 的 IPromptTemplateRepository 实现。
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_async(self, entity: PromptTemplate) -> int:
        """
        添加新的提示词模板。

        Args:
            entity: 待添加的 PromptTemplate 模型实例（ID 和时间会被覆盖）。

        Returns:
            新创建的模板的 ID。

        Raises:
            SQLAlchemyError: 如果数据库操作失败 (通常在 commit 时)。
        """
        entity.id = generate_id()
        now = datetime.datetime.now()
        entity.create_date = now
        entity.last_modify_date = now
        self.db.add(entity)
        await self.db.flush() # 刷新以获取 ID 或捕获早期错误
        # commit 应在服务层完成
        return entity.id

    async def update_async(self, entity: PromptTemplate) -> bool:
        """
        更新现有的提示词模板。

        Args:
            entity: 包含更新后信息的 PromptTemplate 模型实例。

        Returns:
            操作是否影响了行 (不完全等同于 C# 的 > 0，但接近)。

        Raises:
            SQLAlchemyError: 如果数据库操作失败。
        """
        # 确保对象已附加到会话或尝试合并
        if entity not in self.db and not self.db.is_modified(entity):
             try:
                 # 尝试从当前会话加载具有相同 ID 的实例
                 existing = await self.db.get(PromptTemplate, entity.id)
                 if existing:
                      # 如果存在，将传入实体的值复制到现有实体
                      # (避免使用 merge，因其行为有时不直观)
                      existing.template_key = entity.template_key
                      existing.template_desc = entity.template_desc
                      existing.template_content = entity.template_content
                      # last_modify_date 会通过 onupdate=func.now() 自动更新
                      # 或者在这里显式设置:
                      # existing.last_modify_date = datetime.datetime.now()
                      target_entity = existing
                 else:
                      # 如果会话中没有，数据库中也没有 (或者 ID 不匹配)，则无法更新
                      return False
             except Exception as e:
                 print(f"获取或合并 PromptTemplate 失败: {e}") # logger
                 return False
        else:
             # 如果实体已在会话中，SQLAlchemy 会自动跟踪更改
             target_entity = entity
             # 同样，可以显式更新时间
             # target_entity.last_modify_date = datetime.datetime.now()

        # C# 代码忽略了 CreateDate，这里不需要特殊处理，因为我们只更新了特定字段
        await self.db.flush() # 刷新更改
        # commit 应在服务层完成
        # 这里返回 True 表示 flush 成功，但不保证 commit 成功
        # 更好的方式可能是让服务层判断 commit 结果
        return True


    async def get_async(self, template_id: int) -> Optional[PromptTemplate]:
        """
        根据 ID 获取提示词模板。

        Args:
            template_id: 模板 ID。

        Returns:
            PromptTemplate 模型实例，如果未找到则返回 None。
        """
        stmt = select(PromptTemplate).where(PromptTemplate.id == template_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_key_async(self, template_key: str) -> Optional[PromptTemplate]:
        """
        根据模板 Key 获取提示词模板。

        Args:
            template_key: 模板 Key。

        Returns:
            PromptTemplate 模型实例，如果未找到则返回 None。
        """
        stmt = select(PromptTemplate).where(PromptTemplate.template_key == template_key)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()