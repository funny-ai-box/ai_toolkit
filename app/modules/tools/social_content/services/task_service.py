# app/modules/tools/social_content/services/task_service.py
from typing import List, Optional, Dict, Any, Callable, Tuple
import os
import logging
import asyncio # Keep asyncio import
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile

from app.core.exceptions import BusinessException, NotFoundException # Added NotFoundException
from app.core.storage.base import IStorageService
from app.core.utils.snowflake import generate_id # Ensure this path is correct
from app.core.dtos import PagedResultDto # Assuming this is the generic one

from app.modules.tools.social_content.repositories.task_repository import TaskRepository
from app.modules.tools.social_content.repositories.platform_repository import PlatformRepository
from app.modules.tools.social_content.services.ai_generate_service import AIGenerateService
from app.modules.tools.social_content.models import (
    GenerationTask, GenerationTaskPlatform, GenerationTaskImage,
    GeneratedContent, GenerationTaskStatus, PromptTypeEnum
)
from app.modules.tools.social_content.dtos.task_dtos import (
    CreateTaskRequestDto, TaskDetailResponseDto, TaskListRequestDto,
    TaskListItemDto, TaskPlatformDto, TaskImageDto, GeneratedContentDto
)


class TaskService:
    """任务服务实现"""

    def __init__(
        self,
        db: AsyncSession,
        task_repository: TaskRepository,
        platform_repository: PlatformRepository,
        ai_generate_service: AIGenerateService,
        task_img_storage_service: IStorageService,
        image_path_prefix: str
    ):
        self.db = db
        self.task_repository = task_repository
        self.platform_repository = platform_repository
        self.ai_generate_service = ai_generate_service
        self.task_img_storage_service = task_img_storage_service
        self.image_path_prefix = image_path_prefix
        self.logger = logging.getLogger(__name__)

    async def create_task_async(
        self, user_id: int, request: CreateTaskRequestDto, images: Optional[List[UploadFile]] = None
    ) -> GenerationTask:
        try:
            task = GenerationTask(
                user_id=user_id,
                task_name=request.task_name,
                keywords=request.keywords,
                product_info=request.product_info
            )
            task_id = await self.task_repository.create_task_async(task)
            task.id = task_id # Assign the generated ID back to the object

            prompt_system_content, prompt_template_content = await self._get_prompt_template_content(request)

            task_platform = GenerationTaskPlatform(
                task_id=task_id,
                platform_id=request.platform_id,
                prompt_id=request.prompt_id,
                prompt_type=int(request.prompt_type),
                template_content=prompt_template_content,
                system_prompt=prompt_system_content,
                content_count=request.content_count,
                # status is set in repository
            )
            await self.task_repository.add_task_platform_async(task_platform)

            if images:
                for image_file in images: # Renamed image to image_file
                    filename = image_file.filename
                    ext = os.path.splitext(filename)[1] if filename else ".jpg"
                    # Ensure image_path_prefix ends with a slash if it's a directory
                    if self.image_path_prefix and not self.image_path_prefix.endswith('/'):
                        prefix_to_use = self.image_path_prefix + '/'
                    else:
                        prefix_to_use = self.image_path_prefix or ""

                    file_key = f"{prefix_to_use}{user_id}/{generate_id()}{ext}" # Use file_key for storage

                    contents = await image_file.read()
                    cdn_url = await self.task_img_storage_service.upload_async(
                        contents, file_key, image_file.content_type
                    )
                    task_image = GenerationTaskImage(
                        task_id=task_id,
                        image_path=cdn_url # Store the accessible URL
                    )
                    await self.task_repository.add_task_image_async(task_image)
            return task
        except BusinessException: # Re-raise known business exceptions
            raise
        except Exception as ex:
            print(f"创建任务失败，用户ID：{user_id}: {str(ex)}", exc_info=True)
            raise BusinessException(f"创建任务时发生内部错误: {str(ex)}")


    async def _get_prompt_template_content(
        self, request: CreateTaskRequestDto
    ) -> Tuple[Optional[str], Optional[str]]: # Return types can be Optional
        """
        获取任务的提示词内容（系统默认，或者用户自定义，看用户前端的选择）

        Args:
            request: 创建任务请求

        Returns:
            (系统提示词, 模板内容)
        """
        prompt_template: Optional[str] = ""
        system_prompt: Optional[str] = ""

        if request.prompt_type == PromptTypeEnum.SYSTEM:
            platform_prompt = await self.platform_repository.get_platform_prompt_async(request.prompt_id)
            if not platform_prompt:
                raise NotFoundException(f"系统Prompt不存在: {request.prompt_id}")
            prompt_template = platform_prompt.template_content
            system_prompt = platform_prompt.system_prompt
        elif request.prompt_type == PromptTypeEnum.USER: # Explicitly check USER type
            user_prompt = await self.platform_repository.get_user_prompt_async(request.prompt_id)
            if not user_prompt: # Make sure prompt exists and belongs to user if that's a rule
                raise NotFoundException(f"用户Prompt不存在: {request.prompt_id}")
            # Add user check if necessary:
            # if user_prompt.user_id != request.user_id: # Assuming user_id is part of request or context
            #     raise BusinessException("无权限访问此用户Prompt")
            prompt_template = user_prompt.template_content
            system_prompt = user_prompt.system_prompt
        else:
            raise BusinessException(f"未知的Prompt类型: {request.prompt_type}")

        return (system_prompt, prompt_template)

    async def get_task_async(self, user_id: int, task_id: int) -> TaskDetailResponseDto:
        task = await self.task_repository.get_task_async(task_id)
        if not task or task.user_id != user_id:
            raise NotFoundException("任务不存在或无权限访问")

        platforms = await self.platform_repository.get_all_platforms_async()
        platform_dict = {p.id: p for p in platforms}

        # For templates, it's better to fetch them based on IDs found in task_platforms
        # This avoids fetching ALL user prompts if not needed.
        task_platforms_entities = await self.task_repository.get_task_platforms_async(task_id)
        task_platform_dtos = []

        for tp_entity in task_platforms_entities:
            platform_info = platform_dict.get(tp_entity.platform_id)
            template_name = "未知模板" # Default

            if tp_entity.prompt_id is not None:
                if tp_entity.prompt_type == PromptTypeEnum.SYSTEM:
                    pt = await self.platform_repository.get_platform_prompt_async(tp_entity.prompt_id)
                    if pt: template_name = pt.template_name
                elif tp_entity.prompt_type == PromptTypeEnum.USER:
                    ut = await self.platform_repository.get_user_prompt_async(tp_entity.prompt_id)
                    if ut and ut.user_id == user_id : template_name = ut.template_name # Check ownership
                    elif ut: template_name = "无权限模板"


            tp_dto = TaskPlatformDto(
                id=tp_entity.id,
                platform_id=tp_entity.platform_id,
                platform_name=platform_info.name if platform_info else "未知平台",
                platform_code=platform_info.code if platform_info else "unknown",
                prompt_id=tp_entity.prompt_id,
                prompt_template_name=template_name,
                prompt_type=int(tp_entity.prompt_type),
                template_content=tp_entity.template_content, # Content stored with task_platform
                system_prompt=tp_entity.system_prompt,       # System prompt stored with task_platform
                status=tp_entity.status,
                status_name=self._get_status_name(tp_entity.status),
                content_count=tp_entity.content_count
            )
            task_platform_dtos.append(tp_dto)

        task_images_entities = await self.task_repository.get_task_images_async(task_id)
        task_image_dtos = [
            TaskImageDto.model_validate(ti) for ti in task_images_entities # Using model_validate
        ]

        contents_entities = await self.task_repository.get_task_generated_contents_async(task_id)
        content_dtos = []
        
        # Mapping for prompt template name for generated content (already in task_platform_dtos)
        task_platform_dto_map = {tpd.id: tpd for tpd in task_platform_dtos}

        for content_entity in contents_entities:
            task_platform_dto = task_platform_dto_map.get(content_entity.task_platform_id)
            platform_info = platform_dict.get(content_entity.platform_id)

            content_dtos.append(GeneratedContentDto(
                id=content_entity.id,
                task_platform_id=content_entity.task_platform_id,
                prompt_template_name=task_platform_dto.prompt_template_name if task_platform_dto else "未知模板",
                platform_id=content_entity.platform_id,
                platform_name=platform_info.name if platform_info else "未知平台",
                content_index=content_entity.content_index,
                content=content_entity.content,
                create_date=content_entity.create_date
            ))

        return TaskDetailResponseDto(
            id=task.id,
            task_name=task.task_name,
            keywords=task.keywords,
            product_info=task.product_info,
            status=task.status,
            status_name=self._get_status_name(task.status),
            process_message=task.process_message,
            completion_rate=task.completion_rate,
            create_date=task.create_date,
            platforms=task_platform_dtos,
            images=task_image_dtos,
            contents=content_dtos
        )

    async def get_user_tasks_async(self, user_id: int, request: TaskListRequestDto) -> PagedResultDto[TaskListItemDto]:
        tasks_entities, total_count = await self.task_repository.get_user_tasks_async(
            user_id, request.page_index, request.page_size
        )
        items_dtos: List[TaskListItemDto] = []
        if tasks_entities:
            for t_entity in tasks_entities:
                # Optimized: Fetch counts in bulk if performance becomes an issue.
                # For now, individual fetches for clarity based on original structure.
                task_platforms = await self.task_repository.get_task_platforms_async(t_entity.id)
                task_images = await self.task_repository.get_task_images_async(t_entity.id)
                task_contents = await self.task_repository.get_task_generated_contents_async(t_entity.id)
                
                items_dtos.append(TaskListItemDto(
                    id=t_entity.id,
                    task_name=t_entity.task_name,
                    platform_count=len(task_platforms),
                    image_count=len(task_images),
                    content_count=len(task_contents),
                    status=t_entity.status,
                    status_name=self._get_status_name(t_entity.status),
                    completion_rate=t_entity.completion_rate,
                    create_date=t_entity.create_date
                ))
        
        return PagedResultDto[TaskListItemDto](
            items=items_dtos,
            total_count=total_count,
            page_index=request.page_index,
            page_size=request.page_size,
            # Ensure total_pages is at least 0, and 1 if there are items but less than a page
            total_pages=( (total_count + request.page_size - 1) // request.page_size if request.page_size > 0 else 0 ) if total_count > 0 else 0
        )

    async def process_task_async(
        self,
        task_id: int,
        on_chunk_received: Optional[Callable[[str], None]] = None
        # Removed cancellation_token: Optional[asyncio.CancelToken] = None
    ) -> bool:
        task = await self.task_repository.get_task_async(task_id)
        if not task:
            self.logger.warning(f"任务处理失败：任务不存在，任务ID：{task_id}")
            await self.task_repository.update_task_status_async(task_id, GenerationTaskStatus.FAILED, "任务不存在")
            return False
        if task.status != GenerationTaskStatus.PENDING:
            self.logger.warning(
                f"任务处理失败：任务状态不正确，任务ID：{task_id}, 状态：{task.status}"
            )
            # Optionally update message if already processing or completed/failed
            # await self.task_repository.update_task_status_async(task_id, task.status, "任务状态不正确，无法重复处理")
            return False

        try:
            await self.task_repository.update_task_status_async(
                task_id, GenerationTaskStatus.PROCESSING, "开始处理任务", 0.0
            )

            task_images = await self.task_repository.get_task_images_async(task_id)
            task_platforms = await self.task_repository.get_task_platforms_async(task_id)

            await self.ai_generate_service.generate_images_desc_async(task_images)

            processed_platforms = 0
            total_platforms = len(task_platforms) if task_platforms else 0 # Handle empty list

            await self.task_repository.update_task_status_async(
                task_id, GenerationTaskStatus.PROCESSING,
                "图片处理完成，准备生成内容",
                self._calculate_completion_rate(0, total_platforms) # Start with 0 platforms processed for content
            )

            related_contents = await self.ai_generate_service.search_related_contents_async(task, task_images)

            for tp_entity in task_platforms: # Renamed task_platform to tp_entity
                try:
                    await self.task_repository.update_task_platform_status_async(
                        tp_entity.id, GenerationTaskStatus.PROCESSING
                    )
                    generated_contents = await self.ai_generate_service.generate_platform_contents_async(
                        task, tp_entity, task_images, related_contents, on_chunk_received
                        # Removed cancellation_token
                    )
                    if generated_contents: # Only add if list is not empty
                        await self.task_repository.add_generated_contents_async(generated_contents)

                    await self.task_repository.update_task_platform_status_async(
                        tp_entity.id, GenerationTaskStatus.COMPLETED
                    )
                    processed_platforms += 1
                    await self.task_repository.update_task_status_async(
                        task_id, GenerationTaskStatus.PROCESSING,
                        f"正在生成内容，已完成 {processed_platforms}/{total_platforms} 个平台",
                        self._calculate_completion_rate(processed_platforms, total_platforms)
                    )
                except asyncio.CancelledError: # Catch cancellation here if generate_platform_contents_async re-raises it
                    self.logger.info(f"处理任务平台被取消，任务ID：{task_id}, 平台ID：{tp_entity.platform_id}")
                    await self.task_repository.update_task_platform_status_async(
                        tp_entity.id, GenerationTaskStatus.FAILED # Or a new CANCELLED status
                    )
                    # To cancel the whole task, re-raise CancelledError
                    raise
                except Exception as ex_platform:
                    print(
                        f"处理任务平台失败，任务ID：{task_id}, 平台ID：{tp_entity.platform_id}: {str(ex_platform)}", exc_info=True
                    )
                    await self.task_repository.update_task_platform_status_async(
                        tp_entity.id, GenerationTaskStatus.FAILED
                    )
                    # Optionally, decide if one platform failure fails the whole task or just logs and continues

            # Check if all platforms failed or if some succeeded
            final_status = GenerationTaskStatus.COMPLETED
            final_message = "任务处理完成"
            if processed_platforms == 0 and total_platforms > 0:
                final_status = GenerationTaskStatus.FAILED
                final_message = "所有平台内容生成失败"
            elif processed_platforms < total_platforms :
                final_status = GenerationTaskStatus.COMPLETED # Or a new PARTIALLY_COMPLETED status
                final_message = f"任务部分完成，{processed_platforms}/{total_platforms} 个平台成功"


            await self.task_repository.update_task_status_async(
                task_id, final_status, final_message, 100.0 # Completion rate is 100% of processing attempt
            )
            return final_status == GenerationTaskStatus.COMPLETED or processed_platforms > 0

        except asyncio.CancelledError:
            self.logger.info(f"任务处理被取消，任务ID：{task_id}")
            await self.task_repository.update_task_status_async(
                task_id, GenerationTaskStatus.FAILED, "任务处理被取消", # Or a CANCELLED status
                task.completion_rate # Keep last known rate or reset
            )
            return False # Or re-raise if caller needs to know it was cancelled
        except Exception as ex_task:
            print(f"处理任务失败，任务ID：{task_id}: {str(ex_task)}", exc_info=True)
            await self.task_repository.update_task_status_async(
                task_id, GenerationTaskStatus.FAILED, f"处理失败：{str(ex_task)}",
                task.completion_rate if task else 0.0
            )
            return False

    async def streaming_create_task_async(
        self,
        user_id: int,
        request: CreateTaskRequestDto,
        on_chunk_received: Callable[[str], None]
 
    ) -> TaskDetailResponseDto:

        task = await self.create_task_async(user_id, request) # Images are not passed here from original C#
        if not task or not task.id: # Defensive check
            raise BusinessException("任务创建失败，未能获取任务ID")

        try:
            await self.process_task_async(task.id, on_chunk_received)
             # Removed cancellation_token
        except asyncio.CancelledError:
            self.logger.info(f"流式创建并处理任务被取消，任务ID：{task.id}")

        except Exception:
            print(f"流式创建并处理任务过程中发生错误，任务ID：{task.id}", exc_info=True)


        return await self.get_task_async(user_id, task.id)

    def _calculate_completion_rate(self, processed: int, total: int) -> float:
        if total <= 0:
            return 0.0
        return round((processed / total) * 100, 2)

    def _get_status_name(self, status_value: Optional[int]) -> str: # status_value can be int
        if status_value is None:
            return "UNKNOWN"
        try:
            return GenerationTaskStatus(status_value).name
        except ValueError:
            return "INVALID_STATUS"