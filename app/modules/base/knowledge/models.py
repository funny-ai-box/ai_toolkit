# app/modules/base/knowledge/models.py
from typing import Optional
from sqlalchemy import BigInteger, String, DateTime, func, TEXT, Index, Enum as SQLAlchemyEnum, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
import datetime

from app.core.database.session import Base
from app.core.dtos import DocumentAppType # 导入核心枚举
# 导入本地定义的枚举 (或者将这些枚举移到 core.dtos)
from .dtos import DocumentStatus, DocumentLogType

# --- Document Model ---
class Document(Base):
    """知识库文档实体"""
    __tablename__ = "pb_document"
    __table_args__ = (
        Index('idx_userid_apptype', 'UserId', 'AppType'), # 常用查询组合索引
        {'comment': '知识库文档表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, comment="主键ID，雪花算法生成")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="UserId", comment="用户ID")
    reference_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, name="ReferenceId", comment="参考ID")
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, name="Title", comment="文档标题")
    # 使用 SQLAlchemy 的 Enum 类型存储枚举值 (存储整数值)
    app_type: Mapped[DocumentAppType] = mapped_column(Integer, nullable=False, name="AppType", comment="文档所属源 (存储整数)")
    type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, name="Type", comment="来源类型 (file, url)")
    original_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, name="OriginalName", comment="原始文件名")
    cdn_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, name="CdnUrl", comment="CDN存储地址")
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, name="SourceUrl", comment="来源链接")
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, name="FileSize", comment="文件大小(字节)")
    content_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0, name="ContentLength", comment="内容长度")
    # 存储枚举字符串值
    status: Mapped[DocumentStatus] = mapped_column(Integer, nullable=False, default=DocumentStatus.PENDING.value, name="Status", comment="解析状态 (存储整数)")
    process_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True, name="ProcessMessage", comment="处理消息")
    is_need_vector: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, name="IsNeedVector", comment="是否需要向量化")
    vector_status: Mapped[DocumentStatus] = mapped_column(Integer, nullable=False, default=DocumentStatus.PENDING.value, name="VectorStatus", comment="向量化状态 (存储整数)")
    vector_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True, name="VectorMessage", comment="向量化处理消息")
    is_need_graph: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, name="IsNeedGraph", comment="是否需要图谱化")
    graph_status: Mapped[DocumentStatus] = mapped_column(Integer, nullable=False, default=DocumentStatus.PENDING.value, name="GraphStatus", comment="图谱化状态 (存储整数)")
    graph_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True, name="GraphMessage", comment="图谱化处理消息")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="最后修改时间")

# --- DocumentContent Model ---
class DocumentContent(Base):
    """知识库文档内容实体"""
    __tablename__ = "pb_document_content"
    __table_args__ = {'comment': '知识库文档内容表'}

    # ID 与 Document 表的 ID 相同，构成一对一关系
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, comment="主键ID (同文档ID)")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="UserId", comment="用户ID")
    document_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="DocumentId", comment="文档ID")
    # C# 使用 LONGTEXT，SQLAlchemy 的 TEXT 通常映射到足够大的文本类型
    content: Mapped[Optional[str]] = mapped_column(TEXT, nullable=True, name="Content", comment="文档内容")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="最后修改时间")

# --- DocumentGraph Model ---
class DocumentGraph(Base):
    """知识库文档知识图谱实体"""
    __tablename__ = "pb_document_graph"
    __table_args__ = (
        Index('idx_graph_docid', 'DocumentId', unique=True), # 文档 ID 应该是唯一的
        {'comment': '知识库文档知识图谱表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, comment="主键ID，雪花算法生成")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="UserId", comment="用户ID")
    document_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True, name="DocumentId", comment="文档ID")
    summary: Mapped[Optional[str]] = mapped_column(TEXT, nullable=True, name="Summary", comment="AI总结内容")
    # 存储为 JSON 字符串
    keywords: Mapped[Optional[str]] = mapped_column(String(5000), nullable=True, name="Keywords", comment="关键词(JSON数组)")
    # 存储为 JSON 字符串
    mind_map: Mapped[Optional[str]] = mapped_column(TEXT, nullable=True, name="MindMap", comment="知识脑图(JSON结构)") # C# 是 LONGTEXT
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="最后修改时间")

# --- DocumentLog Model ---
class DocumentLog(Base):
    """知识库文档处理日志实体"""
    __tablename__ = "pb_document_log"
    __table_args__ = (
        Index('idx_log_docid_logtype', 'DocumentId', 'LogType'),
        {'comment': '知识库文档处理日志表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, comment="主键ID，雪花算法生成")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="UserId", comment="用户ID")
    document_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="DocumentId", comment="文档ID")
    log_type: Mapped[DocumentLogType] = mapped_column(Integer, nullable=False, name="LogType", comment="日志类型 (存储整数)")
    message: Mapped[Optional[str]] = mapped_column(TEXT, nullable=True, name="Message", comment="日志消息")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="最后修改时间")

# --- DocumentVector Model ---
class DocumentVector(Base):
    """知识库文档向量实体 (存储在关系数据库中，关联到 Milvus 中的向量)"""
    __tablename__ = "pb_document_vector"
    __table_args__ = (
        Index('idx_vector_docid_chunkidx', 'DocumentId', 'ChunkIndex'),
        {'comment': '知识库文档向量表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, comment="主键ID，雪花算法生成")
    document_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="DocumentId", comment="文档ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="UserId", comment="用户ID")
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, name="ChunkIndex", comment="文档分片索引")
    chunk_content: Mapped[Optional[str]] = mapped_column(TEXT, nullable=True, name="ChunkContent", comment="分片内容")
    # VectorId 对应 Milvus 中的主键 ID
    vector_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="VectorId", comment="向量数据库中的记录ID")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="最后修改时间")