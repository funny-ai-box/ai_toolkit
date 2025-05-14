"""
客服系统实体模型：聊天会话和历史记录
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from sqlalchemy import BigInteger, String, Integer, DateTime, func, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.core.ai.dtos import ChatRoleType
from app.core.database.session import Base

class ChatSessionStatus(int, Enum):
    """会话状态枚举"""
    ENDED = 0  # 已结束
    ACTIVE = 1  # 进行中

class ChatSession(Base):
    """智能客服会话实体"""
    __tablename__ = "cs_chat_session"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="UserId", comment="用户ID")
    user_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, name="UserName", comment="用户姓名")
    session_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, name="SessionName", comment="会话名称")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1, name="Status", comment="状态：1-进行中，0-已结束")
    session_key: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, name="SessionKey", comment="会话唯一标识")
    create_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="LastModifyDate", comment="最后修改时间")
    
    # 聊天历史记录（非数据库字段）
    history: List["ChatHistory"] = []

class ChatHistory(Base):
    """会话历史记录实体"""
    __tablename__ = "cs_chat_history"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="SessionId", comment="会话ID")
    role: Mapped[ChatRoleType] = mapped_column(Integer, nullable=False, name="Role", comment="角色(user/assistant)")
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="Content", comment="对话内容")
    intent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, name="Intent", comment="用户意图")
    call_datas: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, name="CallDatas", comment="调用的函数返回的关键数据")
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, name="ImageUrl", comment="图片URL，如果是图片消息")
    create_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="LastModifyDate", comment="最后修改时间")

class ChatConnection(Base):
    """实时聊天连接实体"""
    __tablename__ = "cs_chat_connection"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="SessionId", comment="会话ID")
    connection_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, name="ConnectionId", comment="连接ID")
    client_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, name="ClientType", comment="客户端类型")
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1, name="IsActive", comment="是否活跃")
    last_active_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, name="LastActiveTime", comment="最后活跃时间")
    create_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="LastModifyDate", comment="最后修改时间")

class CustomerIntentType(str, Enum):
    """客户意图枚举"""
    GREETING = "GREETING"  # 用户打招呼
    PRODUCT_INQUIRY = "PRODUCT_INQUIRY"  # 用户询问商品信息
    ORDER_INQUIRY = "ORDER_INQUIRY"  # 用户询问订单信息
    SHIPPING_POLICY = "SHIPPING_POLICY"  # 用户询问物流政策
    RETURN_POLICY = "RETURN_POLICY"  # 用户询问退换货政策
    GENERAL_QUERY = "GENERAL_QUERY"  # 用户询问一般性问题
    SENSITIVE_QUERY = "SENSITIVE_QUERY"  # 用户询问敏感性问题
    COMPLAINT = "COMPLAINT"  # 用户投诉
    GRATITUDE = "GRATITUDE"  # 用户表示感谢
    FAREWELL = "FAREWELL"  # 用户道别