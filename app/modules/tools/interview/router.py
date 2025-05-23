# app/modules/tools/interview/router.py
import logging
from typing import Annotated, Optional, List # Ensure List is imported

from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File, Form, Body, status
)
from sqlalchemy.ext.asyncio import AsyncSession

# Core Imports
from app.core.config.settings import settings # Renamed from Settings for consistency
from app.core.database.session import get_db

# API Dependencies
from app.api.dependencies import (
    get_current_active_user_id,
    get_chatai_service_from_state,
    get_storage_service_from_state,
    get_prompt_template_service,
    get_job_persistence_service, # Added for job endpoints
    get_redis_service_from_state, # Needed for PromptTemplateService in DocumentService
    get_user_docs_milvus_service_from_state, # Needed for DocumentService
    # RateLimiter # Example if you add rate limiting
)

# Core DTOs and Enums
from app.core.dtos import ApiResponse, DocumentAppType, PagedResultDto, BaseIdRequestDto
from app.core.job.decorators import job_endpoint
from app.core.job.models import JobStatus # For potential use

# Module-specific DTOs
from app.modules.tools.interview.dtos import (
    CreateScenarioRequestDto, ScenarioCreationResultDto, ImportInterviewTextRequestDto,
    InterviewScenarioContentItemDto, ScenarioListRequestDto, ScenarioListItemDto,
    ScenarioDetailDto, QuestionsListRequestDto, QuestionListItemDto, QuestionDetailDto,
    QuestionsUpdateRequestDto, CreateInterviewSessionRequestDto, InterviewSessionInfoDto,
    StartSessionRequestDto, EndSessionRequestDto, RealTimeConnectionInfoDto,
    SaveInteractionRequestDto, InterviewSessionListRequestDto, InterviewSessionListItemDto,
    InterviewSessionDetailDto, EvaluateSessionRequestDto
)
from app.modules.tools.interview.enums import InterviewContentType

# TYPE_CHECKING block for services and repositories
from typing import TYPE_CHECKING

from app.modules.tools.interview.repositories.interaction_repository import InterviewInteractionRepository
from app.modules.tools.interview.repositories.job_position_repository import JobPositionRepository
from app.modules.tools.interview.repositories.question_repository import InterviewQuestionRepository
from app.modules.tools.interview.repositories.scenario_content_repository import InterviewScenarioContentRepository
from app.modules.tools.interview.repositories.scenario_repository import InterviewScenarioRepository
from app.modules.tools.interview.repositories.session_repository import InterviewSessionRepository
from app.modules.tools.interview.services.ai_evaluate_answer_service import AIEvaluateAnswerService
from app.modules.tools.interview.services.ai_question_service import AIQuestionService
from app.modules.tools.interview.services.ai_realtime_service import AIRealTimeService
from app.modules.tools.interview.services.interview_question_service import InterviewQuestionService
from app.modules.tools.interview.services.interview_scenario_service import InterviewScenarioService
from app.modules.tools.interview.services.interview_session_service import InterviewSessionService
from app.core.ai.chat.base import IChatAIService
from app.core.storage.base import IStorageService
from app.core.job.services import JobPersistenceService
from app.core.redis.service import RedisService
from app.core.ai.vector.base import IUserDocsMilvusService

from app.modules.base.prompts.services import PromptTemplateService
from app.modules.base.prompts.repositories import PromptTemplateRepository
from app.modules.base.knowledge.services.document_service import DocumentService
from app.modules.base.knowledge.services.extract_service import DocumentExtractService, IDocumentExtractService
from app.modules.base.knowledge.services.graph_service import KnowledgeGraphService

    


# Logger
logger = logging.getLogger(__name__)

# Router
router = APIRouter(
    prefix="/interview", # Consistent with original, ensure main app doesn't add /api again if this is a sub-router
    tags=["面试模拟器"],
)

# --- Repository Dependency Providers ---
def _get_scenario_repository(db: AsyncSession = Depends(get_db)) -> 'InterviewScenarioRepository':

    return InterviewScenarioRepository(db)

def _get_scenario_content_repository(db: AsyncSession = Depends(get_db)) -> 'InterviewScenarioContentRepository':

    return InterviewScenarioContentRepository(db)

def _get_job_position_repository(db: AsyncSession = Depends(get_db)) -> 'JobPositionRepository':

    return JobPositionRepository(db)

def _get_question_repository(db: AsyncSession = Depends(get_db)) -> 'InterviewQuestionRepository':
 
    return InterviewQuestionRepository(db)

def _get_session_repository(db: AsyncSession = Depends(get_db)) -> 'InterviewSessionRepository':

    return InterviewSessionRepository(db)

def _get_interaction_repository(db: AsyncSession = Depends(get_db)) -> 'InterviewInteractionRepository':
   
    return InterviewInteractionRepository(db)

# --- AI Service Dependency Providers ---
def _get_ai_question_service(
    # settings: Settings, # settings from app.core.config.settings directly
    prompt_template_service: 'PromptTemplateService' = Depends(get_prompt_template_service),
    ai_service: 'IChatAIService' = Depends(get_chatai_service_from_state)
) -> 'AIQuestionService':

    return AIQuestionService(settings, logging.getLogger(__name__ + ".AIQuestionService"), prompt_template_service, ai_service)

def _get_ai_evaluate_answer_service(
    # settings: Settings, # settings from app.core.config.settings directly
    prompt_template_service: 'PromptTemplateService' = Depends(get_prompt_template_service),
    ai_service: 'IChatAIService' = Depends(get_chatai_service_from_state)
) -> 'AIEvaluateAnswerService':

    return AIEvaluateAnswerService(settings, logging.getLogger(__name__ + ".AIEvaluateAnswerService"), prompt_template_service, ai_service)

def _get_ai_realtime_service(
    # settings: Settings, # settings from app.core.config.settings directly
    prompt_template_service: 'PromptTemplateService' = Depends(get_prompt_template_service),
    scenario_repository: 'InterviewScenarioRepository' = Depends(_get_scenario_repository),
    position_repository: 'JobPositionRepository' = Depends(_get_job_position_repository),
    question_repository: 'InterviewQuestionRepository' = Depends(_get_question_repository),
    session_repository: 'InterviewSessionRepository' = Depends(_get_session_repository)
) -> 'AIRealTimeService':
   
    return AIRealTimeService(
        settings, logging.getLogger(__name__ + ".AIRealTimeService"), prompt_template_service,
        scenario_repository, position_repository, question_repository, session_repository
    )

# --- DocumentService Provider (local to interview module, similar to knowledge module) ---
def _get_document_service(
    db: AsyncSession = Depends(get_db),
    user_docs_milvus_service: 'IUserDocsMilvusService' = Depends(get_user_docs_milvus_service_from_state), # For potential vectorization
    storage_service: Optional['IStorageService'] = Depends(get_storage_service_from_state),
    ai_service: 'IChatAIService' = Depends(get_chatai_service_from_state), # For potential vectorization/graphing
    redis_service: 'RedisService' = Depends(get_redis_service_from_state), # For PromptTemplateService if graph service is used
    job_persistence_service: 'JobPersistenceService' = Depends(get_job_persistence_service),
    # settings: Settings # settings from app.core.config.settings directly
) -> 'DocumentService':


    prompt_repo = PromptTemplateRepository(db=db)
    prompt_service = PromptTemplateService(db=db, repository=prompt_repo, redis_service=redis_service)
    
    extract_service_instance = DocumentExtractService() 
    graph_service_instance = KnowledgeGraphService(
        prompt_service=prompt_service,
        ai_service=ai_service 
    )
    # This DocumentService might be used for uploads that could optionally trigger full processing
    doc_service = DocumentService(
        db=db,
        user_docs_milvus_service=user_docs_milvus_service,
        storage_service=storage_service,
        extract_service=extract_service_instance,
        graph_service=graph_service_instance,
        ai_service=ai_service, # This AI service is for vectorization within DocumentService
        job_persistence_service=job_persistence_service,
        settings=settings,
    )
    return doc_service

# --- Main Interview Business Service Dependency Providers ---
def _get_interview_question_service(
    scenario_repository: 'InterviewScenarioRepository' = Depends(_get_scenario_repository),
    position_repository: 'JobPositionRepository' = Depends(_get_job_position_repository),
    question_repository: 'InterviewQuestionRepository' = Depends(_get_question_repository),
    ai_question_service: 'AIQuestionService' = Depends(_get_ai_question_service)
) -> 'InterviewQuestionService':

    return InterviewQuestionService(
        logging.getLogger(__name__ + ".InterviewQuestionService"),
        scenario_repository, position_repository, question_repository, ai_question_service
    )

def _get_interview_scenario_service(
    scenario_repository: 'InterviewScenarioRepository' = Depends(_get_scenario_repository),
    position_repository: 'JobPositionRepository' = Depends(_get_job_position_repository),
    question_repository: 'InterviewQuestionRepository' = Depends(_get_question_repository),
    scenario_content_repository: 'InterviewScenarioContentRepository' = Depends(_get_scenario_content_repository),
    document_service: 'DocumentService' = Depends(_get_document_service), # Uses the local _get_document_service
    question_service: 'InterviewQuestionService' = Depends(_get_interview_question_service)
) -> 'InterviewScenarioService':

    return InterviewScenarioService(
        logging.getLogger(__name__ + ".InterviewScenarioService"),
        scenario_repository, position_repository, question_repository,
        scenario_content_repository, document_service, question_service
    )

def _get_interview_session_service(
    session_repository: 'InterviewSessionRepository' = Depends(_get_session_repository),
    interaction_repository: 'InterviewInteractionRepository' = Depends(_get_interaction_repository),
    scenario_repository: 'InterviewScenarioRepository' = Depends(_get_scenario_repository),
    position_repository: 'JobPositionRepository' = Depends(_get_job_position_repository),
    question_repository: 'InterviewQuestionRepository' = Depends(_get_question_repository),
    real_time_service: 'AIRealTimeService' = Depends(_get_ai_realtime_service),
    evaluate_service: 'AIEvaluateAnswerService' = Depends(_get_ai_evaluate_answer_service),
    storage_service: 'IStorageService' = Depends(get_storage_service_from_state)
) -> 'InterviewSessionService':

    return InterviewSessionService(
        logging.getLogger(__name__ + ".InterviewSessionService"),
        session_repository, interaction_repository, scenario_repository,
        position_repository, question_repository, real_time_service,
        evaluate_service, storage_service
    )

# --- API Endpoints ---

# Scenario Management
@router.post("/scenarios/create", response_model=ApiResponse[ScenarioCreationResultDto], summary="创建面试场景")
async def create_scenario(
    request: CreateScenarioRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    scenario_service: 'InterviewScenarioService' = Depends(_get_interview_scenario_service)
):
    result = await scenario_service.create_scenario_async(user_id, request)
    return ApiResponse.success(data=result, message="面试场景创建成功")

@router.post("/scenarios/contents/upload", response_model=ApiResponse[int], summary="上传场景素材文档")
async def upload_scenario_document( # Renamed for clarity
    file: UploadFile = File(..., description="要上传的文档文件"),
    request_id: int = Form(..., alias="id", description="场景ID (scenario_id)"),
    user_id: int = Depends(get_current_active_user_id),
    document_service: 'DocumentService' = Depends(_get_document_service),
    scenario_service: 'InterviewScenarioService' = Depends(_get_interview_scenario_service)
):
    """
    上传文档作为面试场景的素材。
    注意：此处的 `request_id` 是 `scenario_id`。
    文档将关联到 `DocumentAppType.INTERVIEW`。
    默认不进行向量化和图谱化，仅存储。如需处理，需调整 DocumentService 调用或后续任务。
    """
    # The comment "只是文档存储，不需要向量化和图谱化" suggests skip_vectorize and skip_graph should be True.
    # However, the original code passed False, False. Adjust as per actual requirement.
    # If True, DocumentService's AI dependencies might be simplified for this context.
    document_id = await document_service.upload_document_async(
        user_id=user_id,
        app_type=DocumentAppType.INTERVIEW,
        file=file,
        title=file.filename or "",  # 使用文件名作为标题
        reference_id=request_id,     # 使用 reference_id 关联到场景
        need_vector=False,           # 面试场景不需要向量化
        need_graph=False             # 面试场景不需要图谱化
    )
    content_id = await scenario_service.add_scenario_content_async(
        user_id=user_id,
        scenario_id=request_id,
        content_type=int(InterviewContentType.FILE),
        source_document_id=str(document_id), # Ensure content_value is string
        source_content=""
    )
    return ApiResponse.success(data=content_id, message="文档上传成功并已关联到场景")

@router.post("/scenarios/contents/text", response_model=ApiResponse[int], summary="导入文本到场景")
async def import_scenario_text( # Renamed for clarity
    request: ImportInterviewTextRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    scenario_service: 'InterviewScenarioService' = Depends(_get_interview_scenario_service)
):
    content_id = await scenario_service.add_scenario_content_async(
        user_id=user_id,
        scenario_id=request.id, # This is scenario_id
        content_type=int(InterviewContentType.TEXT),
        source_document_id=0, # Or an appropriate placeholder if not a document_id
        source_content=request.text or ""
    )
    return ApiResponse.success(data=content_id, message="文本导入成功")

@router.post("/scenarios/contents/delete", response_model=ApiResponse[None], summary="删除场景内容项")
async def delete_scenario_content( # Renamed for clarity
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    scenario_service: 'InterviewScenarioService' = Depends(_get_interview_scenario_service)
):
    deleted = await scenario_service.delete_scenario_content_async(user_id, request.id)
    if deleted:
        return ApiResponse.success(message="内容删除成功")
    return ApiResponse.fail(message="内容删除失败", code=status.HTTP_400_BAD_REQUEST)

@router.post("/scenarios/contents/dtl", response_model=ApiResponse[InterviewScenarioContentItemDto], summary="获取场景内容详情")
async def get_scenario_content_detail( # Renamed for clarity
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    scenario_service: 'InterviewScenarioService' = Depends(_get_interview_scenario_service)
):
    content = await scenario_service.get_scenario_content_detail_async(user_id, request.id)
    return ApiResponse.success(data=content)

@router.post("/scenarios/detail", response_model=ApiResponse[ScenarioDetailDto], summary="获取场景详情")
async def get_scenario_detail( # Renamed for clarity
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    scenario_service: 'InterviewScenarioService' = Depends(_get_interview_scenario_service)
):
    result = await scenario_service.get_scenario_async(user_id, request.id)
    return ApiResponse.success(data=result)

@router.post("/scenarios/list", response_model=ApiResponse[PagedResultDto[ScenarioListItemDto]], summary="获取用户场景列表")
async def get_user_scenarios_list( # Renamed for clarity
    request: ScenarioListRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    scenario_service: 'InterviewScenarioService' = Depends(_get_interview_scenario_service)
):
    result = await scenario_service.get_user_scenarios_async(user_id, request)
    return ApiResponse.success(data=result)

@router.post("/scenarios/delete", response_model=ApiResponse[None], summary="删除场景")
async def delete_scenario(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    scenario_service: 'InterviewScenarioService' = Depends(_get_interview_scenario_service)
):
    deleted = await scenario_service.delete_scenario_async(user_id, request.id)
    if deleted:
        return ApiResponse.success(message="面试场景删除成功")
    return ApiResponse.fail(message="面试场景删除失败", code=status.HTTP_400_BAD_REQUEST)

# Question Management
@router.post("/questions/detail", response_model=ApiResponse[QuestionDetailDto], summary="获取问题详情")
async def get_question_detail( # Renamed
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    question_service: 'InterviewQuestionService' = Depends(_get_interview_question_service)
):
    result = await question_service.get_question_async(user_id, request.id)
    return ApiResponse.success(data=result)

@router.post("/questions/update", response_model=ApiResponse[None], summary="修改面试问题")
async def update_question(
    request: QuestionsUpdateRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    question_service: 'InterviewQuestionService' = Depends(_get_interview_question_service)
):
    updated = await question_service.update_question_async(user_id, request)
    if updated:
        return ApiResponse.success(message="面试题目修改成功")
    return ApiResponse.fail(message="面试题目修改失败", code=status.HTTP_400_BAD_REQUEST)

@router.post("/questions/list", response_model=ApiResponse[PagedResultDto[QuestionListItemDto]], summary="获取场景的问题列表")
async def get_questions_list_for_scenario( # Renamed
    request: QuestionsListRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    question_service: 'InterviewQuestionService' = Depends(_get_interview_question_service)
):
    result = await question_service.get_questions_async(user_id, request)
    return ApiResponse.success(data=result)

@router.post("/questions/generate", response_model=ApiResponse[None], summary="提交生成面试问题任务")
async def submit_generate_questions_task( # Renamed
    request: BaseIdRequestDto = Body(...), # request.id is scenario_id
    user_id: int = Depends(get_current_active_user_id),
    scenario_service: 'InterviewScenarioService' = Depends(_get_interview_scenario_service)
):
    """
    提交一个后台任务来为指定场景生成面试问题。
    这里的 request.id 是 scenario_id。
    """
    submitted = await scenario_service.start_analysis_question_async(user_id, request.id)
    if submitted:
        return ApiResponse.success(message="面试问题生成已提交，请稍后刷新查看结果")
    return ApiResponse.fail(message="面试问题生成提交失败", code=status.HTTP_400_BAD_REQUEST)


# Session Management
@router.post("/sessions/create", response_model=ApiResponse[InterviewSessionInfoDto], summary="创建面试会话")
async def create_session(
    request: CreateInterviewSessionRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    session_service: 'InterviewSessionService' = Depends(_get_interview_session_service)
):
    result = await session_service.create_session_async(user_id, request)
    return ApiResponse.success(data=result, message="面试会话创建成功")

@router.post("/sessions/start", response_model=ApiResponse[RealTimeConnectionInfoDto], summary="开始面试会话")
async def start_session(
    request: StartSessionRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    session_service: 'InterviewSessionService' = Depends(_get_interview_session_service)
):
    result = await session_service.start_session_async(user_id, request)
    return ApiResponse.success(data=result, message="面试会话已开始")

@router.post("/sessions/end", response_model=ApiResponse[None], summary="结束面试会话")
async def end_session(
    request: EndSessionRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    session_service: 'InterviewSessionService' = Depends(_get_interview_session_service)
):
    ended = await session_service.end_session_async(user_id, request)
    if ended:
        return ApiResponse.success(message="面试会话已结束")
    return ApiResponse.fail(message="面试会话结束失败", code=status.HTTP_400_BAD_REQUEST)

@router.post("/sessions/detail", response_model=ApiResponse[InterviewSessionDetailDto], summary="获取会话详情")
async def get_session_detail( # Renamed
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    session_service: 'InterviewSessionService' = Depends(_get_interview_session_service)
):
    result = await session_service.get_session_async(user_id, request.id)
    return ApiResponse.success(data=result)

@router.post("/sessions/list", response_model=ApiResponse[PagedResultDto[InterviewSessionListItemDto]], summary="获取用户的会话列表")
async def get_user_sessions_list( # Renamed
    request: InterviewSessionListRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    session_service: 'InterviewSessionService' = Depends(_get_interview_session_service)
):
    result = await session_service.get_user_sessions_async(user_id, request)
    return ApiResponse.success(data=result)

@router.post("/sessions/evaluate", response_model=ApiResponse[None], summary="提交评估面试任务")
async def submit_evaluate_session_task( # Renamed
    request: EvaluateSessionRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    session_service: 'InterviewSessionService' = Depends(_get_interview_session_service)
):
    submitted = await session_service.start_evaluate_session_async(user_id, request)
    if submitted:
        return ApiResponse.success(message="面试评估已提交，请稍后刷新查看结果")
    return ApiResponse.fail(message="面试评估提交失败", code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@router.post("/interactions/save", response_model=ApiResponse[None], summary="保存交互记录")
async def save_interaction(
    request: SaveInteractionRequestDto = Body(...),
    # user_id is not needed here if session_id is sufficient for auth/context,
    # or if called by system (Function Call)
    session_service: 'InterviewSessionService' = Depends(_get_interview_session_service)
):
    """保存交互记录（面试过程中主要通过Function Call调用）"""
    saved = await session_service.save_interaction_async(request)
    if saved:
        return ApiResponse.success(message="交互记录保存成功")
    return ApiResponse.fail(message="交互记录保存失败", code=status.HTTP_400_BAD_REQUEST)

# --- Task Processing Endpoints ---
@router.post(
    "/tasks/generate-questions/{job_id}/{scenario_id}", # scenario_id is params_id
    response_model=ApiResponse[None],
    summary="[内部] 执行生成面试问题任务",
    description="由调度器调用，自动处理锁和状态更新。"
)
@job_endpoint(default_can_retry=False)
async def execute_generate_questions_task(
    job_id: int,
    scenario_id: int, # This is the params_id for this task
    job_service: 'JobPersistenceService' = Depends(get_job_persistence_service), # Correctly injected
    scenario_service: 'InterviewScenarioService' = Depends(_get_interview_scenario_service)
):
    """处理生成面试问题任务"""
    await scenario_service.process_generate_questions_async(scenario_id)
    # job_service can be used here if explicit job updates are needed outside the decorator
    return ApiResponse.success(message="面试问题生成完成")

@router.post(
    "/tasks/evaluate-session/{job_id}/{session_id}", # session_id is params_id
    response_model=ApiResponse[None], # Assuming evaluation result is stored and not returned directly
    summary="[内部] 执行评估面试结果任务",
    description="由调度器调用，自动处理锁和状态更新。"
)
@job_endpoint(default_can_retry=False) # Or True if evaluation can be retried
async def execute_evaluate_session_task(
    job_id: int,
    session_id: int, # This is the params_id for this task
    job_service: 'JobPersistenceService' = Depends(get_job_persistence_service), # Correctly injected
    session_service: 'InterviewSessionService' = Depends(_get_interview_session_service)
):
    """处理评估面试结果任务"""
    # process_evaluate_session_async might return data, adjust response_model if needed
    await session_service.process_evaluate_session_async(session_id)
    return ApiResponse.success(message="面试评估完成")

