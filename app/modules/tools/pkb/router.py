"""
个人知识库API路由
"""
import json
import logging
from typing import List, Optional, AsyncGenerator
import uuid
from fastapi import (
    APIRouter, 
    Depends, 
    Body, 
    Request, 
    Response,
    BackgroundTasks, 
    status
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.config.settings import settings
from app.core.dtos import ApiResponse, BaseIdRequestDto
from app.core.exceptions import BusinessException
from app.core.ai.chat.base import IChatAIService
from app.core.ai.vector.base import IUserDocsMilvusService
from app.core.utils.snowflake import generate_id

from app.api.dependencies import (
    get_current_active_user_id,
    get_user_docs_milvus_service_from_state,
    get_chatai_service_from_state,
    get_redis_service_from_state,
    RateLimiter
)

from app.modules.base.prompts.repositories import PromptTemplateRepository
from app.modules.base.prompts.services import PromptTemplateService
from app.modules.base.knowledge.repositories.document_repository import DocumentRepository

from app.modules.tools.pkb.dtos.chat_message import (
    ChatMessageDto, 
    ChatRequestDto, 
    ChatReplyDto, 
    PagedChatHistoryDto,
    ChatSessionHistory,
    ChatHistoryPaginated
)
from app.modules.tools.pkb.dtos.chat_session import (
    ChatSessionInfoDto,
    ChatSessionCreateRequestDto,
    ChatSessionUpdateRequestDto
)
from app.modules.tools.pkb.dtos.share_session import (
    ShareSessionRequestDto,
    ShareSessionResponseDto,
    GetSessionByShareCodeDto,
    ChatWithSharedSession
)
from app.modules.tools.pkb.repositories.chat_session_repository import ChatSessionRepository
from app.modules.tools.pkb.repositories.chat_history_repository import ChatHistoryRepository
from app.modules.tools.pkb.services.chat_service import ChatService
from app.modules.tools.pkb.services.pkb_service import PKBService

# 获取日志记录器
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter(
    prefix="/pkb",
    tags=["Personal Knowledge Base"]
)

# 内部依赖项: 获取 PKBService 实例
def _get_pkb_service(
    db: AsyncSession = Depends(get_db),
    user_docs_milvus_service: IUserDocsMilvusService = Depends(get_user_docs_milvus_service_from_state),
    ai_service: IChatAIService = Depends(get_chatai_service_from_state),
    redis_service = Depends(get_redis_service_from_state)
) -> PKBService:
    """内部依赖项: 创建并返回 PKBService 及其内部所有依赖"""
    # 创建仓储
    chat_session_repository = ChatSessionRepository(db)
    chat_history_repository = ChatHistoryRepository(db)
    document_repository = DocumentRepository(db)
    
    # 创建提示词服务
    prompt_template_repository = PromptTemplateRepository(db)   
    prompt_template_service = PromptTemplateService(
        db=db,
        repository=prompt_template_repository,
        redis_service=redis_service
    )
    
    # 创建聊天服务
    chat_service = ChatService(
        db=db,
        settings=settings,
        chat_session_repository=chat_session_repository,
        chat_history_repository=chat_history_repository,
        ai_service=ai_service,
        user_docs_service=user_docs_milvus_service,
        prompt_template_service=prompt_template_service
    )
    
    # 创建PKB服务
    pkb_service = PKBService(
        db=db,
        settings=settings,
        chat_service=chat_service,
        document_repository=document_repository
    )
    
    return pkb_service


# API 端点定义

@router.post(
    "/chat/sessions/create",
    response_model=ApiResponse[int],
    summary="创建聊天会话",
    description="创建一个新的聊天会话",
)
async def create_chat_session(
    request: ChatSessionCreateRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    pkb_service: PKBService = Depends(_get_pkb_service)
):
    """
    创建聊天会话
    
    - **sessionName**: 会话名称 (可选)
    - **prompt**: 自定义提示词 (可选)
    - **documentId**: 文档ID，为0不指定文档 (必需)
    
    *需要有效的登录令牌*
    """
    session_id = await pkb_service.create_chat_session_async(
        user_id=user_id,
        document_id=request.document_id,
        session_name=request.session_name or "",
        prompt=request.prompt
    )
    return ApiResponse.success(data=session_id, message="会话创建成功")


@router.post(
    "/chat/sessions/update",
    response_model=ApiResponse,
    summary="更新聊天会话",
    description="更新聊天会话的名称或提示词",
)
async def update_chat_session(
    request: ChatSessionUpdateRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    pkb_service: PKBService = Depends(_get_pkb_service)
):
    """
    更新聊天会话
    
    - **sessionId**: 会话ID (必需)
    - **sessionName**: 会话名称 (可选)
    - **prompt**: 自定义提示词 (可选)
    
    *需要有效的登录令牌*
    """
    result = await pkb_service.update_chat_session_async(
        session_id=request.session_id,
        session_name=request.session_name,
        prompt=request.prompt
    )
    return ApiResponse.success(message="会话更新成功") if result else ApiResponse.fail(message="会话更新失败")


@router.post(
    "/chat/sessions/delete",
    response_model=ApiResponse,
    summary="删除聊天会话",
    description="删除指定ID的聊天会话及其所有历史记录",
)
async def delete_chat_session(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    pkb_service: PKBService = Depends(_get_pkb_service)
):
    """
    删除聊天会话
    
    - **id**: 会话ID (必需)
    
    *需要有效的登录令牌*
    """
    result = await pkb_service.delete_chat_session_async(request.id)
    return ApiResponse.success(message="会话删除成功") if result else ApiResponse.fail(message="会话删除失败")


@router.post(
    "/chat/sessions/list",
    response_model=ApiResponse[List[ChatSessionInfoDto]],
    summary="获取用户所有聊天会话",
    description="获取当前用户的所有聊天会话列表",
)
async def get_user_chat_sessions(
    user_id: int = Depends(get_current_active_user_id),
    pkb_service: PKBService = Depends(_get_pkb_service)
):
    """
    获取用户的所有聊天会话
    
    *需要有效的登录令牌*
    """
    sessions = await pkb_service.get_user_chat_sessions_async(user_id)
    return ApiResponse.success(data=sessions)


@router.post(
    "/chat/sessions/dtl",
    response_model=ApiResponse[ChatSessionInfoDto],
    summary="获取聊天会话详情",
    description="获取指定ID的聊天会话详细信息",
)
async def get_chat_session_detail(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    pkb_service: PKBService = Depends(_get_pkb_service)
):
    """
    获取聊天会话详情
    
    - **id**: 会话ID (必需)
    
    *需要有效的登录令牌*
    """
    session = await pkb_service.get_chat_session_detail_async(request.id)
    if not session:
        return ApiResponse.fail(message="会话不存在", code=status.HTTP_404_NOT_FOUND)
    return ApiResponse.success(data=session)


@router.post(
    "/chat/sessions/history",
    response_model=ApiResponse[List[ChatMessageDto]],
    summary="获取聊天历史",
    description="获取指定会话的聊天历史记录",
)
async def get_chat_history(
    request: ChatSessionHistory = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    pkb_service: PKBService = Depends(_get_pkb_service)
):
    """
    获取聊天历史
    
    - **sessionId**: 会话ID (必需)
    - **limit**: 数量限制 (可选，默认20)
    
    *需要有效的登录令牌*
    """
    history = await pkb_service.get_chat_history_async(request.session_id, request.limit)
    return ApiResponse.success(data=history)


@router.post(
    "/chat/sessions/history/paged",
    response_model=ApiResponse[PagedChatHistoryDto],
    summary="分页获取聊天历史",
    description="分页获取指定会话的聊天历史记录",
)
async def get_chat_history_paginated(
    request: ChatHistoryPaginated = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    pkb_service: PKBService = Depends(_get_pkb_service)
):
    """
    分页获取聊天历史
    
    - **sessionId**: 会话ID (必需)
    - **pageSize**: 每页大小 (必需)
    - **lastId**: 上次加载的最后一条记录ID，首次加载不传 (可选)
    
    *需要有效的登录令牌*
    """
    history = await pkb_service.get_chat_history_paginated_async(
        request.session_id, 
        request.page_size, 
        request.last_id
    )
    
    if history:
        result = PagedChatHistoryDto(
            messages=history,
            has_more=len(history) == request.page_size,
            next_last_id=min(h.id for h in history) if history else None
        )
        return ApiResponse.success(data=result)
    
    return ApiResponse.success(
        data=PagedChatHistoryDto(
            messages=[],
            has_more=False,
            next_last_id=None
        )
    )


@router.post(
    "/chat/sessions/chat",
    response_model=ApiResponse[ChatReplyDto],
    summary="聊天",
    description="发送消息并获取AI回复",
    dependencies=[Depends(RateLimiter(limit=60, period_seconds=60, limit_type="user"))]
)
async def chat(
    request: ChatRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    pkb_service: PKBService = Depends(_get_pkb_service)
):
    """
    聊天
    
    - **sessionId**: 会话ID (必需)
    - **message**: 消息内容 (必需)
    
    *需要有效的登录令牌*
    """
    if not request.message:
        return ApiResponse.fail(message="消息内容不能为空", code=status.HTTP_400_BAD_REQUEST)
    
    reply = await pkb_service.chat_async(user_id, request.session_id, request.message)
    return ApiResponse.success(data=reply)


@router.post(
    "/chat/sessions/chatstream",
    summary="流式聊天",
    description="发送消息并获取流式AI回复",
    dependencies=[Depends(RateLimiter(limit=60, period_seconds=60, limit_type="user"))]
)
async def chat_streaming(
    request: ChatRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    pkb_service: PKBService = Depends(_get_pkb_service)
):
    """
    流式聊天
    
    - **sessionId**: 会话ID (必需)
    - **message**: 消息内容 (必需)
    
    返回Server-Sent Events流
    
    *需要有效的登录令牌*
    """
    if not request.message:
        return ApiResponse.fail(message="消息内容不能为空", code=status.HTTP_400_BAD_REQUEST)
    
    async def event_generator():
        # 创建事件ID
        event_id = str(uuid.uuid4()).replace("-", "")
        
        try:
            # 发送开始事件
            yield f"id: {event_id}\n"
            yield f"event: start\n"
            yield f"data: {json.dumps({'message': '开始生成回复'})}\n\n"
            
            # 定义回调函数
            async def on_chunk_received(chunk):
                nonlocal event_id
                yield f"id: {event_id}\n"
                yield f"event: chunk\n"
                yield f"data: {chunk}\n\n"
            
            # 包装回调函数使其可以在流中使用
            buffer = []
            
            def callback(chunk):
                buffer.append(chunk)
            
            # 调用流式聊天API
            final_reply = await pkb_service.streaming_chat_async(
                user_id,
                request.session_id,
                request.message,
                callback
            )
            
            # 发送缓冲的数据块
            for chunk in buffer:
                yield f"id: {event_id}\n"
                yield f"event: chunk\n"
                yield f"data: {chunk}\n\n"
            
            # 发送完成事件，包含完整回复（包括引用源）
            yield f"id: {event_id}\n"
            yield f"event: done\n"
            yield f"data: {json.dumps(final_reply.dict(by_alias=True))}\n\n"
            
        except Exception as ex:
            # 发生错误
            error_message = str(ex)
            if isinstance(ex, BusinessException):
                error_message = ex.message
            
            yield f"id: {event_id}\n"
            yield f"event: error\n"
            yield f"data: {error_message}\n\n"
        finally:
            # 发送结束事件
            yield f"id: {event_id}\n"
            yield f"event: end\n"
            yield f"data: \n\n"
    
    # 设置响应
    return StreamingResponse(
        content=event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@router.post(
    "/chat/share",
    response_model=ApiResponse[ShareSessionResponseDto],
    summary="分享聊天会话",
    description="分享或取消分享聊天会话"
)
async def share_session(
    request: ShareSessionRequestDto = Body(...),
    request_obj: Request = Request,
    user_id: int = Depends(get_current_active_user_id),
    pkb_service: PKBService = Depends(_get_pkb_service)
):
    """
    分享聊天会话
    
    - **sessionId**: 会话ID (必需)
    - **isShared**: 是否分享 (必需)
    
    *需要有效的登录令牌*
    """
    base_url = f"{request_obj.url.scheme}://{request_obj.url.netloc}"
    result = await pkb_service.share_session_async(request.session_id, request.is_shared, base_url)
    
    return ApiResponse.success(
        data=result,
        message="会话分享成功" if request.is_shared else "会话取消分享成功"
    )


@router.post(
    "/chat/share/get",
    response_model=ApiResponse[ChatSessionInfoDto],
    summary="获取分享的会话信息",
    description="通过分享码获取会话信息"
)
async def get_session_by_share_code(
    request: GetSessionByShareCodeDto = Body(...),
    pkb_service: PKBService = Depends(_get_pkb_service)
):
    """
    通过分享码获取会话信息
    
    - **shareCode**: 分享码 (必需)
    
    *不需要登录*
    """
    try:
        session = await pkb_service.get_session_by_share_code_async(request.share_code or "")
        return ApiResponse.success(data=session)
    except BusinessException as ex:
        return ApiResponse.fail(message=ex.message, code=status.HTTP_404_NOT_FOUND)


@router.post(
    "/chat/share/chat",
    response_model=ApiResponse[ChatReplyDto],
    summary="与分享的会话聊天",
    description="使用分享的会话进行聊天",
    dependencies=[Depends(RateLimiter(limit=30, period_seconds=60, limit_type="ip"))]
)
async def chat_with_shared_session(
    request: ChatWithSharedSession = Body(...),
    pkb_service: PKBService = Depends(_get_pkb_service)
):
    """
    与分享的会话聊天
    
    - **shareCode**: 分享码 (必需)
    - **message**: 消息内容 (必需)
    
    *不需要登录，基于IP限流*
    """
    if not request.message:
        return ApiResponse.fail(message="消息内容不能为空", code=status.HTTP_400_BAD_REQUEST)
    
    try:
        # 获取分享的会话
        session = await pkb_service.get_session_by_share_code_async(request.share_code or "")
        if not session:
            return ApiResponse.fail(message="分享的会话不存在或已取消分享", code=status.HTTP_404_NOT_FOUND)
        
        # 使用会话的创建者ID进行聊天
        # 注：这里使用0作为用户ID，表示匿名用户
        reply = await pkb_service.chat_async(0, session.id, request.message)
        return ApiResponse.success(data=reply)
    
    except BusinessException as ex:
        return ApiResponse.fail(message=ex.message, code=status.HTTP_404_NOT_FOUND)