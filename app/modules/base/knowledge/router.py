# app/modules/base/knowledge/router.py
import logging
from typing import List, Optional # 确保导入 List, Optional
from fastapi import (
    APIRouter, Depends, UploadFile, File, Form, HTTPException, status, Request, Body, BackgroundTasks
)
from sqlalchemy.ext.asyncio import AsyncSession

# 导入核心依赖获取函数 (用于获取 db, settings, logger 等)
from app.core.database.session import get_db
from app.core.config.settings import settings

from app.api.dependencies import ( # <--- 只导入核心依赖工厂
    get_current_active_user_id,
    get_user_docs_milvus_service_from_state,
    get_storage_service_from_state,
    get_chatai_service_from_state, # <--- 用于注入给 Knowledge 服务
    get_redis_service_from_state,   # <--- PromptTemplateService 需要
    get_job_persistence_service, # Job Persistence Service 依赖
    RateLimiter
)

# --- 导入 Job Decorator ---
from app.core.job.decorators import job_endpoint
# --- 导入 Job Status 枚举 ---
from app.core.job.models import JobStatus

# 导入核心 DTO 和异常
from app.core.dtos import ApiResponse, BaseIdRequestDto, PagedResultDto
from app.core.exceptions import NotFoundException, BusinessException
from app.core.dtos import DocumentAppType

# 导入 Knowledge 模块的 DTOs
from app.modules.base.knowledge.dtos import (
    PageUrlImportRequestDto, DocumentDetailResponseDto, DocumentListItemDto,
    DocumentListRequestDto, DocumentContentDto, DocumentLogItemDto, KnowledgeGraphDto
) 

# --- 导入 Service/Repo 协议/类 (用于类型提示) ---
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.ai.vector.base import IUserDocsMilvusService
    from app.core.storage.base import IStorageService
    from app.modules.base.knowledge.services.extract_service import IDocumentExtractService
    from app.modules.base.knowledge.services.graph_service import KnowledgeGraphService
    from app.core.ai.chat.base import IChatAIService
    from app.core.redis.service import RedisService
    from app.core.job.services import JobPersistenceService

# --- 在顶层作用域导入 DocumentService，用于路由函数类型提示 ---
# 但为了避免循环依赖，我们继续使用 TYPE_CHECKING 结合字符串提示
if TYPE_CHECKING:
    from app.modules.base.knowledge.services.document_service import DocumentService

# --- 获取 Logger ---
logger = logging.getLogger(__name__)

# --- 创建 Knowledge API Router ---
# 对应 C# [ToolController("knowledge", "知识库文档", ...)]
router = APIRouter(
    prefix="/knowledge", # API 前缀 (结合 main.py 中的 /api -> /api/knowledge)
    tags=["Knowledge Base"] # Swagger UI 分组标签
) 

# --- 内部依赖项工厂：获取 DocumentService 实例 ---
def _get_document_service(
    # --- 只注入最核心的依赖 ---
    db: AsyncSession = Depends(get_db),
    user_docs_milvus_service: 'IUserDocsMilvusService' = Depends(get_user_docs_milvus_service_from_state),
    storage_service: Optional['IStorageService'] = Depends(get_storage_service_from_state),
    ai_service: 'IChatAIService' = Depends(get_chatai_service_from_state), # 假设向量化用
    redis_service: 'RedisService' = Depends(get_redis_service_from_state), # Prompt 和 Graph Service 可能需要
    job_persistence_service:'JobPersistenceService' = Depends(get_job_persistence_service),
    # --------------------------
) -> 'DocumentService':
    """内部依赖项：创建并返回 DocumentService 及其内部所有依赖。"""
    # 在函数内部导入，避免循环依赖
    from app.modules.base.knowledge.services.document_service import DocumentService
    from app.modules.base.knowledge.services.extract_service import DocumentExtractService
    from app.modules.base.knowledge.services.graph_service import KnowledgeGraphService
    from app.modules.base.prompts.services import PromptTemplateService
    from app.modules.base.prompts.repositories import PromptTemplateRepository

    # --- 手动创建内部依赖 ---
    # 1. 创建 Prompt 相关 (因为 GraphService 需要)
    prompt_repo = PromptTemplateRepository(db=db)
    prompt_service = PromptTemplateService(db=db, repository=prompt_repo, redis_service=redis_service)

    # 2. 创建 Knowledge 内部服务
    extract_service_instance = DocumentExtractService() # 假设无外部依赖
    # Graph Service 需要 prompt_service 和 ai_service
    # 注意: graph_service 可能需要不同的 ai_service (聊天模型)
    # 这里暂时使用注入的 ai_service (通常是嵌入模型?)，需要根据实际情况调整
    graph_service_instance = KnowledgeGraphService(
        prompt_service=prompt_service,
        ai_service=ai_service, # 确认这里的 AI Service 类型是否正确
    )

    # 3. 创建 DocumentService
    doc_service = DocumentService(
        db=db,
        user_docs_milvus_service=user_docs_milvus_service,
        storage_service=storage_service,
        extract_service=extract_service_instance,
        graph_service=graph_service_instance,
        ai_service=ai_service, # 这个 AI 服务用于向量化
        job_persistence_service=job_persistence_service,
        settings=settings,
    )
    return doc_service

# --- Knowledge API 端点定义 ---

# 对应 C# [HttpPost("documents/upload")]
@router.post(
    "/documents/upload",
    response_model=ApiResponse[int], # 返回文档 ID (int/long)
    summary="上传文档",
    description="上传文件（如 PDF, DOCX, TXT）到知识库，后台将自动解析和处理。",
    status_code=status.HTTP_202_ACCEPTED, # 接受请求，后台处理，返回 202
    dependencies=[
        Depends(get_current_active_user_id), # <--- 需要登录
        Depends(RateLimiter(limit=5, period_seconds=300, limit_type="user")) # C# rate limit
    ]
)
async def upload_document(
    # FastAPI 处理文件上传使用 File(...)
    # 其他表单字段使用 Form(...)
    file: UploadFile = File(..., description="要上传的文档文件"),
    title: Optional[str] = Form(None, description="文档标题 (可选)"), # 改为 Optional
    app_type: DocumentAppType = Form(..., alias="appType", description="知识所属应用源"),
    # 从依赖项获取 user_id 和 service
    user_id: int = Depends(get_current_active_user_id),
    doc_service: 'DocumentService' = Depends(_get_document_service) # 使用内部工厂
):
    """
    上传文档接口。后台会自动进行解析、向量化和图谱化（如果配置需要）。

    - **file**: 要上传的文件 (必需)
    - **title**: 文档标题 (可选, 默认使用文件名)
    - **appType**: 知识所属应用源 (必需, 例如 PKB, CustomerService)

    *需要有效的登录令牌 (Authorization header)*
    """
    if title is None: title = "" # 处理 None 的情况

    # 调用服务层方法处理上传
    document_id = await doc_service.upload_document_async(
        user_id=user_id,
        app_type=app_type,
        file=file,
        title=title
    )
    # 返回成功响应，告知客户端请求已被接受，后台正在处理
    return ApiResponse.success(data=document_id, message="文档上传请求已接受，正在后台处理")


# 对应 C# [HttpPost("documents/importurl")]
@router.post(
    "/documents/importurl",
    response_model=ApiResponse[int], # 返回文档 ID
    summary="导入网页",
    description="根据提供的 URL 导入网页内容到知识库，后台将自动解析和处理。",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[
        Depends(get_current_active_user_id),
        Depends(RateLimiter(limit=10, period_seconds=300, limit_type="user"))
    ]
)
async def import_web_page(
    request_dto: PageUrlImportRequestDto = Body(...), # 从请求体获取 JSON 数据
    user_id: int = Depends(get_current_active_user_id),
    doc_service: 'DocumentService' = Depends(_get_document_service) 
):
    """
    导入网页接口。后台会自动进行解析、向量化和图谱化（如果配置需要）。

    - **url**: 要导入的网页 URL (必需)
    - **title**: 文档标题 (可选, 默认使用 URL 或网页标题)
    - **appType**: 知识所属应用源 (必需)

    *需要有效的登录令牌 (Authorization header)*
    """
    document_id = await doc_service.import_web_page_async(
        user_id=user_id,
        app_type=request_dto.app_type,
        url=str(request_dto.url), # 将 Pydantic URL 转为字符串
        title=request_dto.title or ""
    )
    return ApiResponse.success(data=document_id, message="网页导入请求已接受，正在后台处理")


# 对应 C# [HttpPost("documents/list")]
@router.post(
    "/documents/list",
    response_model=ApiResponse[PagedResultDto[DocumentListItemDto]], # 分页列表响应
    summary="获取用户文档列表",
    description="分页获取当前用户指定应用类型的文档列表。",
    dependencies=[Depends(get_current_active_user_id)] # 需要登录
)
async def get_user_documents(
    request: DocumentListRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    doc_service: 'DocumentService' = Depends(_get_document_service) 
):
    """
    获取文档列表接口。

    - **appType**: 要查询的应用类型 (必需)
    - **pageIndex**: 页码 (必需, >= 1)
    - **pageSize**: 每页大小 (必需, 1-100)

    *需要有效的登录令牌 (Authorization header)*
    """
    paged_result = await doc_service.get_user_documents_async(user_id, request)
    return ApiResponse.success(data=paged_result)


# 对应 C# [HttpPost("documents/dtl")]
@router.post(
    "/documents/dtl",
    response_model=ApiResponse[DocumentDetailResponseDto],
    summary="获取文档详情",
    description="获取指定 ID 的文档详细信息，包括内容和知识图谱（如果处理完成）。",
    dependencies=[Depends(get_current_active_user_id)]
)
async def get_document_detail(
    request_dto: BaseIdRequestDto = Body(...), # 使用核心 ID 请求 DTO
    user_id: int = Depends(get_current_active_user_id),
    doc_service: 'DocumentService' = Depends(_get_document_service) 
):
    """
    获取文档详情接口。

    - **id**: 要查询的文档 ID (必需)

    *需要有效的登录令牌 (Authorization header)*
    """
    # NotFoundException 会被全局处理器捕获并返回 404
    document_detail = await doc_service.get_document_async(user_id, request_dto.id)
    return ApiResponse.success(data=document_detail)


# 对应 C# [HttpPost("documents/content")]
@router.post(
    "/documents/content",
    response_model=ApiResponse[DocumentContentDto],
    summary="获取文档内容",
    description="获取已处理完成的文档的文本内容。",
    dependencies=[Depends(get_current_active_user_id)]
)
async def get_document_content(
    request_dto: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    doc_service: 'DocumentService' = Depends(_get_document_service) 
):
    """
    获取文档内容接口。

    - **id**: 要查询的文档 ID (必需)

    *文档必须已处理完成 (status=Completed)*
    *需要有效的登录令牌 (Authorization header)*
    """
    # BusinessException (文档未完成) 或 NotFoundException 会被捕获
    document_content = await doc_service.get_document_content_async(user_id, request_dto.id)
    return ApiResponse.success(data=document_content)


# 对应 C# [HttpPost("documents/logs")]
@router.post(
    "/documents/logs",
    response_model=ApiResponse[List[DocumentLogItemDto]],
    summary="获取文档处理日志",
    description="获取指定文档的处理过程日志列表。",
    dependencies=[Depends(get_current_active_user_id)]
)
async def get_document_logs(
    request_dto: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    doc_service: 'DocumentService' = Depends(_get_document_service) 
):
    """
    获取文档日志接口。

    - **id**: 要查询的文档 ID (必需)

    *需要有效的登录令牌 (Authorization header)*
    """
    logs = await doc_service.get_document_logs_async(user_id, request_dto.id)
    return ApiResponse.success(data=logs)


# 对应 C# [HttpPost("documents/delete")]
@router.post(
    "/documents/delete",
    response_model=ApiResponse[None], # 成功时无特定数据返回
    summary="删除文档",
    description="删除指定的文档及其所有关联数据（内容、向量、图谱、日志、存储文件）。",
    status_code=status.HTTP_200_OK, # 或者 204 No Content? C# 返回 OK
    dependencies=[Depends(get_current_active_user_id)]
)
async def delete_document(
    request_dto: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    doc_service: 'DocumentService' = Depends(_get_document_service) 
):
    """
    删除文档接口。

    - **id**: 要删除的文档 ID (必需)

    *需要有效的登录令牌 (Authorization header)*
    """
    success = await doc_service.delete_document_async(user_id, request_dto.id)
    if success:
        return ApiResponse.success(message="文档删除成功")
    else:
        # delete_document_async 内部会抛出异常，理论上不会走到这里
        # 但为了覆盖 C# 的返回逻辑，保留一个失败分支
        return ApiResponse.fail(message="文档删除失败", code=status.HTTP_500_INTERNAL_SERVER_ERROR) # 或者返回 404?



@router.post(
    "/documents/tasks/process/{job_id}/{params_id}",
    summary="[内部] 执行文档解析任务",
    description="由调度器调用，自动处理锁和状态更新。", # 更新描述
    status_code=status.HTTP_200_OK, # 现在直接返回 200
    response_model=ApiResponse[None]
)
@job_endpoint(default_can_retry=False) # 应用装饰器，解析失败通常不重试
async def execute_process_document_task(
    job_id: int, # 参数名需与路径参数匹配
    params_id: int, # 新增，需要从路径获取
    job_service: 'JobPersistenceService' = Depends(get_job_persistence_service),
    doc_service: 'DocumentService' = Depends(_get_document_service)
):
    """
    实际的文档解析业务逻辑调用。
    此函数在获取锁后，在后台任务中被调用。
    如果此函数成功执行（无异常），任务将被标记为 COMPLETED。
    如果此函数抛出异常，任务将被标记为 FAILED (根据装饰器参数决定是否重试)。
    """
    # 只包含核心业务逻辑调用
    await doc_service.execute_document_parsing(params_id)


@router.post(
    "/documents/tasks/vectorize/{job_id}/{params_id}",
    summary="[内部] 执行文档向量化任务",
    description="由调度器调用，自动处理锁和状态更新。",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[None]
)
@job_endpoint(default_can_retry=True) # 向量化失败允许重试
async def execute_vectorize_document_task(
    job_id: int,
    params_id: int,
    job_service: 'JobPersistenceService' = Depends(get_job_persistence_service),
    doc_service: 'DocumentService' = Depends(_get_document_service)
):
    """实际的文档向量化业务逻辑调用。"""
    await doc_service.execute_document_vectorization(params_id)


@router.post(
    "/documents/tasks/graph/{job_id}/{params_id}",
    summary="[内部] 执行文档图谱化任务",
    description="由调度器调用，自动处理锁和状态更新。",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[None]
)
@job_endpoint(default_can_retry=True) # 图谱化失败允许重试
async def execute_graph_document_task(
    job_id: int,
    params_id: int,
    job_service: 'JobPersistenceService' = Depends(get_job_persistence_service),
    doc_service: 'DocumentService' = Depends(_get_document_service)
):
    """实际的文档图谱化业务逻辑调用。"""
    await doc_service.execute_document_graphing(params_id)