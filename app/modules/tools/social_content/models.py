# app/modules/tools/social_content/models.py
import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, String, Text, Boolean, Integer, Enum as SQLEnum, func
from sqlalchemy.orm import Mapped, mapped_column


from app.core.database.session import Base
from app.core.utils.snowflake import generate_id


class Platform(Base):
    """社交平台实体"""
    __tablename__ = "sct_platform"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    name: Mapped[str] = mapped_column(String(50), nullable=True, name="Name", comment="平台名称")
    code: Mapped[str] = mapped_column(String(50), nullable=True, name="Code", comment="平台代码")
    icon: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, name="Icon", comment="平台图标")
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, name="Description", comment="平台描述")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, name="IsActive", comment="是否启用：0-禁用，1-启用")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", comment="最后修改时间")


class PlatformTemplate(Base):
    """平台Prompt模板实体"""
    __tablename__ = "sct_platform_template"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    platform_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="PlatformId", comment="平台ID")
    template_name: Mapped[str] = mapped_column(String(100), nullable=True, name="TemplateName", comment="模板名称")
    template_content: Mapped[str] = mapped_column(Text, nullable=True, name="TemplateContent", comment="模板内容")
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="SystemPrompt", comment="系统提示词")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", comment="最后修改时间")


class PromptTypeEnum(int):
    """Prompt类型枚举"""
    SYSTEM = 1  # 系统默认
    USER = 2  # 用户自定义


class PlatformTemplateUser(Base):
    """用户自定义Prompt实体"""
    __tablename__ = "sct_platform_template_user"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    platform_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="PlatformId", comment="平台ID")
    template_name: Mapped[str] = mapped_column(String(100), nullable=True, name="TemplateName", comment="模板名称")
    template_content: Mapped[str] = mapped_column(Text, nullable=True, name="TemplateContent", comment="模板内容")
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="SystemPrompt", comment="系统提示词")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", comment="最后修改时间")


class GenerationTaskStatus(int):
    """任务状态枚举"""
    PENDING = 0  # 待处理
    PROCESSING = 1  # 处理中
    COMPLETED = 2  # 处理完成
    FAILED = 3  # 处理失败


class GenerationTask(Base):
    """内容生成任务实体"""
    __tablename__ = "sct_generation_task"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    task_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, name="TaskName", comment="任务名称")
    keywords: Mapped[Optional[str]] = mapped_column(String(5000), nullable=True, name="Keywords", comment="关键词")
    product_info: Mapped[Optional[str]] = mapped_column(String(5000), nullable=True, name="ProductInfo", comment="商品信息")
    status: Mapped[int] = mapped_column(Integer, nullable=False, name="Status", comment="状态：0-待处理，1-处理中，2-处理完成，3-处理失败")
    process_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True, name="ProcessMessage", comment="处理消息")
    completion_rate: Mapped[float] = mapped_column(Integer, nullable=False, name="CompletionRate", comment="完成率")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", comment="最后修改时间")


class GenerationTaskPlatform(Base):
    """任务平台关联实体"""
    __tablename__ = "sct_generation_task_platform"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="TaskId", comment="任务ID")
    platform_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="PlatformId", comment="平台ID")
    prompt_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="PromptId", comment="Prompt ID")
    prompt_type: Mapped[int] = mapped_column(Integer, nullable=False, name="PromptType", comment="Prompt类型：1-系统默认，2-用户自定义")
    template_content: Mapped[str] = mapped_column(Text, nullable=True, name="TemplateContent", comment="模板内容")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=True, name="SystemPrompt", comment="系统提示词")
    status: Mapped[int] = mapped_column(Integer, nullable=False, name="Status", comment="状态：0-待处理，1-处理中，2-处理完成，3-处理失败")
    content_count: Mapped[int] = mapped_column(Integer, nullable=False, name="ContentCount", comment="生成内容数量")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", comment="最后修改时间")


class GenerationTaskImage(Base):
    """任务图片实体"""
    __tablename__ = "sct_generation_task_image"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="TaskId", comment="任务ID")
    image_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True, name="ImagePath", comment="图片路径")
    image_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="ImageDescription", comment="图片描述(AI解析)")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", comment="最后修改时间")


class GeneratedContent(Base):
    """生成内容实体"""
    __tablename__ = "sct_generated_content"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="TaskId", comment="任务ID")
    task_platform_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="TaskPlatformId", comment="任务平台ID")
    platform_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="PlatformId", comment="平台ID")
    content_index: Mapped[int] = mapped_column(Integer, nullable=False, name="ContentIndex", comment="内容索引号")
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="Content", comment="生成的内容")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", comment="最后修改时间")