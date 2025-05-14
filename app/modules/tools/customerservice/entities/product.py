"""
客服系统实体模型：商品
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import BigInteger, String, DECIMAL, Text, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.session import Base



class Product(Base):
    """商品实体模型"""
    __tablename__ = "cs_product"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="UserId", comment="用户ID")
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, name="Code", comment="商品编码")
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, name="Name", comment="商品名称")
    price: Mapped[float] = mapped_column(DECIMAL(precision=10, scale=2), nullable=False, name="Price", comment="商品价格")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="Description", comment="商品描述")
    selling_points: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="SellingPoints", comment="商品卖点")
    stock: Mapped[int] = mapped_column(Integer, nullable=False, name="Stock", comment="库存")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1, name="Status", comment="状态：1-正常，0-下架")
    create_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="LastModifyDate", comment="最后修改时间")
    
    # 用于关联商品图片的属性，不映射到数据库
    images: List["ProductImage"] = []

class ProductImage(Base):
    """商品图片实体模型"""
    __tablename__ = "cs_product_image"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="ProductId", comment="商品ID")
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, name="ImageUrl", comment="图片URL")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, name="SortOrder", comment="排序顺序")
    create_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), name="LastModifyDate", comment="最后修改时间")