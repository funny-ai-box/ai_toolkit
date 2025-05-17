from typing import List, Optional, Dict, Any, Callable
import logging
from datetime import datetime
import asyncio # Keep asyncio import
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai.chat.base import IChatAIService
from app.core.ai.vector.base import IUserDocsMilvusService # Assuming this exists
from app.core.storage.base import IStorageService # Assuming this exists
from app.core.config.settings import settings
from app.core.exceptions import BusinessException
from app.modules.tools.social_content.repositories.platform_repository import PlatformRepository
from app.modules.tools.social_content.repositories.task_repository import TaskRepository
from app.modules.tools.social_content.models import (
    Platform, GenerationTask, GenerationTaskPlatform,
    GenerationTaskImage, GeneratedContent
)
from app.core.dtos import DocumentAppType # Assuming this exists


class AIGenerateService:
    """AI 服务实现"""

    def __init__(
        self,
        db: AsyncSession,
        ai_service: IChatAIService,
        platform_repository: PlatformRepository,
        task_repository: TaskRepository,
        user_docs_service: IUserDocsMilvusService,
        task_img_storage_service: IStorageService
    ):
        self.db = db
        self.ai_service = ai_service
        self.platform_repository = platform_repository
        self.task_repository = task_repository
        self.user_docs_service = user_docs_service
        self.task_img_storage_service = task_img_storage_service
        self.logger = logging.getLogger(__name__)
        self.sensitive_categories = settings.SOCIAL_CONTENT_SENSITIVE_CATEGORIES
        self.search_top_k = 5

    async def generate_platform_contents_async(
        self,
        task: GenerationTask,
        task_platform: GenerationTaskPlatform,
        task_images: List[GenerationTaskImage],
        related_contents: List[str],
        on_chunk_received: Optional[Callable[[str], None]] = None
        # Removed cancellation_token: Optional[asyncio.CancelToken] = None
    ) -> List[GeneratedContent]:
        """
        为平台生成内容

        Args:
            task: 任务
            task_platform: 任务平台
            task_images: 任务图片列表
            related_contents: 相关内容
            on_chunk_received: 接收到数据块时的回调函数

        Returns:
            生成内容列表
        """
        try:
            platform = await self.platform_repository.get_platform_async(task_platform.platform_id)
            if not platform:
                raise BusinessException(f"平台不存在: {task_platform.platform_id}")

            if not task_platform.template_content:
                raise BusinessException(f"平台模板为空: {task_platform.platform_id}")

            prompt = self._replace_template_variables(task_platform.template_content, task, task_images, platform)

            context = ""
            if related_contents:
                context = "以下是一些相关参考内容，你可以借鉴它们的风格和表达方式：\n\n"
                context += "\n\n---\n\n".join(related_contents)

            generated_contents_list = [] # Renamed to avoid conflict

            for i in range(task_platform.content_count):
                messages = []
                sensitive_prompt = f"\n请确保生成的内容不能包含如下内容或敏感信息：{self.sensitive_categories}等内容。"
                if task_platform.system_prompt:
                    messages.append({
                        "role": "system",
                        "content": task_platform.system_prompt + sensitive_prompt
                    })
                else:
                    messages.append({
                        "role": "system",
                        "content": f"你是一个专业的{platform.name}社交平台内容创作专家，擅长创作高质量、吸引人的{platform.name}内容。" + sensitive_prompt
                    })

                if context:
                    messages.append({"role": "user", "content": context})
                    messages.append({
                        "role": "assistant",
                        "content": "我已了解这些参考内容，会借鉴它们的风格和表达方式来创作。"
                    })

                messages.append({
                    "role": "user",
                    "content": f"请为{platform.name}平台创作第 {i + 1} 个内容:\n\n{prompt}"
                })

                content_str = "" # Renamed to avoid conflict
                if not on_chunk_received:
                    content_str = await self.ai_service.chat_completion_async(messages)
                else:
                    on_chunk_received(f"---开始生成第 {i + 1} 个内容---\n\n")
                    content_chunks = []
                    try:
                        async for chunk in self.ai_service.streaming_chat_completion_async(messages):
                            content_chunks.append(chunk)
                            on_chunk_received(chunk)
                    except asyncio.CancelledError:
                        self.logger.info(f"内容生成任务 (平台ID: {task_platform.platform_id}, 索引: {i+1}) 被取消。")
                        # Decide how to handle partial generation:
                        # Option 1: Stop and return what's generated so far (if any)
                        # Option 2: Raise CancelledError to propagate
                        # Option 3: Log and continue to next content item if applicable
                        # For now, we'll let it break out of this specific content item's loop
                        break # Break from async for chunk loop
                    content_str = "".join(content_chunks)
                
                if not content_str and (not on_chunk_received or (on_chunk_received and not content_chunks)): # if content is empty and not due to cancellation handled above
                    self.logger.warning(f"AI未返回内容，任务ID：{task.id}, 平台ID：{task_platform.platform_id}, 索引：{i+1}")
                    # Optionally, add a placeholder or skip this content item
                    # For now, we skip adding an empty content
                    continue


                generated_content_item = GeneratedContent( # Renamed to avoid conflict
                    task_id=task.id,
                    task_platform_id=task_platform.id,
                    platform_id=platform.id,
                    content_index=i + 1,
                    content=content_str
                )
                generated_contents_list.append(generated_content_item)
            
            return generated_contents_list
        except asyncio.CancelledError:
            self.logger.info(f"为平台生成内容任务被取消，任务ID：{task.id}, 平台ID：{task_platform.platform_id}")
            raise # Re-raise so the caller (e.g., job endpoint) can handle it
        except Exception as ex:
            print(f"为平台生成内容失败，任务ID：{task.id}, 平台ID：{task_platform.platform_id}: {str(ex)}", exc_info=True)
            raise

    async def generate_images_desc_async(self, task_images: List[GenerationTaskImage]) -> None:
        if not task_images:
            return

        for image in task_images:
            try:
                if not image.image_path:
                    continue

                image_url = image.image_path
                if not image_url.startswith("http"):
                    image_url = self.task_img_storage_service.get_url(image_url)

                messages = [
                    {
                        "role": "system",
                        "content": "请对提供的图片进行详细描述，包括图片中的主要内容、物品、人物、场景、色彩等。描述要全面但简洁，不要超过200字。"
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"图片编号：{image.id}"},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]
                    }
                ]
                description = await self.ai_service.chat_completion_async(messages)
                await self.task_repository.update_task_image_description_async(image.id, description)
                image.image_description = description
            except asyncio.CancelledError:
                self.logger.info(f"图片描述生成任务被取消，图片ID：{image.id}")
                # If one image description is cancelled, decide if to continue with others
                # For now, let it propagate if the whole generate_images_desc_async is cancelled
                raise
            except Exception as ex:
                print(f"处理任务图片失败，图片ID：{image.id}: {str(ex)}", exc_info=True)
                await self.task_repository.update_task_image_description_async(image.id, "图片描述生成失败")

    async def search_related_contents_async(
        self, task: GenerationTask, task_images: List[GenerationTaskImage]
    ) -> List[str]:
        related_contents = []
        try:
            query_text_parts = [] # Renamed to avoid conflict
            if task.keywords:
                query_text_parts.append(f"关键词: {task.keywords}")
            if task.product_info:
                query_text_parts.append(f"商品信息: {task.product_info}")
            if task_images:
                for image in task_images:
                    if image.image_description:
                        query_text_parts.append(f"图片描述: {image.image_description}")
            
            query_text_str = "\n".join(query_text_parts)
            if not query_text_str:
                self.logger.warning("查询文本为空，无法搜索相关内容")
                return related_contents

            query_vector = await self.ai_service.get_embedding_async(query_text_str)
            search_results = await self.user_docs_service.search_async(
                task.user_id,
                DocumentAppType.SOCIAL_CONTENT, # Ensure this enum value exists
                query_vector,
                None,
                self.search_top_k
            )
            for result in search_results:
                if result.content:
                    related_contents.append(result.content)
        except asyncio.CancelledError:
            self.logger.info(f"相关内容搜索任务被取消，任务ID：{task.id}")
            raise
        except Exception as ex:
            print(f"搜索相关内容失败，任务ID：{task.id}: {str(ex)}", exc_info=True)
        return related_contents

    def _replace_template_variables(
        self,
        template: str,
        task: GenerationTask,
        task_images: List[GenerationTaskImage],
        platform: Platform
    ) -> str:
        template = template.replace("{{平台名称}}", platform.name or "")
        template = template.replace("{{平台代码}}", platform.code or "")
        template = template.replace("{{任务名称}}", task.task_name or "")
        template = template.replace("{{关键词}}", task.keywords or "")
        template = template.replace("{{商品信息}}", task.product_info or "")

        if task_images:
            image_descriptions = [f"图片{i + 1}描述: {image.image_description or ''}" for i, image in enumerate(task_images)]
            template = template.replace("{{图片描述}}", "\n".join(image_descriptions))
            for i, image in enumerate(task_images):
                template = template.replace(f"{{{{图片{i + 1}描述}}}}", image.image_description or "")
        else:
            template = template.replace("{{图片描述}}", "")
        template = template.replace("{{今天日期}}", datetime.now().strftime("%Y-%m-%d"))
        return template