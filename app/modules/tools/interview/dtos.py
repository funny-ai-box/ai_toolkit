"""
面试模拟器模块的数据传输对象

此模块定义了面试模拟器功能的Pydantic模型，用于API请求和响应的数据验证和序列化。
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime

from app.core.dtos import ApiResponse, PagedResultDto, BasePageRequestDto, BaseIdRequestDto
from app.modules.tools.interview.enums import (
    InterviewScenarioStatus, 
    QuestionDifficulty, 
    InterviewSessionStatus, 
    InterviewerGender,
    InterviewContentType, 
    JobPositionQuestionStatusType,
    InterviewSessionEvaluateStatusType
)


# 职位DTO
class JobPositionDto(BaseModel):
    """职位DTO"""
    id: Optional[int] = Field(None, alias="id", description="职位ID（创建时不需要）")
    name: str = Field(..., alias="name", description="职位名称", min_length=2, max_length=100)
    level: QuestionDifficulty = Field(QuestionDifficulty.JUNIOR, alias="level", description="职位级别")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


class JobPositionResponseDto(BaseModel):
    """职位响应DTO"""
    id: Optional[int] = Field(None, alias="id", description="职位ID")
    name: str = Field(..., alias="name", description="职位名称")
    level: QuestionDifficulty = Field(..., alias="level", description="职位级别")
    question_status: JobPositionQuestionStatusType = Field(..., alias="questionStatus", description="问题生成状态")
    error_message: Optional[str] = Field(None, alias="errorMessage", description="错误消息")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


# 创建面试场景请求DTO
class CreateScenarioRequestDto(BaseModel):
    """创建面试场景请求DTO"""
    name: str = Field(..., alias="name", description="场景名称", min_length=2, max_length=100)
    description: str = Field("", alias="description", description="场景描述", max_length=500)
    interviewer_name: str = Field(..., alias="interviewerName", description="面试官名称", min_length=2, max_length=50)
    interviewer_gender: InterviewerGender = Field(InterviewerGender.MALE, alias="interviewerGender", description="面试官性别")
    job_positions: List[JobPositionDto] = Field(..., alias="jobPositions", description="职位列表", min_items=1)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class ImportInterviewTextRequestDto(BaseModel):
    """导入文本请求DTO"""
    id: int = Field(..., alias="id", description="场景ID")
    text: str = Field(..., alias="text", description="文本内容", max_length=20000)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class ScenarioCreationResultDto(BaseModel):
    """场景创建结果DTO"""
    id: int = Field(..., alias="id", description="场景ID")
    name: str = Field(..., alias="name", description="场景名称")
    status: InterviewScenarioStatus = Field(..., alias="status", description="场景状态")
    job_positions: List[JobPositionDto] = Field([], alias="jobPositions", description="职位列表")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


# 场景列表相关DTO
class ScenarioListRequestDto(BasePageRequestDto):
    """场景列表查询请求DTO"""
    name: Optional[str] = Field(None, alias="name", description="场景名称（模糊查询）")
    status: Optional[InterviewScenarioStatus] = Field(None, alias="status", description="场景状态")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class ScenarioContentItemDto(BaseModel):
    """文档内容项DTO"""
    id: int = Field(..., alias="id", description="内容项ID")
    content_type: InterviewContentType = Field(..., alias="contentType", description="内容类型")
    source_document_id: int = Field(..., alias="sourceDocumentId", description="文档Id")
    source_content: Optional[str] = Field(None, alias="sourceContent", description="文本或文件或网页的内容")
    source_document_title: Optional[str] = Field(None, alias="sourceDocumentTitle", description="文档标题")
    source_document_original_name: Optional[str] = Field(None, alias="sourceDocumentOriginalName", description="文档原始文件名")
    source_document_source_url: Optional[str] = Field(None, alias="sourceDocumentSourceUrl", description="文档来源链接")
    source_document_status: int = Field(..., alias="sourceDocumentStatus", description="文档处理进度")
    source_document_process_message: Optional[str] = Field(None, alias="sourceDocumentProcessMessage", description="文档处理进度消息")
    create_date: datetime = Field(..., alias="createDate", description="创建时间")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


class InterviewScenarioContentItemDto(BaseModel):
    """场景内容项DTO"""
    id: int = Field(..., alias="id", description="内容项ID")
    content_type: InterviewContentType = Field(..., alias="contentType", description="内容类型")
    source_document_id: int = Field(..., alias="sourceDocumentId", description="文档Id")
    source_content: Optional[str] = Field(None, alias="sourceContent", description="文本或文件或网页的内容")
    source_document_title: Optional[str] = Field(None, alias="sourceDocumentTitle", description="文档标题")
    source_document_original_name: Optional[str] = Field(None, alias="sourceDocumentOriginalName", description="文档原始文件名")
    source_document_source_url: Optional[str] = Field(None, alias="sourceDocumentSourceUrl", description="文档来源链接")
    source_document_status: int = Field(..., alias="sourceDocumentStatus", description="文档处理进度")
    source_document_process_message: Optional[str] = Field(None, alias="sourceDocumentProcessMessage", description="文档处理进度消息")
    create_date: datetime = Field(..., alias="createDate", description="创建时间")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


class ScenarioListItemDto(BaseModel):
    """场景列表项DTO"""
    id: int = Field(..., alias="id", description="场景ID")
    name: str = Field(..., alias="name", description="场景名称")
    description: str = Field(..., alias="description", description="场景描述")
    interviewer_name: str = Field(..., alias="interviewerName", description="面试官名称")
    interviewer_gender: InterviewerGender = Field(..., alias="interviewerGender", description="面试官性别")
    job_position_count: int = Field(..., alias="jobPositionCount", description="职位数量")
    content_item_count: int = Field(..., alias="contentItemCount", description="内容项数量")
    status: InterviewScenarioStatus = Field(..., alias="status", description="场景状态")
    create_date: datetime = Field(..., alias="createDate", description="创建时间")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


class ScenarioDetailDto(BaseModel):
    """场景详情DTO"""
    id: int = Field(..., alias="id", description="场景ID")
    name: str = Field(..., alias="name", description="场景名称")
    description: str = Field(..., alias="description", description="场景描述")
    interviewer_name: str = Field(..., alias="interviewerName", description="面试官名称")
    interviewer_gender: InterviewerGender = Field(..., alias="interviewerGender", description="面试官性别")
    status: InterviewScenarioStatus = Field(..., alias="status", description="场景状态")
    job_positions: List[JobPositionResponseDto] = Field([], alias="jobPositions", description="职位列表")
    content_items: Optional[List[ScenarioContentItemDto]] = Field(None, alias="contentItems", description="内容项列表")
    create_date: datetime = Field(..., alias="createDate", description="创建时间")
    last_modify_date: datetime = Field(..., alias="lastModifyDate", description="更新时间")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


# 问题相关DTO
class QuestionsListRequestDto(BasePageRequestDto):
    """问题列表查询请求DTO"""
    scenario_id: int = Field(..., alias="scenarioId", description="场景ID")
    job_position_id: Optional[int] = Field(None, alias="jobPositionId", description="职位ID")
    difficulty: Optional[QuestionDifficulty] = Field(None, alias="difficulty", description="问题难度")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class QuestionListItemDto(BaseModel):
    """问题列表项DTO"""
    id: int = Field(..., alias="id", description="问题ID")
    job_position_id: int = Field(..., alias="jobPositionId", description="职位ID")
    job_position_name: str = Field(..., alias="jobPositionName", description="职位名称")
    content: str = Field(..., alias="content", description="问题内容")
    short_answer: str = Field(..., alias="shortAnswer", description="标准答案（简短版）")
    question_type: Optional[str] = Field(None, alias="questionType", description="问题类型")
    difficulty: QuestionDifficulty = Field(..., alias="difficulty", description="问题难度")
    sort_order: int = Field(..., alias="sortOrder", description="排序顺序")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


class QuestionDetailDto(BaseModel):
    """问题详情DTO"""
    id: int = Field(..., alias="id", description="问题ID")
    scenario_id: int = Field(..., alias="scenarioId", description="场景ID")
    job_position_id: int = Field(..., alias="jobPositionId", description="职位ID")
    job_position_name: str = Field(..., alias="jobPositionName", description="职位名称")
    content: str = Field(..., alias="content", description="问题内容")
    standard_answer: str = Field(..., alias="standardAnswer", description="标准答案")
    question_type: Optional[str] = Field(None, alias="questionType", description="问题类型")
    difficulty: QuestionDifficulty = Field(..., alias="difficulty", description="问题难度")
    sort_order: int = Field(..., alias="sortOrder", description="排序顺序")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


class QuestionsUpdateRequestDto(BaseModel):
    """面试题目修改的请求"""
    question_id: int = Field(..., alias="questionId", description="题目ID")
    content: str = Field(..., alias="content", description="面试问题", min_length=2, max_length=100)
    answer: str = Field(..., alias="answer", description="问题答案", max_length=500)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


# AI相关DTO
class AIQuestionResponseDto(BaseModel):
    """AI输出问题的响应格式"""
    type: Optional[str] = Field(None, alias="type", description="问题类型：字符串，代表问题类型的关键字")
    difficulty: QuestionDifficulty = Field(..., alias="difficulty", description="问题难度")
    content: Optional[str] = Field(None, alias="content", description="问题内容")
    answer: Optional[str] = Field(None, alias="answer", description="答案")
    sort_order: int = Field(..., alias="sortOrder", description="排序")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


class AIEvaluateAnswerResponseDto(BaseModel):
    """AI 对每个问题答案的评分"""
    score: int = Field(..., alias="score", description="评分")
    evaluation: Optional[str] = Field(None, alias="evaluation", description="评语")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


# 会话相关DTO
class CreateInterviewSessionRequestDto(BaseModel):
    """创建面试会话请求DTO"""
    scenario_id: int = Field(..., alias="scenarioId", description="场景ID")
    job_position_id: int = Field(..., alias="jobPositionId", description="职位ID")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class InterviewSessionInfoDto(BaseModel):
    """面试会话简要信息DTO"""
    id: int = Field(..., alias="id", description="会话ID")
    scenario_id: int = Field(..., alias="scenarioId", description="场景ID")
    scenario_name: str = Field(..., alias="scenarioName", description="场景名称")
    interviewer_name: str = Field(..., alias="interviewerName", description="面试官名称")
    job_position_id: int = Field(..., alias="jobPositionId", description="职位ID")
    job_position_name: str = Field(..., alias="jobPositionName", description="职位名称")
    status: InterviewSessionStatus = Field(..., alias="status", description="会话状态")
    openai_session_token: Optional[str] = Field(None, alias="openAISessionToken", description="OpenAI会话Token (仅在开始面试时返回)")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


class InterviewSessionListRequestDto(BasePageRequestDto):
    """面试会话列表请求DTO"""
    scenario_id: Optional[int] = Field(None, alias="scenarioId", description="场景ID")
    job_position_id: Optional[int] = Field(None, alias="jobPositionId", description="职位ID")
    status: Optional[InterviewSessionStatus] = Field(None, alias="status", description="会话状态")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class InterviewSessionListItemDto(BaseModel):
    """面试会话列表项DTO"""
    id: int = Field(..., alias="id", description="会话ID")
    scenario_name: str = Field(..., alias="scenarioName", description="场景名称")
    job_position_name: str = Field(..., alias="jobPositionName", description="职位名称")
    status: InterviewSessionStatus = Field(..., alias="status", description="会话状态")
    start_time: Optional[datetime] = Field(None, alias="startTime", description="开始时间")
    end_time: Optional[datetime] = Field(None, alias="endTime", description="结束时间")
    duration_minutes: Optional[int] = Field(None, alias="durationMinutes", description="持续时间（分钟）")
    overall_score: Optional[int] = Field(None, alias="overallScore", description="总体评分")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


class InteractionDto(BaseModel):
    """交互记录DTO"""
    id: int = Field(..., alias="id", description="交互ID")
    question_id: Optional[int] = Field(None, alias="questionId", description="问题ID")
    question: str = Field(..., alias="question", description="提问内容")
    answer: str = Field(..., alias="answer", description="回答内容")
    question_audio_url: Optional[str] = Field(None, alias="questionAudioUrl", description="问题音频URL")
    answer_audio_url: Optional[str] = Field(None, alias="answerAudioUrl", description="回答音频URL")
    score: Optional[int] = Field(None, alias="score", description="回答评分")
    evaluation: Optional[str] = Field(None, alias="evaluation", description="回答评价")
    interaction_order: int = Field(..., alias="interactionOrder", description="交互顺序")
    create_date: datetime = Field(..., alias="createDate", description="创建时间")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


class InterviewSessionDetailDto(BaseModel):
    """面试会话详情DTO"""
    id: int = Field(..., alias="id", description="会话ID")
    scenario_id: int = Field(..., alias="scenarioId", description="场景ID")
    scenario_name: str = Field(..., alias="scenarioName", description="场景名称")
    job_position_id: int = Field(..., alias="jobPositionId", description="职位ID")
    job_position_name: str = Field(..., alias="jobPositionName", description="职位名称")
    status: InterviewSessionStatus = Field(..., alias="status", description="会话状态")
    start_time: Optional[datetime] = Field(None, alias="startTime", description="开始时间")
    end_time: Optional[datetime] = Field(None, alias="endTime", description="结束时间")
    duration_minutes: Optional[int] = Field(None, alias="durationMinutes", description="持续时间（分钟）")
    overall_score: Optional[int] = Field(None, alias="overallScore", description="总体评分")
    overall_evaluation: Optional[str] = Field(None, alias="overallEvaluation", description="总体评价")
    evaluate_status: InterviewSessionEvaluateStatusType = Field(..., alias="evaluateStatus", description="面试结果评估状态")
    evaluate_count: int = Field(0, alias="evaluateCount", description="评估次数")
    error_message: Optional[str] = Field(None, alias="errorMessage", description="面试结果评估错误消息")
    interactions: List[InteractionDto] = Field([], alias="interactions", description="交互记录列表")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


class StartSessionRequestDto(BaseModel):
    """开始面试会话请求DTO"""
    session_id: int = Field(..., alias="sessionId", description="会话ID")
    noise_reduction: Optional[str] = Field(None, alias="noiseReduction", description="音频降噪配置")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class EndSessionRequestDto(BaseModel):
    """结束面试会话请求DTO"""
    session_id: int = Field(..., alias="sessionId", description="会话ID")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class RealTimeSessionResponse(BaseModel):
    """OpenAI RealTime会话响应"""
    id: str = Field(..., alias="id", description="会话ID")
    model: str = Field(..., alias="model", description="模型")
    modalities: List[str] = Field(..., alias="modalities", description="模态")
    instructions: str = Field(..., alias="instructions", description="指令")
    voice: str = Field(..., alias="voice", description="语音")
    client_secret_value: str = Field(..., alias="clientSecretValue", description="客户端密钥")
    client_secret_expires_at: int = Field(..., alias="clientSecretExpiresAt", description="客户端密钥过期时间")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class RealTimeConnectionInfoDto(BaseModel):
    """OpenAI RealTime会话连接信息DTO"""
    session_token: str = Field(..., alias="sessionToken", description="会话令牌")
    session_info: InterviewSessionInfoDto = Field(..., alias="sessionInfo", description="会话信息")
    questions: List[QuestionListItemDto] = Field([], alias="questions", description="面试问题列表（预加载）")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


class SaveInteractionRequestDto(BaseModel):
    """保存交互记录请求DTO (用于Function Call)"""
    session_id: int = Field(..., alias="sessionId", description="会话ID")
    question_id: Optional[int] = Field(None, alias="questionId", description="问题ID（预设问题时使用）")
    question: str = Field(..., alias="question", description="提问内容")
    answer: str = Field(..., alias="answer", description="回答内容")
    question_audio_base64: Optional[str] = Field(None, alias="questionAudioBase64", description="问题音频数据(Base64编码)")
    answer_audio_base64: Optional[str] = Field(None, alias="answerAudioBase64", description="回答音频数据(Base64编码)")
    interaction_order: int = Field(..., alias="interactionOrder", description="交互顺序")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class EvaluateSessionRequestDto(BaseModel):
    """评估面试请求DTO"""
    session_id: int = Field(..., alias="sessionId", description="会话ID")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True


class AnswerEvaluationDto(BaseModel):
    """回答评估DTO"""
    interaction_id: int = Field(..., alias="interactionId", description="交互ID")
    question: str = Field(..., alias="question", description="问题内容")
    answer: str = Field(..., alias="answer", description="回答内容")
    score: int = Field(..., alias="score", description="回答评分")
    evaluation: str = Field(..., alias="evaluation", description="回答评价")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True


class EvaluationResultDto(BaseModel):
    """面试评估结果DTO"""
    session_id: int = Field(..., alias="sessionId", description="会话ID")
    success: bool = Field(..., alias="success", description="评估状态（成功/失败）")
    overall_score: Optional[int] = Field(None, alias="overallScore", description="总体评分")
    overall_evaluation: Optional[str] = Field(None, alias="overallEvaluation", description="总体评价")
    answer_evaluations: Optional[List[AnswerEvaluationDto]] = Field(None, alias="answerEvaluations", description="回答评估列表")

    class Config:
        populate_by_name = True
        from_attributes = True
        arbitrary_types_allowed = True