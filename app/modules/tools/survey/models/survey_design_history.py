import datetime
from sqlalchemy import BigInteger, DateTime, String, Text, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database.session import Base 
from app.core.ai.dtos import ChatRoleType

class SurveyDesignHistory(Base):
    """AI设计会话历史"""
    __tablename__ = "survey_design_history"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="TaskId", comment="任务ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    role: Mapped[str] = mapped_column(String(50), nullable=False, name="Role", comment="消息角色(用户/AI)")
    content: Mapped[str] = mapped_column(Text, nullable=True, name="Content", comment="消息内容")
    complete_json_config: Mapped[str] = mapped_column(Text, nullable=True, name="CompleteJsonConfig", 
                                                     comment="完整JSON配置,当AI生成完整问卷配置时，将JSON保存在此字段")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, 
                                                          server_default=func.now(), name="CreateDate", comment="创建时间")
