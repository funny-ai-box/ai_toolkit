"""
智能客服路由模块
"""
import logging
from typing import List, Optional
from fastapi import (
    APIRouter, Depends, UploadFile, File, Form, HTTPException, 
    status, Request, Body
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.config.settings import settings
from app.api.dependencies import (
    get_current_active_user_id,
    get_storage_service_from_state,
    get_chatai_service_from_state,
    get_user_docs_milvus_service_from_state,
    RateLimiter
)
from app.core.dtos import ApiResponse, BaseIdRequestDto, PagedResultDto
from app.core.exceptions import NotFoundException, BusinessException

from app.modules.tools.customerservice.dtos import (
    # 聊天会话相关DTO
    ChatSessionDto, ChatMessageRequestDto, ChatMessageResultDto,
    ChatSessionListRequestDto, ChatSessionListItemDto, ChatSessionCreateDto,
    ChatHistoryListRequestDto, ChatHistoryDto,
    # 商品相关DTO
    ProductDetailDto, ProductListItemDto, ProductImageDto, 
    ProductCreateDto, ProductUpdateDto, ProductListRequestDto,
    ProductSearchRequestDto, GetProductByCodeRequestDto, 
    ProductImageUploadDto, ProductImageDeleteDto
)
from app.modules.tools.customerservice.services.chat_service import ChatService
from app.modules.tools.customerservice.services.product_service import ProductService
from app.modules.tools.customerservice.services.chat_ai_service import ChatAIService
from app.modules.tools.customerservice.services.chat_tools_service import ChatToolsService
from app.modules.base.prompts.services import PromptTemplateService

logger = logging.getLogger(__name__)

# 创建API路由
router = APIRouter(
    prefix="/customerservice",
    tags=["Customer Service"]
)

# 内部依赖项工厂：获取服务实例
def _get_services(
    db: AsyncSession = Depends(get_db),
    prompt_template_service: PromptTemplateService = Depends(),
    storage_service = Depends(get_storage_service_from_state),
    chatai_service = Depends(get_chatai_service_from_state),
    user_docs_milvus_service = Depends(get_user_docs_milvus_service_from_state)
):
    """内部依赖项：创建并返回客服模块所需的服务实例"""
    
    # 从配置获取参数
    chat_config = settings.get("CustomerService", {}).get("Chat", {})
    max_context_messages = int(chat_config.get("MaxContextMessages", 10))
    max_vector_search_results = int(chat_config.get("MaxVectorSearchResults", 5))
    min_vector_score = float(chat_config.get("MinVectorScore", 0.8))
    sensitive_words = chat_config.get("SensitiveWords", "色情、赌博、毒品、暴力等违法内容")
    
    # 创建AI服务
    chat_ai_service = ChatAIService(
        ai_service=chatai_service,
        prompt_template_service=prompt_template_service,
        sensitive_words=sensitive_words
    )
    
    # 创建产品服务
    product_service = ProductService(
        db=db,
        storage_service=storage_service
    )
    
    # 创建工具服务
    chat_tools_service = ChatToolsService(
        product_service=product_service,
        ai_service=chatai_service,
        user_docs_service=user_docs_milvus_service,
        max_vector_search_results=max_vector_search_results,
        min_vector_score=min_vector_score
    )
    
    # 创建聊天服务
    chat_service = ChatService(
        db=db,
        chat_ai_service=chat_ai_service,
        storage_service=storage_service,
        max_context_messages=max_context_messages
    )
    
    return chat_service, product_service

#######################
# 商品管理相关接口
#######################

@router.post("/prod/create", response_model=ApiResponse[BaseIdRequestDto])
async def create_product(
    request: ProductCreateDto = Form(...),
    images: Optional[List[UploadFile]] = File(None),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    创建商品
    
    - **code**: 商品编码（必需）
    - **name**: 商品名称（必需）
    - **price**: 商品价格（必需）
    - **description**: 商品描述（可选）
    - **sellingPoints**: 商品卖点（可选）
    - **stock**: 库存数量（必需）
    - **status**: 状态：1-正常，0-下架（默认1）
    - **images**: 商品图片（可选，最多10张）
    """
    _, product_service = services
    product_id = await product_service.create_product_async(user_id, request, images)
    return ApiResponse.success(data={"id": product_id}, message="创建商品成功")

@router.post("/prod/update", response_model=ApiResponse)
async def update_product(
    request: ProductUpdateDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    更新商品信息
    
    - **id**: 商品ID（必需）
    - **code**: 商品编码（可选）
    - **name**: 商品名称（可选）
    - **price**: 商品价格（可选）
    - **description**: 商品描述（可选）
    - **sellingPoints**: 商品卖点（可选）
    - **stock**: 库存数量（可选）
    - **status**: 状态：1-正常，0-下架（可选）
    """
    _, product_service = services
    result = await product_service.update_product_async(user_id, request)
    return ApiResponse.success(message="更新商品成功") if result else ApiResponse.fail("更新商品失败")

@router.post("/prod/delete", response_model=ApiResponse)
async def delete_product(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    删除商品
    
    - **id**: 商品ID（必需）
    """
    _, product_service = services
    result = await product_service.delete_product_async(user_id, request.id)
    return ApiResponse.success(message="删除商品成功") if result else ApiResponse.fail("删除商品失败")

@router.post("/prod/list", response_model=ApiResponse[PagedResultDto[ProductListItemDto]])
async def get_products(
    request: ProductListRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    获取商品列表
    
    - **keyword**: 搜索关键词（可选）
    - **pageIndex**: 页码（默认1）
    - **pageSize**: 每页数量（默认20）
    """
    _, product_service = services
    products = await product_service.get_products_async(user_id, request.dict())
    return ApiResponse.success(data=products)

@router.post("/prod/dtl", response_model=ApiResponse[ProductDetailDto])
async def get_product(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    获取商品详情
    
    - **id**: 商品ID（必需）
    """
    _, product_service = services
    product = await product_service.get_product_async(user_id, request.id)
    return ApiResponse.success(data=product)

@router.post("/prod/image/upload", response_model=ApiResponse[ProductImageDto])
async def upload_product_image(
    request: ProductImageUploadDto = Form(...),
    image: UploadFile = File(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    上传商品图片
    
    - **productId**: 商品ID（必需）
    - **image**: 图片文件（必需）
    """
    _, product_service = services
    img = await product_service.upload_product_image_async(user_id, request.product_id, image)
    return ApiResponse.success(data=img, message="上传商品图片成功")

@router.post("/prod/image/delete", response_model=ApiResponse)
async def delete_product_image(
    request: ProductImageDeleteDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    删除商品图片
    
    - **productId**: 商品ID（必需）
    - **imageId**: 图片ID（必需）
    """
    _, product_service = services
    result = await product_service.delete_product_image_async(user_id, request.product_id, request.image_id)
    return ApiResponse.success(message="删除商品图片成功") if result else ApiResponse.fail("删除商品图片失败")

#######################
# 聊天会话管理相关接口
#######################

@router.post("/session/create", response_model=ApiResponse[ChatSessionDto])
async def create_session(
    request: ChatSessionCreateDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    创建聊天会话
    
    - **userName**: 用户姓名（可选）
    """
    chat_service, _ = services
    session = await chat_service.create_session_async(user_id, request.user_name or "")
    return ApiResponse.success(data=session, message="会话创建成功")

@router.post("/session/detail", response_model=ApiResponse[ChatSessionDto])
async def get_session(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    获取会话详情
    
    - **id**: 会话ID（必需）
    """
    chat_service, _ = services
    session = await chat_service.get_session_async(user_id, request.id)
    if session is None:
        return ApiResponse.fail(message="会话不存在", code=404)
    return ApiResponse.success(data=session)

@router.post("/session/list", response_model=ApiResponse[PagedResultDto[ChatSessionListItemDto]])
async def get_session_list(
    request: ChatSessionListRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    获取会话列表
    
    - **pageIndex**: 页码（默认1）
    - **pageSize**: 每页数量（默认20）
    - **includeEnded**: 是否包含已结束的会话（默认true）
    """
    chat_service, _ = services
    result = await chat_service.get_user_sessions_async(user_id, request)
    return ApiResponse.success(data=result)

@router.post("/session/end", response_model=ApiResponse)
async def end_session(
    request: BaseIdRequestDto = Body(...),
    services = Depends(_get_services)
):
    """
    结束会话
    
    - **id**: 会话ID（必需）
    """
    chat_service, _ = services
    result = await chat_service.end_session_async(request.id)
    return ApiResponse.success(message="会话已结束") if result else ApiResponse.fail(message="结束会话失败")

@router.post("/session/history", response_model=ApiResponse[PagedResultDto[ChatHistoryDto]])
async def get_session_history(
    request: ChatHistoryListRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    获取会话历史记录
    
    - **sessionId**: 会话ID（必需）
    - **pageIndex**: 页码（默认1）
    - **pageSize**: 每页数量（默认20）
    """
    chat_service, _ = services
    result = await chat_service.get_session_history_async(user_id, request)
    return ApiResponse.success(data=result)

#######################
# 消息处理相关接口
#######################

@router.post("/message/send", response_model=ApiResponse[ChatMessageResultDto])
@RateLimiter(limit=60, period_seconds=60, limit_type="user")  # 每分钟最多60次请求
async def send_message(
    request: ChatMessageRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    发送文本消息
    
    - **sessionId**: 会话ID（必需）
    - **content**: 消息内容（必需）
    """
    chat_service, _ = services
    result = await chat_service.send_message_async(user_id, request)
    if result.success:
        return ApiResponse.success(data=result)
    else:
        return ApiResponse.fail(message=result.error_message or "")

@router.post("/message/sendimage", response_model=ApiResponse[ChatMessageResultDto])
@RateLimiter(limit=20, period_seconds=60, limit_type="user")  # 每分钟最多20次图片请求
async def send_image(
    session_id: int = Form(...),
    image: UploadFile = File(...),
    user_id: int = Depends(get_current_active_user_id),
    services = Depends(_get_services)
):
    """
    发送图片消息
    
    - **sessionId**: 会话ID（必需）
    - **image**: 图片文件（必需）
    """
    chat_service, _ = services
    
    if image is None:
        return ApiResponse.fail(message="请上传图片")
        
    result = await chat_service.send_image_async(user_id, session_id, image)
    
    if result.success:
        return ApiResponse.success(data=result)
    else:
        return ApiResponse.fail(message=result.error_message or "")