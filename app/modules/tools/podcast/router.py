"""
播客模块API路由定义
"""
import logging
from typing import List, Optional
from fastapi import (
    APIRouter, Depends, UploadFile, File, Form, HTTPException, 
    status, BackgroundTasks, Body
)
from sqlalchemy.ext.asyncio import AsyncSession

# 核心依赖
from app.core.database.session import get_db
from app.api.dependencies import (
    get_current_active_user_id,
    get_storage_service_from_state,
    get_chatai_service_from_state,
    get_job_persistence_service,
    RateLimiter
)
from app.core.job.decorators import job_endpoint
from app.core.dtos import ApiResponse, BaseIdRequestDto, PagedResultDto
from app.core.dtos import DocumentAppType
from app.core.exceptions import NotFoundException, BusinessException

# 播客模块DTOs
from app.modules.tools.podcast.constants import PodcastTaskContentType
from app.modules.tools.podcast.dtos import (
    CreatePodcastRequestDto, PodcastDetailDto, PodcastListRequestDto, 
    PodcastListItemDto, PodcastContentItemDto, TtsVoiceDefinition,
    ImportPodcastUrlRequestDto, ImportPodcastTextRequestDto,
    GetVoicesByLocaleRequestDto, PodcastDetailResponse, PodcastListResponse,
    PodcastContentItemResponse, TtsVoiceDefinitionListResponse, BaseIdResponse
)

# 导入文档服务
from app.modules.base.knowledge.services.document_service import DocumentService
from app.modules.base.prompts.services import PromptTemplateService

# 导入类型提示
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.storage.base import IStorageService
    from app.core.ai.chat.base import IChatAIService
    from app.core.job.services import JobPersistenceService
    from app.modules.tools.podcast.services.podcast_service import PodcastService
    from app.modules.tools.podcast.services.ai_script_service import AIScriptService
    from app.modules.tools.podcast.services.ai_speech_service import AISpeechService

# 获取日志记录器
logger = logging.getLogger(__name__)

# 创建播客API路由
router = APIRouter(
    prefix="/podcast",
    tags=["Podcast"],
    responses={404: {"description": "Not found"}}
)

# 内部依赖项工厂：获取播客服务实例
def _get_podcast_service(
    db: AsyncSession = Depends(get_db),
    storage_service: Optional['IStorageService'] = Depends(get_storage_service_from_state),
    ai_service: 'IChatAIService' = Depends(get_chatai_service_from_state),
    job_persistence_service: 'JobPersistenceService' = Depends(get_job_persistence_service),
) -> 'PodcastService':
    """内部依赖项：创建并返回PodcastService及其内部所有依赖"""
    
    # 导入内部依赖，避免循环依赖
    from app.modules.tools.podcast.repositories import (
        PodcastTaskRepository, PodcastTaskContentRepository, 
        PodcastTaskScriptRepository, PodcastScriptHistoryRepository,
        PodcastVoiceRepository
    )
    from app.modules.tools.podcast.services.podcast_service import PodcastService
    from app.modules.tools.podcast.services.ai_script_service import AIScriptService
    from app.modules.tools.podcast.services.ai_speech_service import AISpeechService
    from app.modules.base.knowledge.services.document_service import DocumentService
    from app.modules.base.prompts.services import PromptTemplateService
    from app.modules.base.prompts.repositories import PromptTemplateRepository
    from app.core.redis.service import RedisService

    # 创建依赖项
    podcast_repository = PodcastTaskRepository(db)
    podcast_content_repository = PodcastTaskContentRepository(db)
    podcast_script_repository = PodcastTaskScriptRepository(db)
    script_history_repository = PodcastScriptHistoryRepository(db)
    voice_repository = PodcastVoiceRepository(db)
    
    # 获取提示词服务依赖
    prompt_repo = PromptTemplateRepository(db=db)
    # 为了避免循环导入，这里我们没有显式地传入 redis_service
    prompt_service = PromptTemplateService(db=db, repository=prompt_repo, redis_service=None)
    
    # 创建AI服务
    ai_script_service = AIScriptService(ai_service=ai_service, prompt_template_service=prompt_service)
    ai_speech_service = AISpeechService(db=db, voice_repository=voice_repository, storage_service=storage_service)
    
    # 创建文档服务
    # 由于文档服务有多个依赖，这里简化创建
    # 在实际实现中需要完整传入文档服务的所有依赖
    document_service = _get_document_service(db)
    
    # 创建播客服务
    podcast_service = PodcastService(
        db=db,
        podcast_repository=podcast_repository,
        podcast_content_repository=podcast_content_repository,
        podcast_script_repository=podcast_script_repository,
        script_history_repository=script_history_repository,
        document_service=document_service,
        ai_script_service=ai_script_service,
        ai_speech_service=ai_speech_service,
        job_persistence_service=job_persistence_service
    )
    
    return podcast_service


def _get_document_service(
    db: AsyncSession = Depends(get_db),
) -> DocumentService:
    """
    内部依赖项：获取文档服务
    
    注意：此处简化了文档服务的创建，实际实现中需要传入所有必要的依赖
    """
    # 由于文档服务依赖复杂，此处仅返回最小化实现
    # 在实际使用中，应当正确创建并返回完整的文档服务
    return DocumentService(db=db)


# 播客API端点定义

@router.post(
    "/tasks/create",
    response_model=ApiResponse[BaseIdRequestDto],
    summary="创建播客",
    description="创建一个新的播客任务",
    dependencies=[
        Depends(RateLimiter(limit=10, period_seconds=300, limit_type="user"))
    ]
)
async def create_podcast(
    request: CreatePodcastRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service)
):
    """
    创建播客接口
    
    - **title**: 播客标题 (必需)
    - **description**: 播客描述 (必需)
    - **scene**: 播客场景/主题 (必需)
    - **atmosphere**: 播客氛围 (必需)
    - **guestCount**: 嘉宾数量 (可选，默认为1)
    
    *需要有效的登录令牌*
    """
    podcast_id = await podcast_service.create_podcast_async(user_id, request)
    return ApiResponse.success(
        data=BaseIdRequestDto(id=podcast_id),
        message="播客创建成功"
    )


@router.post(
    "/tasks/contents/upload",
    response_model=ApiResponse[int],
    summary="上传文档",
    description="上传文档到播客内容中",
    dependencies=[
        Depends(RateLimiter(limit=5, period_seconds=300, limit_type="user"))
    ]
)
async def upload_document(
    file: UploadFile = File(...),
    id: int = Form(..., description="播客ID"),
    user_id: int = Depends(get_current_active_user_id),
    document_service: DocumentService = Depends(_get_document_service),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service)
):
    """
    上传文档接口
    
    - **file**: 要上传的文件 (必需)
    - **id**: 播客ID (必需)
    
    *需要有效的登录令牌*
    """
    # 上传文档到文档系统
    document_id = await document_service.upload_document_async(
        user_id=user_id,
        app_type=DocumentAppType.PODCAST,
        file=file,
        title="",
        parent_id=id,
        need_vectorize=False,
        need_graph=False
    )
    
    # 添加到播客内容
    content_id = await podcast_service.add_podcast_content_async(
        user_id=user_id,
        podcast_id=id,
        content_type=PodcastTaskContentType.FILE,  # 文档文件类型
        source_document_id=document_id,
        source_content=""
    )
    
    return ApiResponse.success(data=content_id, message="文档上传成功")


@router.post(
    "/tasks/contents/importurl",
    response_model=ApiResponse[int],
    summary="导入网页",
    description="导入网页内容到播客中",
    dependencies=[
        Depends(RateLimiter(limit=5, period_seconds=300, limit_type="user"))
    ]
)
async def import_web_page(
    request: ImportPodcastUrlRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    document_service: DocumentService = Depends(_get_document_service),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service)
):
    """
    导入网页接口
    
    - **id**: 播客ID (必需)
    - **url**: 要导入的网页URL (必需)
    
    *需要有效的登录令牌*
    """
    # 导入网页到文档系统
    document_id = await document_service.import_web_page_async(
        user_id=user_id,
        app_type=DocumentAppType.PODCAST,
        url=str(request.url),
        title="",
        parent_id=request.id,
        need_vectorize=False,
        need_graph=False
    )
    
    # 添加到播客内容
    content_id = await podcast_service.add_podcast_content_async(
        user_id=user_id,
        podcast_id=request.id,
        content_type=PodcastTaskContentType.URL,  # 网页URL类型
        source_document_id=document_id,
        source_content=""
    )
    
    return ApiResponse.success(data=content_id, message="网页导入成功")


@router.post(
    "/tasks/contents/text",
    response_model=ApiResponse[int],
    summary="导入文本",
    description="导入文本内容到播客中",
    dependencies=[
        Depends(RateLimiter(limit=5, period_seconds=300, limit_type="user"))
    ]
)
async def import_text(
    request: ImportPodcastTextRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service)
):
    """
    导入文本接口
    
    - **id**: 播客ID (必需)
    - **text**: 要导入的文本内容 (必需)
    
    *需要有效的登录令牌*
    """
    # 添加到播客内容
    content_id = await podcast_service.add_podcast_content_async(
        user_id=user_id,
        podcast_id=request.id,
        content_type=PodcastTaskContentType.TEXT,  # 文本类型
        source_document_id=0,
        source_content=request.text or ""
    )
    
    return ApiResponse.success(data=content_id, message="文本导入成功")


@router.post(
    "/tasks/contents/delete",
    response_model=ApiResponse,
    summary="删除内容",
    description="删除播客的内容项"
)
async def delete_content(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service)
):
    """
    删除内容接口
    
    - **id**: 内容项ID (必需)
    
    *需要有效的登录令牌*
    """
    result = await podcast_service.delete_podcast_content_async(user_id, request.id)
    return ApiResponse.success(message="播客内容删除成功") if result else ApiResponse.fail(message="播客内容删除失败")


@router.post(
    "/tasks/contents/dtl",
    response_model=PodcastContentItemResponse,
    summary="获取内容详情",
    description="获取播客内容项的详细信息"
)
async def get_podcast_content_dtl(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service)
):
    """
    获取内容详情接口
    
    - **id**: 内容项ID (必需)
    
    *需要有效的登录令牌*
    """
    content = await podcast_service.get_podcast_content_detail_async(user_id, request.id)
    return ApiResponse.success(data=content)


@router.post(
    "/tasks/dtl",
    response_model=PodcastDetailResponse,
    summary="获取播客详情",
    description="获取播客的详细信息，包括内容和脚本"
)
async def get_podcast_detail(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service)
):
    """
    获取播客详情接口
    
    - **id**: 播客ID (必需)
    
    *需要有效的登录令牌*
    """
    podcast = await podcast_service.get_podcast_async(user_id, request.id)
    return ApiResponse.success(data=podcast)


@router.post(
    "/tasks/list",
    response_model=PodcastListResponse,
    summary="获取播客列表",
    description="分页获取用户的播客列表"
)
async def get_podcast_list(
    request: PodcastListRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service)
):
    """
    获取播客列表接口
    
    - **pageIndex**: 页码 (必需)
    - **pageSize**: 每页大小 (必需)
    
    *需要有效的登录令牌*
    """
    podcasts = await podcast_service.get_user_podcasts_async(user_id, request)
    return ApiResponse.success(data=podcasts)


@router.post(
    "/tasks/delete",
    response_model=ApiResponse,
    summary="删除播客",
    description="删除指定的播客"
)
async def delete_podcast(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service)
):
    """
    删除播客接口
    
    - **id**: 播客ID (必需)
    
    *需要有效的登录令牌*
    """
    result = await podcast_service.delete_podcast_async(user_id, request.id)
    return ApiResponse.success(message="播客删除成功") if result else ApiResponse.fail(message="播客删除失败")


@router.post(
    "/tasks/generate",
    response_model=ApiResponse,
    summary="生成播客",
    description="开始播客生成过程",
    dependencies=[
        Depends(RateLimiter(limit=10, period_seconds=300, limit_type="user"))
    ]
)
async def start_podcast_generate(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service)
):
    """
    生成播客接口
    
    - **id**: 播客ID (必需)
    
    *需要有效的登录令牌*
    """
    result = await podcast_service.start_podcast_generate_async(user_id, request.id)
    return ApiResponse.success(message="播客生成任务已提交，请稍后刷新查看结果") if result else ApiResponse.fail(message="播客生成任务提交失败")


@router.post(
    "/voices/all",
    response_model=TtsVoiceDefinitionListResponse,
    summary="获取所有语音",
    description="获取所有支持的语音列表"
)
async def get_supported_voices(
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service)
):
    """
    获取所有语音接口
    
    *需要有效的登录令牌*
    """
    voices = await podcast_service.get_supported_voices_async()
    return ApiResponse.success(data=voices)


@router.post(
    "/voices/locale",
    response_model=TtsVoiceDefinitionListResponse,
    summary="获取指定语言的语音",
    description="获取指定语言/地区的语音列表"
)
async def get_voices_by_locale(
    request: GetVoicesByLocaleRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    podcast_service: 'PodcastService' = Depends(_get_podcast_service)
):
    """
    获取指定语言的语音接口
    
    - **locale**: 语言/地区 (必需, 如zh-CN, en-US等)
    
    *需要有效的登录令牌*
    """
    if not request.locale:
        return ApiResponse.fail(message="语言/地区参数不能为空")
    
    voices = await podcast_service.get_voices_by_locale_async(request.locale)
    return ApiResponse.success(data=voices)


# 后台任务端点
@router.post(
    "/tasks/process/{job_id}/{params_id}",
    response_model=ApiResponse,
    summary="[内部] 处理播客生成任务",
    description="由调度器调用，处理播客生成任务"
)
@job_endpoint(default_can_retry=True)
async def process_podcast_generate_task(
    job_id: int,
    params_id: int,
    podcast_service: 'PodcastService' = Depends(_get_podcast_service)
):
    """
    处理播客生成任务
    
    此接口由任务调度器调用，不应由用户直接调用
    
    Args:
        job_id: 任务ID
        params_id: 播客ID
    """
    # 调用服务层处理播客生成
    await podcast_service.process_podcast_generate(params_id)
    return ApiResponse.success(message="播客处理成功")

