"""
原型设计模块的数据库模型定义
"""
import datetime
from typing import Optional, List

from sqlalchemy import String, Integer, Text, Boolean, ForeignKey, DateTime, BigInteger, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.session import Base
from app.modules.tools.prototype.enums import PrototypeSessionStatus, PrototypePageStatus, PrototypeMessageType


class PrototypeSession(Base):
    """原型会话实体"""
    __tablename__ = "adp_prototype_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, name="Name", comment="会话名称")
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True, name="Description", comment="会话描述")
    status: Mapped[PrototypeSessionStatus] = mapped_column(
        SQLEnum(PrototypeSessionStatus), nullable=False, name="Status", comment="会话状态"
    )
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="Requirements", comment="需求描述（结构化JSON）")
    page_structure: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="PageStructure", comment="页面结构（结构化JSON）")
    is_generating_code: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False, name="IsGeneratingCode", comment="是否正在生成代码")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now, name="LastModifyDate", comment="最后修改时间")

    # Relationships
    messages: Mapped[List["PrototypeMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    pages: Mapped[List["PrototypePage"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    resources: Mapped[List["PrototypeResource"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class PrototypePage(Base):
    """原型页面实体"""
    __tablename__ = "adp_prototype_page"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("adp_prototype_session.Id"), nullable=False, name="SessionId", comment="会话ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, name="Name", comment="页面名称")
    path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, name="Path", comment="页面路径（用于路由）")
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, name="IsComplete", comment="代码是否完整")
    partial_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="PartialContent", comment="部分内容（如果代码未完成）")
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True, name="Description", comment="页面描述")
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="Content", comment="页面内容（React代码）")
    status: Mapped[PrototypePageStatus] = mapped_column(
        SQLEnum(PrototypePageStatus), nullable=False, name="Status", comment="页面状态"
    )
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, name="ErrorMessage", comment="错误消息")
    order: Mapped[int] = mapped_column(Integer, nullable=True, default=0, name="Order", comment="页面顺序（用于排序）")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, name="Version", comment="版本号")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now, name="LastModifyDate", comment="最后修改时间")

    # Relationships
    session: Mapped["PrototypeSession"] = relationship(back_populates="pages")
    history: Mapped[List["PrototypePageHistory"]] = relationship(back_populates="page", cascade="all, delete-orphan")


class PrototypePageHistory(Base):
    """原型页面历史版本实体"""
    __tablename__ = "adp_prototype_page_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    page_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("adp_prototype_page.Id"), nullable=False, name="PageId", comment="页面ID")
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="SessionId", comment="会话ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="Content", comment="页面内容（React代码）")
    version: Mapped[int] = mapped_column(Integer, nullable=False, name="Version", comment="版本号")
    change_description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True, name="ChangeDescription", comment="修改描述")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now, name="CreateDate", comment="创建时间")

    # Relationships
    page: Mapped["PrototypePage"] = relationship(back_populates="history")


class PrototypeMessage(Base):
    """原型会话消息实体"""
    __tablename__ = "adp_prototype_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("adp_prototype_session.Id"), nullable=False, name="SessionId", comment="会话ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    message_type: Mapped[PrototypeMessageType] = mapped_column(
        SQLEnum(PrototypeMessageType), nullable=False, name="MessageType", comment="消息类型"
    )
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="Content", comment="消息内容")
    is_code: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False, name="IsCode", comment="是否是代码内容")
    attachment_ids: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, name="AttachmentIds", comment="附件ID（如果有）")
    attachment_urls: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True, name="AttachmentUrls", comment="附件URL（如果有）")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now, name="CreateDate", comment="创建时间")

    # Relationships
    session: Mapped["PrototypeSession"] = relationship(back_populates="messages")


class PrototypeResource(Base):
    """原型引用资源实体（CSS、JS等）"""
    __tablename__ = "adp_prototype_resource"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID（雪花算法）")
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("adp_prototype_session.Id"), nullable=False, name="SessionId", comment="会话ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, name="Name", comment="资源名称")
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, name="ResourceType", comment="资源类型（css, js, image等）")
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, name="Url", comment="资源URL")
    gemini_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, name="GeminiUrl", comment="Gemini大模型使用的URL")
    gemini_mime_type: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, name="GeminiMimeType", comment="Gemini大模型使用的MIME类型")
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="Content", comment="资源内容（可选，如果是自定义资源）")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now, name="CreateDate", comment="创建时间")

    # Relationships
    session: Mapped["PrototypeSession"] = relationship(back_populates="resources")