# app/core/job/models.py
from sqlalchemy import BigInteger, String, DateTime, func, TEXT, Index, Integer, Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column
import datetime
from enum import IntEnum
from typing import Optional

from app.core.database.session import Base
from app.core.utils.snowflake import generate_id # 假设雪花 ID 生成器可用

# --- 枚举定义 ---
class JobStatus(IntEnum):
    """任务持久化状态"""
    PENDING = 0     # 待处理
    PROCESSING = 1  # 处理中
    COMPLETED = 2   # 处理成功
    FAILED = 3      # 处理失败

class JobLogLevel(IntEnum):
    """任务日志级别"""
    INFO = 1
    WARNING = 2
    ERROR = 3

# --- JobConfig Model ---
class JobConfig(Base):
    """任务配置表模型"""
    __tablename__ = "pb_job_config"
    __table_args__ = (
        Index('uq_jobconfig_tasktype', 'TaskType', unique=True), # 索引仍使用数据库列名
        {'comment': '任务配置表'}
    )

    # Python: snake_case, DB: PascalCase via name=
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=generate_id, name="Id", comment="主键ID，雪花算法")
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, name="TaskType", comment="任务类型唯一标识")
    api_path: Mapped[str] = mapped_column(String(500), nullable=False, name="ApiPath", comment="任务执行的 API 路径模板")
    http_method: Mapped[str] = mapped_column(String(10), nullable=False, default="POST", name="HttpMethod", comment="调用 API 的 HTTP 方法")
    default_max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3, name="DefaultMaxRetries", comment="默认最大重试次数")
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, name="Description", comment="任务描述")
    # 时间戳字段使用指定的大驼峰名称
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="更新时间")

# --- JobPersist Model  ---
class JobPersist(Base):
    """任务持久化表模型"""
    __tablename__ = "pb_job_persist"
    __table_args__ = (
        Index('idx_jobpersist_status_scheduled', 'Status', 'ScheduledAt'),
        Index('idx_jobpersist_type_params', 'TaskType', 'ParamsId'),
        {'comment': '任务持久化表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=generate_id, name="Id", comment="主键ID，雪花算法")
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True, name="TaskType", comment="任务类型唯一标识")
    params_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True, name="ParamsId", comment="关联的参数 ID")
    params_data: Mapped[Optional[str]] = mapped_column(TEXT, nullable=True, name="ParamsData", comment="其他参数 (JSON 格式)")
    status: Mapped[JobStatus] = mapped_column(Integer, nullable=False, default=JobStatus.PENDING.value, index=True, name="Status", comment="任务状态 (存储整数)")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, name="RetryCount", comment="当前重试次数")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3, name="MaxRetries", comment="最大允许重试次数")
    last_error: Mapped[Optional[str]] = mapped_column(TEXT, nullable=True, name="LastError", comment="最后一次错误信息")
    scheduled_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True, index=True, name="ScheduledAt", comment="计划执行时间")
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True, name="StartedAt", comment="实际开始执行时间")
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True, name="CompletedAt", comment="任务完成或失败时间")
    # 时间戳字段
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="更新时间")
 
 # --- JobPersistHistory Model (结构与 JobPersist 相同) ---
class JobPersistHistory(Base):
    """任务持久化历史表模型 (结构同 JobPersist)"""
    __tablename__ = "pb_job_persist_history"
    __table_args__ = (
        Index('idx_jobhist_status_completed', 'Status', 'CompletedAt'), # 按状态和完成时间查询
        Index('idx_jobhist_type_params', 'TaskType', 'ParamsId'),
        Index('idx_jobhist_created', 'CreateDate'), # 按创建时间清理
        {'comment': '任务持久化历史表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, name="Id", comment="主键ID，雪花算法")
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True, name="TaskType", comment="任务类型唯一标识")
    params_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True, name="ParamsId", comment="关联的参数 ID")
    params_data: Mapped[Optional[str]] = mapped_column(TEXT, nullable=True, name="ParamsData", comment="其他参数 (JSON 格式)")
    status: Mapped[JobStatus] = mapped_column(Integer, nullable=False, default=JobStatus.PENDING.value, index=True, name="Status", comment="任务状态 (存储整数)")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, name="RetryCount", comment="当前重试次数")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3, name="MaxRetries", comment="最大允许重试次数")
    last_error: Mapped[Optional[str]] = mapped_column(TEXT, nullable=True, name="LastError", comment="最后一次错误信息")
    scheduled_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True, index=True, name="ScheduledAt", comment="计划执行时间")
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True, name="StartedAt", comment="实际开始执行时间")
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True, name="CompletedAt", comment="任务完成或失败时间")
    # 时间戳字段
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), name="LastModifyDate", comment="更新时间")
    # 可以再加一个迁移时间戳字段
    migrated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="MigratedAt", comment="迁移到历史表的时间")


# --- JobPersistLog Model  ---
class JobPersistLog(Base):
    """任务持久化日志表模型"""
    __tablename__ = "pb_job_persist_log"
    __table_args__ = (
        Index('idx_joblog_jobid', 'JobId'),
        {'comment': '任务持久化日志表'}
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=generate_id, name="Id", comment="日志主键ID，雪花算法")
    job_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="JobId", comment="关联的任务持久化 ID")
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=func.now(), name="Timestamp", comment="日志时间戳")
    level: Mapped[JobLogLevel] = mapped_column(Integer, nullable=False, default=JobLogLevel.INFO.value, name="Level", comment="日志级别 (存储整数)")
    message: Mapped[Optional[str]] = mapped_column(TEXT, nullable=True, name="Message", comment="日志消息")