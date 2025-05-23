"""
面试模拟器模块的数据模型

此模块定义了面试模拟器功能的SQLAlchemy ORM模型，包括面试场景、职位、问题、会话和交互记录。
"""
import datetime
from sqlalchemy import BigInteger, DateTime, Integer, String, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Enum as SQLAlchemyEnum

from app.core.database.session import Base
from app.modules.tools.interview.enums import (
    InterviewScenarioStatus, 
    QuestionDifficulty, 
    InterviewSessionStatus, 
    InterviewerGender,
    InterviewContentType, 
    JobPositionQuestionStatusType,
    InterviewSessionEvaluateStatusType
)


class InterviewScenario(Base):
    """面试场景实体模型"""
    __tablename__ = "ism_interview_scenario"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    name: Mapped[str] = mapped_column(String(100), nullable=False, name="Name", comment="场景名称")
    description: Mapped[str] = mapped_column(String(500), nullable=False, name="Description", comment="场景描述")
    interviewer_name: Mapped[str] = mapped_column(String(50), nullable=False, name="InterviewerName", comment="面试官名称")
    interviewer_gender: Mapped[int] = mapped_column(
        Integer, nullable=False, name="InterviewerGender", comment="面试官性别"
    )
    generate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, name="GenerateCount", comment="生成次数")
    status: Mapped[int] = mapped_column(
        Integer, 
        nullable=False, 
        default=InterviewScenarioStatus.INIT.value,
        name="Status",
        comment="场景状态"
    )
    error_message: Mapped[str] = mapped_column(String(500), nullable=True, name="ErrorMessage", comment="错误消息")
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间"
    )
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="LastModifyDate", comment="更新时间"
    )
    
    # 关联关系
    job_positions = relationship("JobPosition", back_populates="scenario", cascade="all, delete-orphan")
    scenario_contents = relationship("InterviewScenarioContent", back_populates="scenario", cascade="all, delete-orphan")
    questions = relationship("InterviewQuestion", back_populates="scenario", cascade="all, delete-orphan")
    sessions = relationship("InterviewSession", back_populates="scenario", cascade="all, delete-orphan")


class JobPosition(Base):
    """面试职位实体模型"""
    __tablename__ = "ism_job_position"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    scenario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ism_interview_scenario.Id"), nullable=False, name="ScenarioId", comment="场景ID"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, name="Name", comment="职位名称")
    question_status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=JobPositionQuestionStatusType.PENDING,
        name="QuestionStatus",
        comment="问题生成状态"
    )
    error_message: Mapped[str] = mapped_column(String(500), nullable=True, name="ErrorMessage", comment="错误消息")
    level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=QuestionDifficulty.JUNIOR,
        name="Level",
        comment="职位级别"
    )
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间"
    )
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="LastModifyDate", comment="更新时间"
    )
    
    # 关联关系
    scenario = relationship("InterviewScenario", back_populates="job_positions")
    questions = relationship("InterviewQuestion", back_populates="job_position", cascade="all, delete-orphan")
    sessions = relationship("InterviewSession", back_populates="job_position", cascade="all, delete-orphan")


class InterviewScenarioContent(Base):
    """面试场景包含的内容项实体"""
    __tablename__ = "ism_interview_scenario_content"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    scenario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ism_interview_scenario.Id"), nullable=False, name="ScenarioId", comment="场景ID"
    )
    content_type: Mapped[int] = mapped_column(
        Integer, nullable=False, name="ContentType", comment="内容项类型"
    )
    source_document_id: Mapped[int] = mapped_column(
        BigInteger, nullable=True, name="SourceDocumentId", comment="源文档ID（如果是上传文档或URL）"
    )
    source_content: Mapped[str] = mapped_column(Text, nullable=True, name="SourceContent", comment="源文本内容")
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间"
    )
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="LastModifyDate", comment="更新时间"
    )
    
    # 关联关系
    scenario = relationship("InterviewScenario", back_populates="scenario_contents")


class InterviewQuestion(Base):
    """面试问题实体模型"""
    __tablename__ = "ism_interview_question"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    scenario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ism_interview_scenario.Id"), nullable=False, name="ScenarioId", comment="场景ID"
    )
    job_position_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ism_job_position.Id"), nullable=False, name="JobPositionId", comment="职位ID"
    )
    content: Mapped[str] = mapped_column(Text, nullable=True, name="Content", comment="问题内容")
    standard_answer: Mapped[str] = mapped_column(Text, nullable=True, name="StandardAnswer", comment="标准答案")
    question_type: Mapped[str] = mapped_column(String(50), nullable=True, name="QuestionType", comment="问题类型")
    difficulty: Mapped[QuestionDifficulty] = mapped_column(
        SQLAlchemyEnum(QuestionDifficulty), 
        nullable=False, 
        name="Difficulty", 
        comment="问题难度"
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, name="SortOrder", comment="排序顺序")
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间"
    )
    
    # 关联关系
    scenario = relationship("InterviewScenario", back_populates="questions")
    job_position = relationship("JobPosition", back_populates="questions")
    interactions = relationship("InterviewInteraction", back_populates="question")


class InterviewSession(Base):
    """面试会话实体模型"""
    __tablename__ = "ism_interview_session"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    interviewee_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="IntervieweeId", comment="面试者用户ID")
    scenario_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ism_interview_scenario.Id"), nullable=False, name="ScenarioId", comment="场景ID"
    )
    job_position_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ism_job_position.Id"), nullable=False, name="JobPositionId", comment="职位ID"
    )
    openai_session_id: Mapped[str] = mapped_column(
        String(100), nullable=True, name="OpenAISessionId", comment="OpenAI会话ID"
    )
    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=InterviewSessionStatus.NOT_STARTED.value,
        name="Status",
        comment="会话状态"
    )
    start_time: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=True, name="StartTime", comment="开始时间"
    )
    end_time: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=True, name="EndTime", comment="结束时间"
    )
    overall_score: Mapped[int] = mapped_column(
        Integer, nullable=True, default=0, name="OverallScore", comment="总体评分(0-100)"
    )
    overall_evaluation: Mapped[str] = mapped_column(
        Text, nullable=True, name="OverallEvaluation", comment="总体评价"
    )
    evaluate_status: Mapped[InterviewSessionEvaluateStatusType] = mapped_column(
        SQLAlchemyEnum(InterviewSessionEvaluateStatusType),
        nullable=False,
        default=InterviewSessionEvaluateStatusType.INIT,
        name="EvaluateStatus",
        comment="面试结果评估状态"
    )
    evaluate_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, name="EvaluateCount", comment="评估次数"
    )
    error_message: Mapped[str] = mapped_column(
        String(500), nullable=True, name="ErrorMessage", comment="面试结果评估错误消息"
    )
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间"
    )
    last_modify_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="LastModifyDate", comment="更新时间"
    )
    
    # 关联关系
    scenario = relationship("InterviewScenario", back_populates="sessions")
    job_position = relationship("JobPosition", back_populates="sessions")
    interactions = relationship("InterviewInteraction", back_populates="session", cascade="all, delete-orphan")


class InterviewInteraction(Base):
    """面试交互记录实体"""
    __tablename__ = "ism_interview_interaction"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ism_interview_session.Id"), nullable=False, name="SessionId", comment="会话ID"
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ism_interview_question.Id"), nullable=True, name="QuestionId", comment="问题ID（如果是预定义问题）"
    )
    question: Mapped[str] = mapped_column(Text, nullable=False, name="Question", comment="提问内容")
    answer: Mapped[str] = mapped_column(Text, nullable=False, name="Answer", comment="回答内容")
    question_audio_url: Mapped[str] = mapped_column(
        String(255), nullable=True, name="QuestionAudioUrl", comment="问题音频URL"
    )
    answer_audio_url: Mapped[str] = mapped_column(
        String(255), nullable=True, name="AnswerAudioUrl", comment="回答音频URL"
    )
    score: Mapped[int] = mapped_column(
        Integer, nullable=True, default=0, name="Score", comment="回答评分(0-100)"
    )
    evaluation: Mapped[str] = mapped_column(
        Text, nullable=True, name="Evaluation", comment="回答评价"
    )
    evaluate_status: Mapped[int] = mapped_column(
        Integer, nullable=True, default=0, name="EvaluateStatus", comment="评估状态（0=未评估，1=评估完成，-1=评估失败）"
    )
    interaction_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, name="InteractionOrder", comment="交互顺序"
    )
    create_date: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), name="CreateDate", comment="创建时间"
    )
    
    # 关联关系
    session = relationship("InterviewSession", back_populates="interactions")
    question = relationship("InterviewQuestion", back_populates="interactions")