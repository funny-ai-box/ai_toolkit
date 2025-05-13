from typing import List, Optional
import asyncio
from fastapi import APIRouter, Depends, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (

    get_chatai_service_from_state,
    get_current_active_user_id,
    get_job_persistence_service,
    get_storage_service_from_state,
    get_user_docs_milvus_service_from_state,

)
from app.core.ai.chat.base import IChatAIService
from app.core.ai.vector.base import IUserDocsMilvusService
from app.core.database.session import get_db
from app.core.storage.base import IStorageService
from app.core.job.services import JobPersistenceService
from app.core.job.decorators import job_endpoint
from app.core.config.settings import settings
from app.core.dtos import ApiResponse, BaseIdRequestDto, BaseIdResponseDto

from app.modules.tools.social_content.repositories.platform_repository import PlatformRepository
from app.modules.tools.social_content.repositories.task_repository import TaskRepository
from app.modules.tools.social_content.services.platform_service import PlatformService
from app.modules.tools.social_content.services.task_service import TaskService
from app.modules.tools.social_content.services.ai_generate_service import AIGenerateService
from app.modules.tools.social_content.dtos.platform_dtos import (
    PlatformDto, PlatformPromptDto, UserPromptDto, 
    AddUserPromptRequestDto, UpdateUserPromptRequestDto
)
from app.modules.tools.social_content.dtos.task_dtos import (
    CreateTaskRequestDto, TaskDetailResponseDto, TaskListRequestDto, 
    TaskListItemDto, TaskStatusRequestDto
)


router = APIRouter(
    prefix="/socialcontent",
    tags=["socialcontent"],
    responses={404: {"description": "Not found"}},
)


# 依赖注入函数
def _get_platform_repository(db: AsyncSession = Depends(get_db)) -> PlatformRepository:
    """内部依赖项工厂：创建并返回 PlatformRepository 实例"""
    return PlatformRepository(db)


def _get_task_repository(db: AsyncSession = Depends(get_db)) -> TaskRepository:
    """内部依赖项工厂：创建并返回 TaskRepository 实例"""
    return TaskRepository(db)


def _get_platform_service(
    db: AsyncSession = Depends(get_db),
    platform_repository: PlatformRepository = Depends(_get_platform_repository)
) -> PlatformService:
    """内部依赖项工厂：创建并返回 PlatformService 实例"""
    return PlatformService(db=db)


def _get_ai_generate_service(
    db: AsyncSession = Depends(get_db),
    ai_service: IChatAIService = Depends(get_chatai_service_from_state),
    platform_repository: PlatformRepository = Depends(_get_platform_repository),
    task_repository: TaskRepository = Depends(_get_task_repository),
    user_docs_service: IUserDocsMilvusService = Depends(get_user_docs_milvus_service_from_state),
    storage_service: IStorageService = Depends(get_storage_service_from_state)
) -> AIGenerateService:
    """内部依赖项工厂：创建并返回 AIGenerateService 实例"""
    return AIGenerateService(
        db=db,
        ai_service=ai_service,
        platform_repository=platform_repository,
        task_repository=task_repository,
        user_docs_service=user_docs_service,
        task_img_storage_service=storage_service
    )


def _get_task_service(
    db: AsyncSession = Depends(get_db),
    task_repository: TaskRepository = Depends(_get_task_repository),
    platform_repository: PlatformRepository = Depends(_get_platform_repository),
    ai_generate_service: AIGenerateService = Depends(_get_ai_generate_service),
    storage_service: IStorageService = Depends(get_storage_service_from_state)
) -> TaskService:
    """内部依赖项工厂：创建并返回 TaskService 实例"""
    return TaskService(
        db=db,
        task_repository=task_repository,
        platform_repository=platform_repository,
        ai_generate_service=ai_generate_service,
        task_img_storage_service=storage_service,
        image_path_prefix=settings.SOCIAL_CONTENT_IMAGE_PATH_PREFIX
    )


# API 路由实现
# 平台相关API
@router.post("/platform/list")
async def get_all_platforms(
    platform_service: PlatformService = Depends(_get_platform_service),
    user_id: int = Depends(get_current_active_user_id)
) -> ApiResponse[List[PlatformDto]]:
    """获取所有平台"""
    platforms = await platform_service.get_all_platforms_async()
    return ApiResponse[List[PlatformDto]].success(platforms)


@router.post("/platform/sys-prompt/list")
async def get_platform_prompts(
    request: BaseIdRequestDto,
    platform_service: PlatformService = Depends(_get_platform_service),
    user_id: int = Depends(get_current_active_user_id)
) -> ApiResponse[List[PlatformPromptDto]]:
    """获取平台提示词配置列表"""
    prompts = await platform_service.get_platform_prompts_async(request.id)
    return ApiResponse[List[PlatformPromptDto]].success(prompts)


@router.post("/platform/user-prompt/list")
async def get_user_prompts(
    request: Optional[BaseIdRequestDto] = None,
    platform_service: PlatformService = Depends(_get_platform_service),
    user_id: int = Depends(get_current_active_user_id)
) -> ApiResponse[List[UserPromptDto]]:
    """获取用户的平台提示词配置列表"""
    platform_id = request.id if request and request.id > 0 else None
    prompts = await platform_service.get_user_prompts_async(user_id, platform_id)
    return ApiResponse[List[UserPromptDto]].success(prompts)


# Continuing the router.py implementation

@router.post("/platform/user-prompt/dtl")
async def get_user_prompt_detail(
    request: BaseIdRequestDto,
    platform_service: PlatformService = Depends(_get_platform_service),
    user_id: int = Depends(get_current_active_user_id)
) -> ApiResponse[UserPromptDto]:
    """获取用户的平台提示词详情"""
    prompt = await platform_service.get_user_prompt_async(user_id, request.id)
    return ApiResponse[UserPromptDto].success(prompt)


@router.post("/platform/user-prompt/add")
async def add_user_prompt(
    request: AddUserPromptRequestDto,
    platform_service: PlatformService = Depends(_get_platform_service),
    user_id: int = Depends(get_current_active_user_id)
) -> ApiResponse[BaseIdResponseDto]:
    """添加用户的平台提示词"""
    prompt_id = await platform_service.add_user_prompt_async(user_id, request)
    return ApiResponse[BaseIdResponseDto].success(BaseIdResponseDto(id=prompt_id), "添加用户模板成功")


@router.post("/platform/user-prompt/update")
async def update_user_prompt(
    request: UpdateUserPromptRequestDto,
    platform_service: PlatformService = Depends(_get_platform_service),
    user_id: int = Depends(get_current_active_user_id)
) -> ApiResponse:
    """更新用户的平台提示词"""
    result = await platform_service.update_user_prompt_async(user_id, request)
    return ApiResponse.success("更新用户模板成功")


@router.post("/platform/user-prompt/delete")
async def delete_user_prompt(
    request: BaseIdRequestDto,
    platform_service: PlatformService = Depends(_get_platform_service),
    user_id: int = Depends(get_current_active_user_id)
) -> ApiResponse:
    """删除用户的平台提示词"""
    result = await platform_service.delete_user_prompt_async(user_id, request.id)
    return ApiResponse.success("删除用户模板成功")


# 任务相关API
@router.post("/task/add")
async def create_task(
    task_name: str = Form(...),
    keywords: str = Form(...),
    product_info: Optional[str] = Form(None),
    platform_id: int = Form(...),
    prompt_id: int = Form(...),
    prompt_type: int = Form(...),
    content_count: int = Form(2),
    images: List[UploadFile] = File(None),
    task_service: TaskService = Depends(_get_task_service),
    user_id: int = Depends(get_current_active_user_id)
) -> ApiResponse[BaseIdResponseDto]:
    """创建文案生成任务"""
    # 构建请求DTO
    request = CreateTaskRequestDto(
        taskName=task_name,
        keywords=keywords,
        productInfo=product_info or "",
        platformId=platform_id,
        promptId=prompt_id,
        promptType=prompt_type,
        contentCount=content_count
    )
    
    # 创建任务
    task = await task_service.create_task_async(user_id, request, images)
    
    # 返回任务ID
    return ApiResponse[BaseIdResponseDto].success(BaseIdResponseDto(id=task.id), "任务创建成功")


class SSEResponse:
    """服务端事件响应封装"""
    
    def __init__(self):
        """初始化事件响应"""
        self.queue = asyncio.Queue()
    
    async def send_event(self, event_type: str, data: str, event_id: str):
        """
        发送事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
            event_id: 事件ID
        """
        message = f"id: {event_id}\nevent: {event_type}\ndata: {data}\n\n"
        await self.queue.put(message)
    
    async def iterator(self):
        """事件迭代器"""
        try:
            while True:
                message = await self.queue.get()
                yield message
                if message.startswith("id:") and "event: end" in message:
                    break
        except asyncio.CancelledError:
            # 客户端取消请求
            pass


@router.post("/task/add/stream")
async def create_task_stream(
    request: CreateTaskRequestDto,
    background_tasks: BackgroundTasks,
    task_service: TaskService = Depends(_get_task_service),
    user_id: int = Depends(get_current_active_user_id)
) -> StreamingResponse:
    """流式创建文案生成任务"""
    # 创建SSE响应
    sse = SSEResponse()
    event_id = str(asyncio.create_task(asyncio.sleep(0)).get_name())  # 生成唯一ID
    
    # 定义回调函数
    async def on_chunk_received(chunk: str):
        await sse.send_event("chunk", chunk, event_id)
    
    # 创建取消令牌
    cancel_token = asyncio.CancelToken()
    
    async def process_task():
        try:
            # 发送开始事件
            await sse.send_event("start", '{"message": "开始生成文案"}', event_id)
            
            # 调用流式API
            result = await task_service.streaming_create_task_async(
                user_id,
                request,
                on_chunk_received,
                cancel_token
            )
            
            # 序列化结果为JSON字符串
            import json
            from pydantic import json
            
            result_json = json.dumps(result.dict(by_alias=True))
            
            # 发送完成事件
            await sse.send_event("done", result_json, event_id)
        except asyncio.CancelledError:
            # 用户取消请求
            await sse.send_event("canceled", "请求已取消", event_id)
        except Exception as ex:
            # 发生错误
            await sse.send_event("error", str(ex), event_id)
        finally:
            # 发送结束事件
            await sse.send_event("end", "", event_id)
    
    # 添加后台任务
    background_tasks.add_task(process_task)
    
    # 返回流式响应
    return StreamingResponse(
        sse.iterator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/task/dtl")
async def get_task_detail(
    request: BaseIdRequestDto,
    task_service: TaskService = Depends(_get_task_service),
    user_id: int = Depends(get_current_active_user_id)
) -> ApiResponse[TaskDetailResponseDto]:
    """获取任务详情"""
    task = await task_service.get_task_async(user_id, request.id)
    return ApiResponse[TaskDetailResponseDto].success(task)


@router.post("/task/list")
async def get_user_tasks(
    request: TaskListRequestDto,
    task_service: TaskService = Depends(_get_task_service),
    user_id: int = Depends(get_current_active_user_id)
) -> ApiResponse[List[TaskListItemDto]]:
    """获取用户任务列表"""
    tasks = await task_service.get_user_tasks_async(user_id, request)
    return ApiResponse[List[TaskListItemDto]].success(tasks)


# 任务执行API - 用于后台处理任务
@router.post("/tasks/process/{job_id}/{task_id}")
@job_endpoint(default_can_retry=True)
async def process_task(
    job_id: int,
    task_id: int,
    job_service: JobPersistenceService = Depends(get_job_persistence_service),
    task_service: TaskService = Depends(_get_task_service)
) -> bool:
    """
    处理社交内容生成任务
    
    Args:
        job_id: 任务ID
        task_id: 社交内容任务ID
        
    Returns:
        处理结果
    """
    return await task_service.process_task_async(task_id)


