# app/modules/tools/podcast/router.py
import logging
from typing import Dict, List, Optional, Any

from fastapi import (
    APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Body
)
from sqlalchemy.ext.asyncio import AsyncSession
import httpx # For factories used by services

from app.core.database.session import get_db
from app.core.config.settings import Settings as GlobalSettings
from app.api.dependencies import (
    get_current_active_user_id,
    RateLimiter,
    get_job_persistence_service,
)
from app.core.job.decorators import job_endpoint
from app.core.dtos import ApiResponse, BaseIdRequestDto, PagedResultDto, BaseIdResponseDto, DocumentAppType
from app.core.exceptions import BusinessException, NotFoundException

# Podcast specific DTOs, Models, Services, Repositories
# IMPORTANT: The NameError "Fields must not use names with leading underscores"
# likely originates from a field definition within one of the DTOs imported below (e.g., CreatePodcastRequestDto).
# Please check your DTOs (in app.modules.tools.podcast.dtos) for field names starting with an underscore.
from app.modules.tools.podcast import dtos, models, services, repositories

# Knowledge base document service (cross-module dependency)
from app.modules.base.knowledge.services.document_service import DocumentService as KnowledgeDocumentService
from app.modules.base.knowledge.repositories import (
    DocumentRepository as KnowledgeDocumentRepository,
    DocumentContentRepository as KnowledgeDocumentChunkRepository, # Aliased to match usage
    DocumentLogRepository as KnowledgeDocumentLogRepository,
    DocumentGraphRepository as KnowledgeKnowledgeGraphRepository,  # Aliased to match usage
)
from app.modules.base.knowledge.services.extract_service import DocumentExtractService as KnowledgeExtractService
from app.modules.base.knowledge.services.graph_service import KnowledgeGraphService as KnowledgeGraphServiceInternal

# Prompt service (cross-module dependency)
from app.modules.base.prompts.services import PromptTemplateService
from app.modules.base.prompts.repositories import PromptTemplateRepository

# Core AI services (interfaces and factory functions that might be used by Knowledge service)
from app.core.ai.chat.factory import get_chat_ai_service # Factory function
from app.core.ai.vector.base import IUserDocsMilvusService
from app.core.storage.base import IStorageService
from app.core.redis.service import RedisService
from app.core.job.services import JobPersistenceService

# Typing for services if needed for string hints, though direct imports are used here.
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.modules.tools.podcast.services import PodcastService, AIScriptService, AISpeechService, PodcastProcessingService
    from app.modules.base.knowledge.services.document_service import DocumentService as KnowledgeDocumentServiceTyped


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/podcast",
    tags=["Podcast - AI播客工具"],
)

# --- Internal Dependency Injection Factories for Podcast Module ---

def _get_knowledge_document_service(
    db: AsyncSession = Depends(get_db),
    settings: GlobalSettings = Depends(GlobalSettings),
    user_docs_milvus_service: IUserDocsMilvusService = Depends(lambda: GlobalSettings().app_state.user_docs_milvus_service),
    storage_service: Optional[IStorageService] = Depends(lambda: GlobalSettings().app_state.storage_service),
    http_client: httpx.AsyncClient = Depends(lambda: GlobalSettings().app_state.http_client),
    redis_service: RedisService = Depends(lambda: GlobalSettings().app_state.redis_service),
    job_persistence_service: JobPersistenceService = Depends(get_job_persistence_service),
) -> KnowledgeDocumentService: # Using direct type hint as class is imported
    """Factory for KnowledgeDocumentService."""
    doc_repo = KnowledgeDocumentRepository(db)
    chunk_repo = KnowledgeDocumentChunkRepository(db)
    log_repo = KnowledgeDocumentLogRepository(db)
    graph_repo = KnowledgeKnowledgeGraphRepository(db)

    prompt_db_repo = PromptTemplateRepository(db=db)
    prompt_service = PromptTemplateService(db=db, repository=prompt_db_repo, redis_service=redis_service)
    
    chat_ai_service_for_graph = get_chat_ai_service(
        provider_type_str=settings.default_chat_provider,
        shared_http_client=http_client
    )
    
    extract_svc = KnowledgeExtractService()
    graph_svc_internal = KnowledgeGraphServiceInternal(
        prompt_service=prompt_service, 
        ai_service=chat_ai_service_for_graph
    )
    
    chat_ai_service_for_embedding = GlobalSettings().app_state.chat_ai_service 

    return KnowledgeDocumentService(
        db=db,
        settings=settings,
        doc_repo=doc_repo,
        chunk_repo=chunk_repo,
        log_repo=log_repo,
        graph_repo=graph_repo,
        user_docs_milvus_service=user_docs_milvus_service,
        storage_service=storage_service,
        extract_service=extract_svc,
        graph_service=graph_svc_internal,
        ai_service=chat_ai_service_for_embedding,
        job_persistence_service=job_persistence_service,
        prompt_template_service=prompt_service
    )

def _get_podcast_repositories(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Provides a dictionary of initialized podcast repositories."""
    task_script_repo = repositories.PodcastTaskScriptRepository(db)
    return {
        "podcast_task_repo": repositories.PodcastTaskRepository(db),
        "podcast_script_repo": task_script_repo,
        "podcast_content_repo": repositories.PodcastTaskContentRepository(db),
        "podcast_history_repo": repositories.PodcastScriptHistoryRepository(db, script_repository=task_script_repo),
        "podcast_voice_repo": repositories.PodcastVoiceRepository(db),
    }

def _get_ai_script_service(
    settings: GlobalSettings = Depends(GlobalSettings),
    http_client: httpx.AsyncClient = Depends(lambda: GlobalSettings().app_state.http_client),
    prompt_template_service: PromptTemplateService = Depends(
        lambda db_session=Depends(get_db), redis_svc=Depends(lambda: GlobalSettings().app_state.redis_service): PromptTemplateService(
            db=db_session, 
            repository=PromptTemplateRepository(db_session), 
            redis_service=redis_svc
        )
    ),
) -> services.AIScriptService: # Using direct type hint
    """Factory for podcast's AIScriptService."""
    return services.AIScriptService(
        settings=settings,
        http_client=http_client,
        prompt_template_service=prompt_template_service,
    )

def _get_ai_speech_service(
    settings: GlobalSettings = Depends(GlobalSettings),
    repos: Dict[str, Any] = Depends(_get_podcast_repositories),
) -> services.AISpeechService: # Using direct type hint
    """Factory for podcast's AISpeechService."""
    return services.AISpeechService(
        settings=settings,
        voice_repository=repos["podcast_voice_repo"],
    )

def _get_podcast_service(
    settings: GlobalSettings = Depends(GlobalSettings),
    repos: Dict[str, Any] = Depends(_get_podcast_repositories),
    ai_script_service: services.AIScriptService = Depends(_get_ai_script_service),
    ai_speech_service: services.AISpeechService = Depends(_get_ai_speech_service),
    knowledge_document_service: KnowledgeDocumentService = Depends(_get_knowledge_document_service),
) -> services.PodcastService: # Using direct type hint
    """Factory for the main PodcastService."""
    return services.PodcastService(
        settings=settings,
        podcast_task_repo=repos["podcast_task_repo"],
        podcast_script_repo=repos["podcast_script_repo"],
        podcast_content_repo=repos["podcast_content_repo"],
        podcast_history_repo=repos["podcast_history_repo"],
        ai_script_service=ai_script_service,
        ai_speech_service=ai_speech_service,
        document_service=knowledge_document_service,
    )

def _get_podcast_processing_service(
    settings: GlobalSettings = Depends(GlobalSettings),
    repos: Dict[str, Any] = Depends(_get_podcast_repositories),
    podcast_service: services.PodcastService = Depends(_get_podcast_service),
) -> services.PodcastProcessingService: # Using direct type hint
    """Factory for PodcastProcessingService."""
    return services.PodcastProcessingService(
        settings=settings,
        podcast_repo=repos["podcast_task_repo"],
        podcast_service=podcast_service,
    )

# --- API Endpoints ---

@router.post(
    "/tasks/create",
    response_model=ApiResponse[BaseIdResponseDto],
    summary="创建播客",
)
async def create_podcast(
    request_dto: dtos.CreatePodcastRequestDto, # Likely source of Pydantic NameError if it has fields like _name
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service), # String literal type hint
    db: AsyncSession = Depends(get_db)
):
    try:
        podcast_id = await podcast_service.create_podcast_async(user_id, request_dto)
        await db.commit()
        return ApiResponse.success(data=BaseIdResponseDto(id=podcast_id), message="播客创建成功")
    except (BusinessException, NotFoundException) as e:
        await db.rollback()
        raise e
    except Exception as e_global:
        await db.rollback()
        logger.error(f"创建播客错误: {e_global}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="播客创建失败")


@router.post(
    "/tasks/contents/upload",
    response_model=ApiResponse[int],
    summary="上传文档作为播客内容",
    dependencies=[
        Depends(get_current_active_user_id),
        Depends(RateLimiter(limit=5, period_seconds=300, limit_type="user"))
    ]
)
async def upload_document_for_podcast(
    request_form: BaseIdRequestDto = Depends(BaseIdRequestDto.as_form),
    file: UploadFile = File(..., description="要上传的文档文件"),
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service),
    knowledge_doc_service: 'KnowledgeDocumentServiceTyped' = Depends(_get_knowledge_document_service), # String literal type hint
    db: AsyncSession = Depends(get_db)
):
    try:
        podcast_id_from_form = request_form.id
        document_id = await knowledge_doc_service.upload_document_async(
            user_id=user_id,
            app_type=DocumentAppType.PODCAST,
            file=file,
            title=file.filename or "Untitled Podcast Document",
            source_id=str(podcast_id_from_form),
            vectorize=False, 
            graphize=False 
        )
        content_id = await podcast_service.add_podcast_content_async(
            user_id=user_id,
            podcast_id=podcast_id_from_form,
            content_type=models.PodcastTaskContentType.FILE,
            source_document_id=document_id,
            source_content=None
        )
        await db.commit()
        return ApiResponse.success(data=content_id, message="播客文档上传成功")
    except (BusinessException, NotFoundException) as e:
        await db.rollback()
        raise e
    except Exception as e_global:
        await db.rollback()
        logger.error(f"上传播客文档错误: {e_global}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="播客文档上传失败")


@router.post(
    "/tasks/contents/importurl",
    response_model=ApiResponse[int],
    summary="导入网页作为播客内容",
    dependencies=[
        Depends(get_current_active_user_id),
        Depends(RateLimiter(limit=5, period_seconds=300, limit_type="user"))
    ]
)
async def import_url_for_podcast(
    request_dto: dtos.ImportPodcastUrlRequestDto,
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service),
    knowledge_doc_service: 'KnowledgeDocumentServiceTyped' = Depends(_get_knowledge_document_service),
    db: AsyncSession = Depends(get_db)
):
    try:
        document_id = await knowledge_doc_service.import_web_page_async(
            user_id=user_id,
            app_type=DocumentAppType.PODCAST,
            url=str(request_dto.url), # Ensure URL is a string
            title=f"Podcast Web Content: {request_dto.url}",
            source_id=str(request_dto.id),
            vectorize=False,
            graphize=False
        )
        content_id = await podcast_service.add_podcast_content_async(
            user_id=user_id,
            podcast_id=request_dto.id,
            content_type=models.PodcastTaskContentType.URL,
            source_document_id=document_id,
            source_content=None
        )
        await db.commit()
        return ApiResponse.success(data=content_id, message="播客网页导入成功")
    except (BusinessException, NotFoundException) as e:
        await db.rollback()
        raise e
    except Exception as e_global:
        await db.rollback()
        logger.error(f"导入播客URL错误: {e_global}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="播客网页导入失败")


@router.post(
    "/tasks/contents/text",
    response_model=ApiResponse[int],
    summary="导入文本作为播客内容",
    dependencies=[
        Depends(get_current_active_user_id),
        Depends(RateLimiter(limit=5, period_seconds=300, limit_type="user"))
    ]
)
async def import_text_for_podcast(
    request_dto: dtos.ImportPodcastTextRequestDto,
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service),
    db: AsyncSession = Depends(get_db)
):
    try:
        content_id = await podcast_service.add_podcast_content_async(
            user_id=user_id,
            podcast_id=request_dto.id,
            content_type=models.PodcastTaskContentType.TEXT,
            source_document_id=None,
            source_content=request_dto.text
        )
        await db.commit()
        return ApiResponse.success(data=content_id, message="播客文本导入成功")
    except (BusinessException, NotFoundException) as e:
        await db.rollback()
        raise e
    except Exception as e_global:
        await db.rollback()
        logger.error(f"导入播客文本错误: {e_global}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="播客文本导入失败")


@router.post(
    "/tasks/contents/delete",
    response_model=ApiResponse[None],
    summary="删除播客的内容项",
    dependencies=[Depends(get_current_active_user_id)]
)
async def delete_podcast_content(
    request_dto: BaseIdRequestDto,
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service),
    db: AsyncSession = Depends(get_db)
):
    try:
        deleted = await podcast_service.delete_podcast_content_async(user_id, request_dto.id)
        if deleted:
            await db.commit()
            return ApiResponse.success(message="播客内容删除成功")
        else:
            await db.rollback() 
            # Using a more standard 404 for not found, or rely on service to raise NotFoundException
            # return ApiResponse.fail(message="播客内容删除失败或未找到", code=status.HTTP_404_NOT_FOUND) 
            raise NotFoundException(message="播客内容删除失败或未找到")
    except (BusinessException, NotFoundException) as e:
        await db.rollback()
        raise e
    except Exception as e_global:
        await db.rollback()
        logger.error(f"删除播客内容错误: {e_global}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="播客内容删除处理失败")


@router.post(
    "/tasks/contents/dtl",
    response_model=ApiResponse[dtos.PodcastContentItemDto],
    summary="获取播客内容项详情",
    dependencies=[Depends(get_current_active_user_id)]
)
async def get_podcast_content_detail(
    request_dto: BaseIdRequestDto,
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service),
):
    try:
        content_detail = await podcast_service.get_podcast_content_detail_async(user_id, request_dto.id)
        return ApiResponse.success(data=content_detail)
    except (BusinessException, NotFoundException) as e:
        raise e
    except Exception as e_global:
        logger.error(f"获取播客内容详情错误: {e_global}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取播客内容详情失败")


@router.post(
    "/tasks/dtl",
    response_model=ApiResponse[dtos.PodcastDetailDto],
    summary="获取播客详情",
    dependencies=[Depends(get_current_active_user_id)]
)
async def get_podcast_detail(
    request_dto: BaseIdRequestDto,
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service),
):
    try:
        podcast_detail = await podcast_service.get_podcast_async(user_id, request_dto.id)
        return ApiResponse.success(data=podcast_detail)
    except (BusinessException, NotFoundException) as e:
        raise e
    except Exception as e_global:
        logger.error(f"获取播客详情错误: {e_global}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取播客详情失败")


@router.post(
    "/tasks/list",
    response_model=ApiResponse[PagedResultDto[dtos.PodcastListItemDto]],
    summary="获取播客列表",
    dependencies=[Depends(get_current_active_user_id)]
)
async def get_podcast_list(
    request_dto: dtos.PodcastListRequestDto,
    user__id: int = Depends(get_current_active_user_id), # Corrected typo from original user_id to user_id if that was a typo
    podcast_service: 'PodcastService' = Depends(_get_podcast_service),
):
    try:
        # Assuming the parameter was meant to be user_id
        paged_result = await podcast_service.get_user_podcasts_async(user__id, request_dto) 
        return ApiResponse.success(data=paged_result)
    except Exception as e_global:
        logger.error(f"获取播客列表错误: {e_global}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取播客列表失败")

@router.post(
    "/tasks/delete",
    response_model=ApiResponse[None],
    summary="删除播客",
    dependencies=[Depends(get_current_active_user_id)]
)
async def delete_podcast(
    request_dto: BaseIdRequestDto,
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service),
    db: AsyncSession = Depends(get_db)
):
    try:
        deleted = await podcast_service.delete_podcast_async(user_id, request_dto.id)
        if deleted:
            await db.commit()
            return ApiResponse.success(message="播客删除成功")
        else:
            await db.rollback()
            # return ApiResponse.fail(message="播客删除失败或未找到", code=status.HTTP_404_NOT_FOUND)
            raise NotFoundException(message="播客删除失败或未找到")
    except (BusinessException, NotFoundException) as e:
        await db.rollback()
        raise e
    except Exception as e_global:
        await db.rollback()
        logger.error(f"删除播客错误: {e_global}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="播客删除处理失败")


@router.post(
    "/tasks/generate",
    response_model=ApiResponse[None],
    summary="开始生成播客",
    dependencies=[
        Depends(get_current_active_user_id),
        Depends(RateLimiter(limit=10, period_seconds=300, limit_type="user"))
    ]
)
async def start_podcast_generation(
    request_dto: BaseIdRequestDto,
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service),
    db: AsyncSession = Depends(get_db)
):
    try:
        submitted = await podcast_service.start_podcast_generate_async(user_id, request_dto.id)
        if submitted:
            await db.commit()
            return ApiResponse.success(message="播客生成任务已提交，请稍后刷新查看结果")
        else:
            # Consider raising BusinessException from service for clearer error handling
            await db.rollback()
            return ApiResponse.fail(message="播客生成任务提交失败，可能是因为状态不符或内部错误")
    except (BusinessException, NotFoundException) as e:
        await db.rollback()
        raise e
    except Exception as e_global:
        await db.rollback()
        logger.error(f"开始播客生成错误: {e_global}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="播客生成任务提交处理失败")


@router.post(
    "/voices/all",
    response_model=ApiResponse[List[dtos.TtsVoiceDefinitionDto]],
    summary="获取所有支持的语音列表",
    dependencies=[Depends(get_current_active_user_id)]
)
async def get_all_supported_voices(
    podcast_service: 'PodcastService' = Depends(_get_podcast_service),
):
    try:
        voices = await podcast_service.get_supported_voices_async()
        return ApiResponse.success(data=voices)
    except Exception as e_global:
        logger.error(f"获取所有支持语音错误: {e_global}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取语音列表失败")


@router.post(
    "/voices/locale",
    response_model=ApiResponse[List[dtos.TtsVoiceDefinitionDto]],
    summary="获取指定语言的语音列表",
    dependencies=[Depends(get_current_active_user_id)]
)
async def get_voices_by_locale(
    request_dto: dtos.GetVoicesByLocaleRequestDto,
    podcast_service: 'PodcastService' = Depends(_get_podcast_service),
):
    try:
        if not request_dto.locale:
            # This can be handled by Pydantic validation if locale is a required field in DTO
            return ApiResponse.fail(message="语言/地区参数不能为空", code=status.HTTP_400_BAD_REQUEST)
            
        voices = await podcast_service.get_voices_by_locale_async(request_dto.locale)
        return ApiResponse.success(data=voices)
    except (BusinessException, NotFoundException) as e: # Assuming service might raise these
        raise e
    except Exception as e_global:
        logger.error(f"按区域获取语音错误: {e_global}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取指定语言语音列表失败")

@router.post(
    "/tasks/process_pending_podcasts_job/{job_id}/{params_id}",
    summary="[内部任务] 处理待处理的播客生成任务",
    response_model=ApiResponse[None], # job_endpoint typically handles the response structure for jobs
)
@job_endpoint() # This decorator should handle db session, commits, rollbacks, and job status updates
async def task_process_pending_podcasts(
    job_id: int, # Provided by job system
    params_id: int, # Provided by job system
    processing_service: 'PodcastProcessingService' = Depends(_get_podcast_processing_service),
    # db: AsyncSession = Depends(get_db) # db session usually managed by @job_endpoint decorator
):
    # The main error "Fields must not use names with leading underscores" would prevent this code from being reached
    # if it occurs during router setup (which it does).
    # This endpoint itself doesn't use DTOs with underscores in its signature directly.
    try:
        await processing_service.process_pending_podcasts_async()
        # If @job_endpoint doesn't return a specific success ApiResponse,
        # this endpoint could return nothing or a standard success message
        # However, job_endpoint typically controls the final response.
        # For consistency, if this were a normal endpoint:
        # return ApiResponse.success(message="待处理播客任务处理完成")
    except Exception as e: 
        logger.error(f"Job {job_id} (task_process_pending_podcasts) failed critically: {e}", exc_info=True)
        # The @job_endpoint decorator should catch this and handle job failure logging/status.
        raise # Re-raise for @job_endpoint to handle