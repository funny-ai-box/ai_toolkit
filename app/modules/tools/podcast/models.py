# app/modules/tools/podcast/models.py
import datetime
from enum import Enum
from typing import Optional, List

from sqlalchemy import (
    BigInteger, String, Text, DateTime, Integer, Boolean,
    Enum as SQLAlchemyEnum, Interval  # <--- CORRECTED IMPORT
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func


from app.core.ai.speech.base import VoicePlatformType as CoreVoicePlatformType
from app.core.database.session import Base


class AudioStatusType(int, Enum):
    """语音生成状态枚举"""
    PENDING = 0     # 待生成
    PROCESSING = 1  # 生成中
    COMPLETED = 2   # 生成完成
    FAILED = 3      # 生成失败

class PodcastRoleType(int, Enum):
    """播客角色类型枚举"""
    HOST = 1    # 主持人
    GUEST = 2   # 嘉宾

class PodcastTaskStatus(int, Enum):
    """播客处理状态枚举"""
    INIT = 0        # 初始化
    PENDING = 1     # 待处理
    PROCESSING = 2  # 开始处理
    COMPLETED = 3   # 处理完成
    FAILED = 4      # 处理失败

class PodcastTaskContentType(int, Enum):
    """播客内容项类型"""
    TEXT = 1  # 文本
    FILE = 2  # 文档文件
    URL = 3   # 网页地址

class VoiceGenderType(int, Enum):
    """语音性别类型"""
    MALE = 1
    FEMALE = 2


class PodcastScriptHistory(Base):
    """播客脚本历史项实体"""
    __tablename__ = "podcast_script_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id")
    podcast_id: Mapped[int] = mapped_column(BigInteger, name="PodcastId", index=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), name="Name", nullable=True)
    status: Mapped[PodcastTaskStatus] = mapped_column(SQLAlchemyEnum(PodcastTaskStatus), name="Status")
    error_message: Mapped[Optional[str]] = mapped_column(String(500), name="ErrorMessage", nullable=True)
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, name="CreateDate", server_default=func.now())
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, name="LastModifyDate", server_default=func.now(), onupdate=func.now())

class PodcastScriptHistoryItem(Base):
    """播客脚本历史项明细实体"""
    __tablename__ = "podcast_script_history_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id")
    podcast_id: Mapped[int] = mapped_column(BigInteger, name="PodcastId", index=True)
    history_id: Mapped[int] = mapped_column(BigInteger, name="HistoryId", index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, name="SequenceNumber")
    role_type: Mapped[PodcastRoleType] = mapped_column(SQLAlchemyEnum(PodcastRoleType), name="RoleType")
    role_name: Mapped[Optional[str]] = mapped_column(String(50), name="RoleName", nullable=True)
    voice_id: Mapped[int] = mapped_column(BigInteger, name="VoiceId")
    content: Mapped[Optional[str]] = mapped_column(Text, name="Content", nullable=True)
    ssml_content: Mapped[Optional[str]] = mapped_column(Text, name="SsmlContent", nullable=True)
    audio_path: Mapped[Optional[str]] = mapped_column(String(255), name="AudioPath", nullable=True)
    audio_duration: Mapped[datetime.timedelta] = mapped_column(Interval, name="AudioDuration", default=datetime.timedelta(0)) # <--- CORRECTED
    audio_status: Mapped[AudioStatusType] = mapped_column(SQLAlchemyEnum(AudioStatusType), name="AudioStatus")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, name="CreateDate", server_default=func.now())
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, name="LastModifyDate", server_default=func.now(), onupdate=func.now())

class PodcastTask(Base):
    """播客任务实体"""
    __tablename__ = "podcast_task"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id")
    user_id: Mapped[int] = mapped_column(BigInteger, name="UserId", index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), name="Title", nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), name="Description", nullable=True)
    scene: Mapped[Optional[str]] = mapped_column(String(100), name="Scene", nullable=True)
    atmosphere: Mapped[Optional[str]] = mapped_column(String(100), name="Atmosphere", nullable=True)
    guest_count: Mapped[int] = mapped_column(Integer, name="GuestCount", default=1)
    status: Mapped[PodcastTaskStatus] = mapped_column(SQLAlchemyEnum(PodcastTaskStatus), name="Status")
    error_message: Mapped[Optional[str]] = mapped_column(String(500), name="ErrorMessage", nullable=True)
    progress_step: Mapped[int] = mapped_column(Integer, name="ProgressStep", default=0)
    generate_id: Mapped[int] = mapped_column(BigInteger, name="GenerateId", default=0)
    generate_count: Mapped[int] = mapped_column(Integer, name="GenerateCount", default=0)
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, name="CreateDate", server_default=func.now())
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, name="LastModifyDate", server_default=func.now(), onupdate=func.now())

class PodcastTaskContent(Base):
    """播客内容项实体"""
    __tablename__ = "podcast_task_content"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id")
    user_id: Mapped[int] = mapped_column(BigInteger, name="UserId", index=True)
    podcast_id: Mapped[int] = mapped_column(BigInteger, name="PodcastId", index=True)
    content_type: Mapped[PodcastTaskContentType] = mapped_column(SQLAlchemyEnum(PodcastTaskContentType), name="ContentType")
    source_document_id: Mapped[Optional[int]] = mapped_column(BigInteger, name="SourceDocumentId", nullable=True)
    source_content: Mapped[Optional[str]] = mapped_column(Text, name="SourceContent", nullable=True)
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, name="CreateDate", server_default=func.now())
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, name="LastModifyDate", server_default=func.now(), onupdate=func.now())

class PodcastTaskScript(Base):
    """播客脚本项实体 (当前正在使用的脚本)"""
    __tablename__ = "podcast_task_script"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id")
    podcast_id: Mapped[int] = mapped_column(BigInteger, name="PodcastId", index=True)
    history_id: Mapped[int] = mapped_column(BigInteger, name="HistoryId", index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, name="SequenceNumber")
    role_type: Mapped[PodcastRoleType] = mapped_column(SQLAlchemyEnum(PodcastRoleType), name="RoleType")
    role_name: Mapped[Optional[str]] = mapped_column(String(50), name="RoleName", nullable=True)
    voice_id: Mapped[int] = mapped_column(BigInteger, name="VoiceId")
    content: Mapped[Optional[str]] = mapped_column(Text, name="Content", nullable=True)
    ssml_content: Mapped[Optional[str]] = mapped_column(Text, name="SsmlContent", nullable=True)
    audio_path: Mapped[Optional[str]] = mapped_column(String(255), name="AudioPath", nullable=True)
    audio_duration: Mapped[datetime.timedelta] = mapped_column(Interval, name="AudioDuration", default=datetime.timedelta(0)) # <--- CORRECTED
    audio_status: Mapped[AudioStatusType] = mapped_column(SQLAlchemyEnum(AudioStatusType), name="AudioStatus")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, name="CreateDate", server_default=func.now())
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, name="LastModifyDate", server_default=func.now(), onupdate=func.now())

class PodcastVoiceDefinition(Base):
    """播客语音角色定义实体"""
    __tablename__ = "podcast_voice_definition"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id")
    voice_type: Mapped[CoreVoicePlatformType] = mapped_column(SQLAlchemyEnum(CoreVoicePlatformType), name="VoiceType")
    voice_symbol: Mapped[Optional[str]] = mapped_column(String(50), name="VoiceSymbol", nullable=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), name="Name", nullable=True)
    locale: Mapped[Optional[str]] = mapped_column(String(20), name="Locale", nullable=True)
    gender: Mapped[VoiceGenderType] = mapped_column(SQLAlchemyEnum(VoiceGenderType), name="Gender")
    description: Mapped[Optional[str]] = mapped_column(String(500), name="Description", nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, name="IsActive", default=True)
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, name="CreateDate", server_default=func.now())
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, name="LastModifyDate", server_default=func.now(), onupdate=func.now())