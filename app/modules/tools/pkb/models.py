"""
个人知识库数据模型
"""
import datetime
from sqlalchemy import BigInteger, Column, String, Text, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.session import Base 


class ChatSession(Base):
    """对话会话实体"""
    __tablename__ = "pkb_chat_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId")
    document_id: Mapped[int] = mapped_column(BigInteger, nullable=True, name="DocumentId")
    session_name: Mapped[str] = mapped_column(String(255), nullable=True, name="SessionName")
    share_code: Mapped[str] = mapped_column(String(32), nullable=True, name="ShareCode")
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, name="IsShared")
    prompt: Mapped[str] = mapped_column(Text, nullable=True, name="Prompt")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate")


class ChatHistory(Base):
    """对话历史实体"""
    __tablename__ = "pkb_chat_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id")
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="SessionId")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId")
    role: Mapped[str] = mapped_column(String(20), nullable=True, name="Role")
    content: Mapped[str] = mapped_column(Text, nullable=True, name="Content")
    vector_ids: Mapped[str] = mapped_column(String(1000), nullable=True, name="VectorIds")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate")


class ChatHistorySources(Base):
    """对话历史的引用文档源"""
    __tablename__ = "pkb_chat_history_sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id")
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="SessionId")
    history_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="HistoryId")
    document_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="DocumentId")
    document_title: Mapped[str] = mapped_column(String(255), nullable=True, name="DocumentTitle")
    content: Mapped[str] = mapped_column(String(255), nullable=True, name="Content")
    score: Mapped[float] = mapped_column(Float, nullable=False, name="Score")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate")