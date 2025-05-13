import datetime
from typing import Optional
from sqlalchemy import Column, BigInteger, String, Text, DateTime, Boolean, Integer, func, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.session import Base
from app.modules.tools.datadesign.enums import LanguageType, DatabaseType, AssistantRoleType
from app.core.ai.dtos import ChatRoleType # Assuming this exists

class CodeTemplate(Base):
    """代码模板实体模型"""
    __tablename__ = "ddb_code_template"
    # __table_args__ = {'comment': '代码模板'} # Add if your DB supports table comments

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID，若用户Id为空，则代表系统预置模板")
    template_name: Mapped[Optional[str]] = mapped_column(String(128), name="TemplateName", comment="模板名称")
    language: Mapped[LanguageType] = mapped_column(SAEnum(LanguageType), nullable=False, name="Language", comment="编程语言")
    database_type: Mapped[DatabaseType] = mapped_column(SAEnum(DatabaseType), nullable=False, name="DatabaseType", comment="数据库类型")
    prompt_content: Mapped[Optional[str]] = mapped_column(Text, name="PromptContent", comment="提示词内容，根据提示词来生成模板")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="最后修改时间")

class CodeTemplateDtl(Base):
    """代码模板明细实体模型"""
    __tablename__ = "ddb_code_template_dtl"
    # __table_args__ = {'comment': '代码模板明细'}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    template_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="TemplateId", comment="模板ID")
    template_dtl_name: Mapped[Optional[str]] = mapped_column(String(128), name="TemplateDtlName", comment="模板明细名称")
    file_name: Mapped[Optional[str]] = mapped_column(String(128), name="FileName", comment="模板文件名称")
    template_content: Mapped[Optional[str]] = mapped_column(Text, name="TemplateContent", comment="模板内容")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="最后修改时间")

class DesignChat(Base):
    """设计会话实体模型"""
    __tablename__ = "ddb_design_chat"
    # __table_args__ = {'comment': '设计会话'}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="TaskId", comment="任务ID")
    role: Mapped[ChatRoleType] = mapped_column(SAEnum(ChatRoleType), nullable=False, name="Role", comment="角色(user/assistant)") # Assuming ChatRoleType is string-based in core
    assistant_role: Mapped[Optional[AssistantRoleType]] = mapped_column(SAEnum(AssistantRoleType), name="AssistantRole", comment="助手角色")
    content: Mapped[Optional[str]] = mapped_column(Text, name="Content", comment="内容")
    is_latest_analysis: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, name="IsLatestAnalysis", comment="是否为最新分析结果")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="最后修改时间")

class DesignTask(Base):
    """设计任务实体模型"""
    __tablename__ = "ddb_design_task"
    # __table_args__ = {'comment': '设计任务'}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    task_name: Mapped[Optional[str]] = mapped_column(String(255), name="TaskName", comment="任务名称")
    description: Mapped[Optional[str]] = mapped_column(Text, name="Description", comment="任务描述")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="最后修改时间")

class DesignTaskState(Base):
    """设计任务状态实体模型"""
    __tablename__ = "ddb_design_task_state"
    # __table_args__ = {'comment': '设计任务状态'}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, name="TaskId", comment="任务ID") # TaskId should be unique
    latest_business_analysis_id: Mapped[Optional[int]] = mapped_column(BigInteger, name="LatestBusinessAnalysisId", default=0, comment="最新业务分析ID")
    latest_database_design_id: Mapped[Optional[int]] = mapped_column(BigInteger, name="LatestDatabaseDesignId", default=0, comment="最新数据库设计ID")
    latest_json_structure_id: Mapped[Optional[int]] = mapped_column(BigInteger, name="LatestJsonStructureId", default=0, comment="最新JSON结构ID")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="最后修改时间")

class FieldDesign(Base):
    """字段设计实体模型"""
    __tablename__ = "ddb_field_design"
    # __table_args__ = {'comment': '字段设计'}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="TaskId", comment="任务ID")
    table_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="TableId", comment="表ID")
    field_name: Mapped[Optional[str]] = mapped_column(String(128), name="FieldName", comment="字段名")
    comment: Mapped[Optional[str]] = mapped_column(String(255), name="Comment", comment="字段注释")
    data_type: Mapped[Optional[str]] = mapped_column(String(50), name="DataType", comment="数据类型")
    length: Mapped[Optional[int]] = mapped_column(Integer, name="Length", comment="长度")
    precision: Mapped[Optional[int]] = mapped_column(Integer, name="Precision", comment="精度")
    scale: Mapped[Optional[int]] = mapped_column(Integer, name="Scale", comment="小数位数")
    default_value: Mapped[Optional[str]] = mapped_column(String(255), name="DefaultValue", comment="默认值")
    is_primary_key: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, name="IsPrimaryKey", comment="是否主键")
    is_nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, name="IsNullable", comment="是否允许为空")
    is_auto_increment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, name="IsAutoIncrement", comment="是否自增")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, name="SortOrder", comment="排序号")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="最后修改时间")

class IndexDesign(Base):
    """索引设计实体模型"""
    __tablename__ = "ddb_index_design"
    # __table_args__ = {'comment': '索引设计'}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="TaskId", comment="任务ID")
    table_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="TableId", comment="表ID")
    index_name: Mapped[Optional[str]] = mapped_column(String(128), name="IndexName", comment="索引名称")
    index_type: Mapped[Optional[str]] = mapped_column(String(50), name="IndexType", comment="索引类型")
    description: Mapped[Optional[str]] = mapped_column(String(255), name="Description", comment="索引描述")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="最后修改时间")

class IndexField(Base):
    """索引字段实体模型"""
    __tablename__ = "ddb_index_field"
    # __table_args__ = {'comment': '索引字段'}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    index_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="IndexId", comment="索引ID")
    field_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="FieldId", comment="字段ID")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, name="SortOrder", comment="排序号")
    sort_direction: Mapped[Optional[str]] = mapped_column(String(10), name="SortDirection", comment="排序方向 (ASC/DESC)")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="最后修改时间")

class TableDesign(Base):
    """表设计实体模型"""
    __tablename__ = "ddb_table_design"
    # __table_args__ = {'comment': '表设计'}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="TaskId", comment="任务ID")
    table_name: Mapped[Optional[str]] = mapped_column(String(128), name="TableName", comment="表名")
    comment: Mapped[Optional[str]] = mapped_column(String(255), name="Comment", comment="表注释")
    business_description: Mapped[Optional[str]] = mapped_column(Text, name="BusinessDescription", comment="业务描述")
    business_group: Mapped[Optional[str]] = mapped_column(String(128), name="BusinessGroup", comment="业务分组")
    field_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, name="FieldCount", comment="字段数量")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, name="SortOrder", comment="排序号")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="最后修改时间")

class TableRelation(Base):
    """表关系设计实体模型"""
    __tablename__ = "ddb_table_relation"
    # __table_args__ = {'comment': '表关系设计'}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="TaskId", comment="任务ID")
    parent_table_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="ParentTableId", comment="父表ID")
    child_table_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="ChildTableId", comment="子表ID")
    relation_type: Mapped[Optional[str]] = mapped_column(String(50), name="RelationType", comment="关系类型")
    description: Mapped[Optional[str]] = mapped_column(String(255), name="Description", comment="关系描述")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="最后修改时间")