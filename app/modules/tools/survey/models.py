import datetime
from typing import Optional, List
from sqlalchemy import BigInteger, String, Integer, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database.session import Base



class SurveyTask(Base):
    """问卷任务实体"""
    __tablename__ = "survey_task"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    name: Mapped[str] = mapped_column(String(100), nullable=True, name="Name", comment="任务名称")
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, name="Description", comment="任务描述")
    share_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, name="ShareCode", comment="共享码（用于分享填写）")
    status: Mapped[int] = mapped_column(Integer, nullable=False, name="Status", comment="状态：0-草稿，1-已发布，2-已关闭")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", comment="最后修改时间")
    
    # Relationships
    tabs: Mapped[List["SurveyTab"]] = relationship("SurveyTab", back_populates="task", cascade="all, delete-orphan")


class SurveyTab(Base):
    """问卷tab页定义"""
    __tablename__ = "survey_tab"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("survey_task.Id"), nullable=False, name="TaskId", comment="任务ID")
    name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, name="Name", comment="Tab名称")
    order_no: Mapped[int] = mapped_column(Integer, nullable=False, name="OrderNo", comment="排序号")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", comment="最后修改时间")
    
    # Relationships
    task: Mapped["SurveyTask"] = relationship("SurveyTask", back_populates="tabs")
    fields: Mapped[List["SurveyField"]] = relationship("SurveyField", back_populates="tab", cascade="all, delete-orphan")


class SurveyField(Base):
    """问卷字段实体"""
    __tablename__ = "survey_field"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("survey_task.Id"), nullable=False, name="TaskId", comment="任务ID")
    tab_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("survey_tab.Id"), nullable=False, name="TabId", comment="Tab页ID")
    field_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, name="FieldKey", comment="字段标识符（供前端使用）")
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, name="Name", comment="字段名称")
    type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, name="Type", comment="字段类型：单选，多选，日期，单行文本，多行文本，图片上传，数字等")
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, name="IsRequired", comment="是否必填")
    config: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="Config", comment="字段配置（JSON格式，包含验证规则、选项数据源等）")
    placeholder: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, name="Placeholder", comment="字段提示信息")
    order_no: Mapped[int] = mapped_column(Integer, nullable=False, name="OrderNo", comment="排序号")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", comment="最后修改时间")
    
    # Relationships
    tab: Mapped["SurveyTab"] = relationship("SurveyTab", back_populates="fields")


class SurveyDesignHistory(Base):
    """AI设计会话历史"""
    __tablename__ = "survey_design_history"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("survey_task.Id"), nullable=False, name="TaskId", comment="任务ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    role: Mapped[int] = mapped_column(String(20), nullable=False, name="Role", comment="消息角色（用户/AI）")
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="Content", comment="消息内容")
    complete_json_config: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="CompleteJsonConfig", comment="完整JSON配置")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", comment="创建时间")


class SurveyResponse(Base):
    """问卷填写记录实体"""
    __tablename__ = "survey_response"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("survey_task.Id"), nullable=False, name="TaskId", comment="任务ID")
    respondent_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, name="RespondentId", comment="填写人ID（可为空，匿名填写）")
    respondent_ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, name="RespondentIp", comment="填写人IP")
    submit_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="SubmitDate", comment="提交时间")
    
    # Relationships
    details: Mapped[List["SurveyResponseDetail"]] = relationship("SurveyResponseDetail", back_populates="response", cascade="all, delete-orphan")


class SurveyResponseDetail(Base):
    """问卷填写详情实体（字段值）"""
    __tablename__ = "survey_response_detail"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    response_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("survey_response.Id"), nullable=False, name="ResponseId", comment="填写记录ID")
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("survey_task.Id"), nullable=False, name="TaskId", comment="任务ID")
    field_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("survey_field.Id"), nullable=False, name="FieldId", comment="字段ID")
    field_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, name="FieldKey", comment="字段标识符")
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="Value", comment="字段值（存储文本值）")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", comment="创建时间")
    
    # Relationships
    response: Mapped["SurveyResponse"] = relationship("SurveyResponse", back_populates="details")