import logging
from typing import List, Optional
from fastapi import (
    APIRouter, Depends, UploadFile, File, Form, HTTPException, 
    status, Request, Body, BackgroundTasks
)
from sqlalchemy.ext.asyncio import AsyncSession

# 导入核心依赖获取函数
from app.core.database.session import get_db
from app.core.config.settings import settings

from app.api.dependencies import (
    get_current_active_user_id,
    get_user_docs_milvus_service_from_state,
    get_storage_service_from_state,
    get_chatai_service_from_state,
    get_redis_service_from_state,
    get_job_persistence_service,
    RateLimiter
)

# 导入核心 DTO 和异常
from app.core.dtos import ApiResponse, BaseIdRequestDto, PagedResultDto, DocumentAppType
from app.core.exceptions import NotFoundException, BusinessException

# 导入 DTO
from app.modules.tools.customerservice.services.chat_service import ChatService
from app.modules.tools.customerservice.services.dtos.chat_dto import (
    ChatSessionListRequestDto, ChatSessionCreateDto, ChatHistoryListRequestDto,
    ChatMessageRequestDto, ConnectionRequestDto
)
from app.modules.tools.customerservice.services.dtos.product_dto import (
    ProductCreateDto, ProductUpdateDto, ProductListRequestDto,
    ProductSearchRequestDto, ProductImageUploadDto, ProductImageDeleteDto
)

# 类型提示导入
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.ai.vector.base import IUserDocsMilvusService
    from app.core.storage.base import IStorageService
    from app.core.ai.chat.base import IChatAIService
    from app.core.redis.service import RedisService
    from app.core.job.services import JobPersistenceService
    from app.modules.tools.customerservice.services.iface.chat_service import IChatService
    from app.modules.tools.customerservice.services.iface.product_service import IProductService

# 获取 Logger
logger = logging.getLogger(__name__)

# 创建 CustomerService API Router
router = APIRouter(
    prefix="/customerservice",
    tags=["AI Customer Service"]
)

# 内部依赖项工厂：获取 ChatService 实例
def _get_chat_service(
    db: AsyncSession = Depends(get_db),
    user_docs_milvus_service: 'IUserDocsMilvusService' = Depends(get_user_docs_milvus_service_from_state),
    storage_service: Optional['IStorageService'] = Depends(get_storage_service_from_state),
    ai_service: 'IChatAIService' = Depends(get_chatai_service_from_state),
    redis_service: 'RedisService' = Depends(get_redis_service_from_state),
    job_persistence_service: 'JobPersistenceService' = Depends(get_job_persistence_service),
) -> 'IChatService':
    """内部依赖项：创建并返回 ChatService 及其内部所有依赖。"""
    # 在函数内部导入，避免循环依赖

    from app.modules.tools.customerservice.services.chat_ai_service import ChatAIService
    from app.modules.tools.customerservice.services.chat_tools_service import ChatToolsService
    from app.modules.tools.customerservice.services.product_service import ProductService
    from app.modules.tools.customerservice.repositories.chat_session_repository import ChatSessionRepository
    from app.modules.tools.customerservice.repositories.chat_history_repository import ChatHistoryRepository
    from app.modules.tools.customerservice.repositories.chat_connection_repository import ChatConnectionRepository
    from app.modules.tools.customerservice.repositories.product_repository import ProductRepository
    from app.modules.base.prompts.services import PromptTemplateService
    from app.modules.base.prompts.repositories import PromptTemplateRepository

    # 创建 Prompt 相关依赖
    prompt_repo = PromptTemplateRepository(db=db)
    prompt_service = PromptTemplateService(db=db, repository=prompt_repo, redis_service=redis_service)

    # 创建仓储
    product_repository = ProductRepository(db=db)
    chat_session_repository = ChatSessionRepository(db=db)
    chat_history_repository = ChatHistoryRepository(db=db)
    chat_connection_repository = ChatConnectionRepository(db=db)

    # 创建服务
    product_service = ProductService(
        product_repository=product_repository,
        storage_service=storage_service,
        settings=settings
    )
    
    chat_tools_service = ChatToolsService(
        product_service=product_service,
        ai_service=ai_service,
        user_docs_milvus_service=user_docs_milvus_service,
        settings=settings
    )
    
    chat_ai_service = ChatAIService(
        ai_service=ai_service,
        chat_tools_service=chat_tools_service,
        prompt_service=prompt_service,
        settings=settings
    )
    
    chat_service = ChatService(
        session_repository=chat_session_repository,
        history_repository=chat_history_repository,
        connection_repository=chat_connection_repository,
        storage_service=storage_service,
        chat_ai_service=chat_ai_service,
        settings=settings
    )
    
    return chat_service

# 内部依赖项工厂：获取 ProductService 实例
def _get_product_service(
    db: AsyncSession = Depends(get_db),
    storage_service: Optional['IStorageService'] = Depends(get_storage_service_from_state),
) -> 'IProductService':
    """内部依赖项：创建并返回 ProductService 及其内部所有依赖。"""
    # 在函数内部导入，避免循环依赖
    from app.modules.tools.customerservice.services.product_service import ProductService
    from app.modules.tools.customerservice.repositories.product_repository import ProductRepository

    # 创建仓储
    product_repository = ProductRepository(db=db)
    
    # 创建服务
    product_service = ProductService(
        product_repository=product_repository,
        storage_service=storage_service,
        settings=settings
    )
    
    return product_service

###################
# 商品管理 API 端点
###################

@router.post(
    "/prod/create",
    response_model=ApiResponse[int],
    summary="创建商品",
    description="创建新商品",
    dependencies=[Depends(get_current_active_user_id)]
)
async def create_product(
    request: ProductCreateDto = Depends(),
    images: List[UploadFile] = File(None),
    user_id: int = Depends(get_current_active_user_id),
    product_service: 'IProductService' = Depends(_get_product_service)
):
    """
    创建商品接口。

    - **商品信息**: 商品详细信息
    - **images**: 可选的商品图片文件列表

    *需要有效的登录令牌 (Authorization header)*
    """
    product_id = await product_service.create_product_async(user_id, request, images)
    return ApiResponse.success(data=product_id, message="创建商品成功")

@router.post(
    "/prod/update",
    response_model=ApiResponse,
    summary="更新商品",
    description="更新商品信息",
    dependencies=[Depends(get_current_active_user_id)]
)
async def update_product(
    request: ProductUpdateDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    product_service: 'IProductService' = Depends(_get_product_service)
):
    """
    更新商品接口。

    - **更新信息**: 需要更新的商品信息字段

    *需要有效的登录令牌 (Authorization header)*
    """
    result = await product_service.update_product_async(user_id, request)
    return ApiResponse.success(message="更新商品成功") if result else ApiResponse.fail(message="更新商品失败")

@router.post(
    "/prod/delete",
    response_model=ApiResponse,
    summary="删除商品",
    description="删除指定商品",
    dependencies=[Depends(get_current_active_user_id)]
)
async def delete_product(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    product_service: 'IProductService' = Depends(_get_product_service)
):
    """
    删除商品接口。

    - **id**: 商品ID

    *需要有效的登录令牌 (Authorization header)*
    """
    result = await product_service.delete_product_async(user_id, request.id)
    return ApiResponse.success(message="删除商品成功") if result else ApiResponse.fail(message="删除商品失败")

@router.post(
    "/prod/list",
    response_model=ApiResponse[PagedResultDto],
    summary="获取商品列表",
    description="分页获取商品列表",
    dependencies=[Depends(get_current_active_user_id)]
)
async def get_products(
    request: ProductListRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    product_service: 'IProductService' = Depends(_get_product_service)
):
    """
    获取商品列表接口。

    - **关键词**: 可选，搜索关键词
    - **pageIndex**: 页码，从1开始
    - **pageSize**: 每页数量

    *需要有效的登录令牌 (Authorization header)*
    """
    products = await product_service.get_products_async(user_id, request)
    return ApiResponse.success(data=products)

@router.post(
    "/prod/dtl",
    response_model=ApiResponse,
    summary="获取商品详情",
    description="获取指定商品的详细信息",
    dependencies=[Depends(get_current_active_user_id)]
)
async def get_product(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    product_service: 'IProductService' = Depends(_get_product_service)
):
    """
    获取商品详情接口。

    - **id**: 商品ID

    *需要有效的登录令牌 (Authorization header)*
    """
    product = await product_service.get_product_async(user_id, request.id)
    return ApiResponse.success(data=product)

@router.post(
    "/prod/image/upload",
    response_model=ApiResponse,
    summary="上传商品图片",
    description="为指定商品上传图片",
    dependencies=[Depends(get_current_active_user_id)]
)
async def upload_product_image(
    product_id: int = Form(...),
    image: UploadFile = File(...),
    user_id: int = Depends(get_current_active_user_id),
    product_service: 'IProductService' = Depends(_get_product_service)
):
    """
    上传商品图片接口。

    - **productId**: 商品ID
    - **image**: 图片文件

    *需要有效的登录令牌 (Authorization header)*
    """
    request = ProductImageUploadDto(product_id=product_id)
    img = await product_service.upload_product_image_async(user_id, request.product_id, image)
    return ApiResponse.success(data=img, message="上传商品图片成功")

@router.post(
    "/prod/image/delete",
    response_model=ApiResponse,
    summary="删除商品图片",
    description="删除指定商品的指定图片",
    dependencies=[Depends(get_current_active_user_id)]
)
async def delete_product_image(
    request: ProductImageDeleteDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    product_service: 'IProductService' = Depends(_get_product_service)
):
    """
    删除商品图片接口。

    - **productId**: 商品ID
    - **imageId**: 图片ID

    *需要有效的登录令牌 (Authorization header)*
    """
    result = await product_service.delete_product_image_async(user_id, request.product_id, request.image_id)
    return ApiResponse.success(message="删除商品图片成功") if result else ApiResponse.fail(message="删除商品图片失败")

###################
# 聊天会话管理 API 端点
###################

@router.post(
    "/session/create",
    response_model=ApiResponse,
    summary="创建聊天会话",
    description="创建新的客服聊天会话",
    dependencies=[Depends(get_current_active_user_id)]
)
async def create_session(
    request: ChatSessionCreateDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    chat_service: 'IChatService' = Depends(_get_chat_service)
):
    """
    创建聊天会话接口。

    - **userName**: 用户名称

    *需要有效的登录令牌 (Authorization header)*
    """
    session = await chat_service.create_session_async(user_id, request.user_name or "")
    return ApiResponse.success(data=session, message="会话创建成功")

@router.post(
    "/session/detail",
    response_model=ApiResponse,
    summary="获取会话详情",
    description="获取指定聊天会话的详细信息",
    dependencies=[Depends(get_current_active_user_id)]
)
async def get_session(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    chat_service: 'IChatService' = Depends(_get_chat_service)
):
    """
    获取会话详情接口。

    - **id**: 会话ID

    *需要有效的登录令牌 (Authorization header)*
    """
    session = await chat_service.get_session_async(user_id, request.id)
    if session is None:
        return ApiResponse.fail(message="会话不存在", code=404)
    return ApiResponse.success(data=session)

@router.post(
    "/session/list",
    response_model=ApiResponse[PagedResultDto],
    summary="获取会话列表",
    description="分页获取用户的聊天会话列表",
    dependencies=[Depends(get_current_active_user_id)]
)
async def get_session_list(
    request: ChatSessionListRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    chat_service: 'IChatService' = Depends(_get_chat_service)
):
    """
    获取会话列表接口。

    - **pageIndex**: 页码，从1开始
    - **pageSize**: 每页数量
    - **includeEnded**: 是否包含已结束的会话

    *需要有效的登录令牌 (Authorization header)*
    """
    result = await chat_service.get_user_sessions_async(user_id, request)
    return ApiResponse.success(data=result)

@router.post(
    "/session/end",
    response_model=ApiResponse,
    summary="结束会话",
    description="结束指定的聊天会话",
    dependencies=[Depends(get_current_active_user_id)]
)
async def end_session(
    request: BaseIdRequestDto = Body(...),
    chat_service: 'IChatService' = Depends(_get_chat_service)
):
    """
    结束会话接口。

    - **id**: 会话ID

    *需要有效的登录令牌 (Authorization header)*
    """
    result = await chat_service.end_session_async(request.id)
    return ApiResponse.success(message="会话已结束") if result else ApiResponse.fail(message="结束会话失败")

@router.post(
    "/session/history",
    response_model=ApiResponse[PagedResultDto],
    summary="获取会话历史记录",
    description="分页获取指定会话的历史聊天记录",
    dependencies=[Depends(get_current_active_user_id)]
)
async def get_session_history(
    request: ChatHistoryListRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    chat_service: 'IChatService' = Depends(_get_chat_service)
):
    """
    获取会话历史记录接口。

    - **sessionId**: 会话ID
    - **pageIndex**: 页码，从1开始
    - **pageSize**: 每页数量

    *需要有效的登录令牌 (Authorization header)*
    """
    result = await chat_service.get_session_history_async(user_id, request)
    return ApiResponse.success(data=result)

@router.post(
    "/message/send",
    response_model=ApiResponse,
    summary="发送文本消息",
    description="向指定会话发送文本消息",
    dependencies=[
        Depends(get_current_active_user_id),
        Depends(RateLimiter(limit=60, period_seconds=60, limit_type="user"))
    ]
)
async def send_message(
    request: ChatMessageRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    chat_service: 'IChatService' = Depends(_get_chat_service)
):
    """
    发送文本消息接口。

    - **sessionId**: 会话ID
    - **content**: 消息内容

    *需要有效的登录令牌 (Authorization header)*
    """
    result = await chat_service.send_message_async(user_id, request)
    return ApiResponse.success(data=result) if result.success else ApiResponse.fail(message=result.error_message or "")

@router.post(
    "/message/sendimage",
    response_model=ApiResponse,
    summary="发送图片消息",
    description="向指定会话发送图片消息",
    dependencies=[
        Depends(get_current_active_user_id),
        Depends(RateLimiter(limit=20, period_seconds=60, limit_type="user"))
    ]
)
async def send_image(
    session_id: int = Form(...),
    image: UploadFile = File(...),
    user_id: int = Depends(get_current_active_user_id),
    chat_service: 'IChatService' = Depends(_get_chat_service)
):
    """
    发送图片消息接口。

    - **sessionId**: 会话ID
    - **image**: 图片文件

    *需要有效的登录令牌 (Authorization header)*
    """
    if image is None:
        return ApiResponse.fail(message="请上传图片")
    
    result = await chat_service.send_image_async(user_id, session_id, image)
    return ApiResponse.success(data=result) if result.success else ApiResponse.fail(message=result.error_message or "")