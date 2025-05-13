# app/base/models.py
from sqlalchemy import BigInteger, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
import datetime

from app.core.database.session import Base # 导入共享的 Base

from .dtos import UserInfoDto

class User(Base):
    """
    用户实体 SQLAlchemy 模型。
    映射到数据库的 pb_users 表。
    """
    __tablename__ = "pb_users"
    # 指定表注释 (如果数据库支持并且需要，SQLAlchemy 本身不直接使用这个)
    __table_args__ = {'comment': '平台用户表'}

    # 主键 ID，使用雪花算法生成，因此数据库层面不是自增的
    # C# long 对应 BigInteger
    # 显式指定列名以匹配 C# 规范
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, comment="主键ID，使用雪花算法")

    # 手机号
    mobile_no: Mapped[Optional[str]] = mapped_column(String(32), index=True, unique=True, nullable=True, comment="手机号", name="MobileNo") # 添加索引和唯一约束

    # 用户名称
    name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="用户名称", name="Name") # C# DTO 是 50，实体是 32，这里改为 50

    # 密码 (哈希存储)
    password: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="密码（哈希存储）", name="Password")

    # 创建时间
    # default=func.now(): 使用数据库服务器的当前时间作为默认值
    # server_default=func.now(): 在数据库层面设置默认值
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间", name="CreateDate"
    )

    # 最后修改时间
    # onupdate=func.now(): 在更新时自动将此列设置为数据库服务器的当前时间
    # server_onupdate=func.now(): 在数据库层面设置更新触发器 (需要数据库支持)
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="最后修改时间", name="LastModifyDate"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, mobile_no='{self.mobile_no}', name='{self.name}')>"

    # 可以添加一个方法将模型转换为 DTO，但通常建议在服务层进行转换
    def to_user_info_dto(self) -> UserInfoDto:
        """将 User 模型转换为 UserInfoDto"""
        return UserInfoDto(
            id=self.id,
            mobileNo=self.mobile_no, # DTO 使用别名
            name=self.name,
            createDate=self.create_date # DTO 使用别名
        )