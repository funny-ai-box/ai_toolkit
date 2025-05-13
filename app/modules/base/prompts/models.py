# app/modules/base/prompts/models.py
from sqlalchemy import BigInteger, String, DateTime, func, TEXT, Index
from sqlalchemy.orm import Mapped, mapped_column
import datetime

from app.core.database.session import Base # 导入共享的 Base

class PromptTemplate(Base):
    """
    提示词模板 SQLAlchemy 模型。
    映射到数据库的 pb_prompt_template 表。
    """
    __tablename__ = "pb_prompt_template"
    __table_args__ = (
        Index('unique_templatekey', 'TemplateKey', unique=True),
        {'comment': '提示词模板表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, comment="主键ID，雪花算法生成")
    template_key: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True, comment="模板唯一 Key", name="TemplateKey")
    template_desc: Mapped[str] = mapped_column(String(250), nullable=False, comment="模板描述", name="TemplateDesc")
    template_content: Mapped[str] = mapped_column(TEXT, nullable=False, comment="模板内容", name="TemplateContent")
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间", name="CreateDate"
    )
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="最后修改时间", name="LastModifyDate"
    )

    def __repr__(self) -> str:
        return f"<PromptTemplate(id={self.id}, template_key='{self.template_key}')>"