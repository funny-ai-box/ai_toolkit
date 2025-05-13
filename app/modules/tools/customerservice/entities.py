"""
智能客服模块实体定义
"""
import datetime
from enum import Enum
from typing import List, Optional
from sqlalchemy import BigInteger, DateTime, String, Text, DECIMAL, Integer, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.session import Base




class ChatSessionStatus(int, Enum):
    """会话状态枚举"""
    ENDED = 0  # 已结束
    ACTIVE = 1  # 进行中


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


class FunctionCallIntention(str, Enum):
    """Function调用的意图"""
    QUERY_PRODUCT = "QUERY_PRODUCT"  # 查询商品
    KNOWLEDGE_BASE = "KNOWLEDGE_BASE"  # 知识库检索


class ChatSession(Base):
    """智能客服会话实体"""
    __tablename__ = "cs_chat_session"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="UserId", comment="用户ID")
    user_name: Mapped[Optional[str]] = mapped_column(String(50), name="UserName", comment="用户姓名")
    session_name: Mapped[Optional[str]] = mapped_column(String(255), name="SessionName", comment="会话名称")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, name="Status", comment="状态：1-进行中，0-已结束")
    session_key: Mapped[Optional[str]] = mapped_column(String(36), name="SessionKey", comment="会话唯一标识")
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间"
    )
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="LastModifyDate", comment="最后修改时间"
    )


class ChatHistory(Base):
    """会话历史记录实体"""
    __tablename__ = "cs_chat_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="SessionId", comment="会话ID")
    role: Mapped[str] = mapped_column(String(10), nullable=False, name="Role", comment="角色(user/assistant)")
    content: Mapped[Optional[str]] = mapped_column(Text, name="Content", comment="对话内容")
    intent: Mapped[Optional[str]] = mapped_column(String(50), name="Intent", comment="用户意图")
    call_datas: Mapped[Optional[str]] = mapped_column(String(50), name="CallDatas", comment="调用的函数返回的关键数据")
    image_url: Mapped[Optional[str]] = mapped_column(String(500), name="ImageUrl", comment="图片URL，如果是图片消息")
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间"
    )
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="LastModifyDate", comment="最后修改时间"
    )


class ChatConnection(Base):
    """实时聊天连接实体"""
    __tablename__ = "cs_chat_connection"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="SessionId", comment="会话ID")
    connection_id: Mapped[Optional[str]] = mapped_column(String(100), name="ConnectionId", comment="连接ID")
    client_type: Mapped[Optional[str]] = mapped_column(String(50), name="ClientType", comment="客户端类型")
    is_active: Mapped[int] = mapped_column(SmallInteger, default=1, name="IsActive", comment="是否活跃")
    last_active_time: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="LastActiveTime", comment="最后活跃时间"
    )
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间"
    )
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="LastModifyDate", comment="最后修改时间"
    )


class Product(Base):
    """商品实体"""
    __tablename__ = "cs_product"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="UserId", comment="用户ID")
    code: Mapped[Optional[str]] = mapped_column(String(50), name="Code", comment="商品编码")
    name: Mapped[Optional[str]] = mapped_column(String(255), name="Name", comment="商品名称")
    price: Mapped[float] = mapped_column(DECIMAL(precision=10, scale=2), name="Price", comment="商品价格")
    description: Mapped[Optional[str]] = mapped_column(Text, name="Description", comment="商品描述")
    selling_points: Mapped[Optional[str]] = mapped_column(Text, name="SellingPoints", comment="商品卖点")
    stock: Mapped[int] = mapped_column(Integer, default=0, name="Stock", comment="库存")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, name="Status", comment="状态：1-正常，0-下架")
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间"
    )
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="LastModifyDate", comment="最后修改时间"
    )


class ProductImage(Base):
    """商品图片实体"""
    __tablename__ = "cs_product_image"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="ProductId", comment="商品ID")
    image_url: Mapped[Optional[str]] = mapped_column(String(500), name="ImageUrl", comment="图片URL")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, name="SortOrder", comment="排序顺序")
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间"
    )
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="LastModifyDate", comment="最后修改时间"
    )