"""
播客模块数据库模型定义
"""
import datetime
from typing import Optional, List, Union
from sqlalchemy import (
    BigInteger, String, Integer, Text, DateTime,
    ForeignKey, Enum, func, Boolean, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base
from app.modules.tools.podcast.constants import (
    PodcastTaskStatus, PodcastRoleType, AudioStatusType, 
    PodcastTaskContentType, VoiceGenderType, VoicePlatformType
)


class PodcastTask(Base):
    """播客实体"""
    __tablename__ = "podcast_task"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, name="UserId", comment="用户ID"
    )
    title: Mapped[str] = mapped_column(
        String(255), nullable=True, name="Title", comment="播客标题"
    )
    description: Mapped[str] = mapped_column(
        String(1000), nullable=True, name="Description", comment="播客描述"
    )
    scene: Mapped[str] = mapped_column(
        String(100), nullable=True, name="Scene", comment="播客场景/主题"
    )
    atmosphere: Mapped[str] = mapped_column(
        String(100), nullable=True, name="Atmosphere", comment="播客氛围"
    )
    guest_count: Mapped[int] = mapped_column(
        Integer, default=1, name="GuestCount", comment="嘉宾数量"
    )
    status: Mapped[PodcastTaskStatus] = mapped_column(
        Integer, default=PodcastTaskStatus.INIT, name="Status", 
        comment="处理状态：0-初始化，1-待处理，2-处理中，3-处理完成，4-处理失败"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, name="ErrorMessage", comment="错误消息"
    )
    progress_step: Mapped[int] = mapped_column(
        Integer, default=0, name="ProgressStep", comment="进度"
    )
    generate_id: Mapped[int] = mapped_column(
        BigInteger, default=0, name="GenerateId", comment="当前的生成Id"
    )
    generate_count: Mapped[int] = mapped_column(
        Integer, default=0, name="GenerateCount", comment="生成次数"
    )
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, name="CreateDate", server_default=func.now(), comment="创建时间"
    )
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, name="LastModifyDate", server_default=func.now(), 
        onupdate=func.now(), comment="最后修改时间"
    )


class PodcastTaskContent(Base):
    """播客包含的内容项实体"""
    __tablename__ = "podcast_task_content"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, name="UserId", comment="用户ID"
    )
    podcast_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, name="PodcastId", comment="播客ID"
    )
    content_type: Mapped[PodcastTaskContentType] = mapped_column(
        Integer, name="ContentType", 
        comment="播客内容项类型: 1-文本，2-文档文件，3-网页地址"
    )
    source_document_id: Mapped[int] = mapped_column(
        BigInteger, nullable=True, name="SourceDocumentId", 
        comment="源文档ID（如果是上传文档或URL）"
    )
    source_content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, name="SourceContent", comment="源文本内容"
    )
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, name="CreateDate", server_default=func.now(), comment="创建时间"
    )
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, name="LastModifyDate", server_default=func.now(), 
        onupdate=func.now(), comment="最后修改时间"
    )


class PodcastTaskScript(Base):
    """播客脚本项实体"""
    __tablename__ = "podcast_task_script"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID"
    )
    podcast_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, name="PodcastId", comment="播客ID"
    )
    history_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, name="HistoryId", comment="历史ID"
    )
    sequence_number: Mapped[int] = mapped_column(
        Integer, nullable=False, name="SequenceNumber", comment="顺序号"
    )
    role_type: Mapped[PodcastRoleType] = mapped_column(
        Integer, nullable=False, name="RoleType", 
        comment="角色类型：1-主持人，2-嘉宾"
    )
    role_name: Mapped[str] = mapped_column(
        String(50), nullable=True, name="RoleName", comment="角色名称"
    )
    voice_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, name="VoiceId", 
        comment="语音角色ID"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, name="Content", comment="脚本内容（无SSML标记）"
    )
    ssml_content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, name="SsmlContent", comment="带SSML标记的脚本内容"
    )
    audio_path: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, name="AudioPath", comment="语音文件路径"
    )
    audio_duration: Mapped[float] = mapped_column(
        Integer, nullable=False, name="AudioDuration", comment="语音时长（秒）"
    )
    audio_status: Mapped[AudioStatusType] = mapped_column(
        Integer, default=AudioStatusType.PENDING, name="AudioStatus", 
        comment="语音生成状态：0-待生成，1-生成中，2-生成完成，3-生成失败"
    )
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, name="CreateDate", server_default=func.now(), comment="创建时间"
    )
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, name="LastModifyDate", server_default=func.now(), 
        onupdate=func.now(), comment="最后修改时间"
    )


class PodcastScriptHistory(Base):
    """播客脚本历史记录"""
    __tablename__ = "podcast_script_history"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID"
    )
    podcast_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, name="PodcastId", comment="播客ID"
    )
    name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, name="Name", comment="系统记录的创建名称"
    )
    status: Mapped[PodcastTaskStatus] = mapped_column(
        Integer, default=PodcastTaskStatus.PENDING, name="Status", 
        comment="处理状态：0-待处理，1-处理中，2-处理完成，3-处理失败"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, name="ErrorMessage", comment="错误消息"
    )
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, name="CreateDate", server_default=func.now(), comment="创建时间"
    )
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, name="LastModifyDate", server_default=func.now(), 
        onupdate=func.now(), comment="最后修改时间"
    )


class PodcastScriptHistoryItem(Base):
    """播客脚本历史项目"""
    __tablename__ = "podcast_script_history_item"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID"
    )
    podcast_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, name="PodcastId", comment="播客ID"
    )
    history_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, name="HistoryId", comment="历史ID"
    )
    sequence_number: Mapped[int] = mapped_column(
        Integer, nullable=False, name="SequenceNumber", comment="顺序号"
    )
    role_type: Mapped[PodcastRoleType] = mapped_column(
        Integer, nullable=False, name="RoleType", 
        comment="角色类型：1-主持人，2-嘉宾"
    )
    role_name: Mapped[str] = mapped_column(
        String(50), nullable=True, name="RoleName", comment="角色名称"
    )
    voice_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, name="VoiceId", 
        comment="语音角色ID"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, name="Content", comment="脚本内容（无SSML标记）"
    )
    ssml_content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, name="SsmlContent", comment="带SSML标记的脚本内容"
    )
    audio_path: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, name="AudioPath", comment="语音文件路径"
    )
    audio_duration: Mapped[float] = mapped_column(
        Integer, nullable=False, name="AudioDuration", comment="语音时长（秒）"
    )
    audio_status: Mapped[AudioStatusType] = mapped_column(
        Integer, default=AudioStatusType.PENDING, name="AudioStatus", 
        comment="语音生成状态：0-待生成，1-生成中，2-生成完成，3-生成失败"
    )
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, name="CreateDate", server_default=func.now(), comment="创建时间"
    )
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, name="LastModifyDate", server_default=func.now(), 
        onupdate=func.now(), comment="最后修改时间"
    )


class PodcastVoiceDefinition(Base):
    """播客语音角色定义实体"""
    __tablename__ = "podcast_voice_definition"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID"
    )
    voice_type: Mapped[str] = mapped_column(
        String(50), nullable=False, name="VoiceType", comment="语音类型：微软，豆包"
    )
    voice_symbol: Mapped[str] = mapped_column(
        String(50), nullable=True, name="VoiceSymbol", comment="语音标识符"
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=True, name="Name", comment="语音名称"
    )
    locale: Mapped[str] = mapped_column(
        String(20), nullable=True, name="Locale", comment="语言/地区"
    )
    gender: Mapped[VoiceGenderType] = mapped_column(
        Integer, nullable=False, name="Gender", comment="性别(Male/Female)"
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True, name="Description", comment="描述"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, name="IsActive", comment="是否启用"
    )
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, name="CreateDate", server_default=func.now(), comment="创建时间"
    )
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, name="LastModifyDate", server_default=func.now(), 
        onupdate=func.now(), comment="最后修改时间"
    )