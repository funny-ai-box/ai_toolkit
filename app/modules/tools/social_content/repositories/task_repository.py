# app/modules/tools/social_content/repositories/task_repository.py
from typing import List, Optional, Dict, Any, Tuple
import datetime
import logging
from sqlalchemy import select, update, delete, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.snowflake import generate_id
from app.modules.tools.social_content.models import (
    GenerationTask, GenerationTaskPlatform, GenerationTaskImage, 
    GeneratedContent, GenerationTaskStatus
)


class TaskRepository:
    """任务仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化任务仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    async def create_task_async(self, task: GenerationTask) -> int:
        """
        创建生成任务
        
        Args:
            task: 任务实体
            
        Returns:
            任务ID
        """
        try:
            task.id = generate_id()
            task.status = int(GenerationTaskStatus.PENDING)
            task.completion_rate = 0
            now = datetime.datetime.now()
            task.create_date = now
            task.last_modify_date = now
            
            self.db.add(task)
            await self.db.flush()
            await self.db.commit()  # 添加显式提交
            
            return task.id
        except Exception as ex:
            print(f"创建生成任务失败: {str(ex)}")
            raise
    
    async def update_task_status_async(
        self, id: int, status: int, message: Optional[str] = None, completion_rate: Optional[float] = None
    ) -> bool:
        """
        更新任务状态
        
        Args:
            id: 任务ID
            status: 状态
            message: 处理消息
            completion_rate: 完成率
            
        Returns:
            是否成功
        """
        try:
            # 基本状态更新
            update_values = {
                "status": status,
                "last_modify_date": datetime.datetime.now()
            }
            
            # 如果有消息，添加到更新字段
            if message is not None:
                update_values["process_message"] = message
            
            # 如果有完成率，添加到更新字段
            if completion_rate is not None:
                update_values["completion_rate"] = completion_rate
            
            query = update(GenerationTask).where(
                GenerationTask.id == id
            ).values(**update_values)
            
            result = await self.db.execute(query)
            await self.db.commit()  # 添加显式提交
            return result.rowcount > 0
        except Exception as ex:
            print(f"更新任务状态失败，任务ID：{id}: {str(ex)}")
            raise
    
    async def get_task_async(self, id: int) -> Optional[GenerationTask]:
        """
        获取任务详情
        
        Args:
            id: 任务ID
            
        Returns:
            任务实体
        """
        try:
            query = select(GenerationTask).where(GenerationTask.id == id)
            result = await self.db.execute(query)
            return result.scalars().first()
        except Exception as ex:
            print(f"获取任务详情失败，任务ID：{id}: {str(ex)}")
            raise
    
    async def get_user_tasks_async(
        self, user_id: int, page_index: int = 1, page_size: int = 20
    ) -> Tuple[List[GenerationTask], int]:
        """
        获取用户任务列表
        
        Args:
            user_id: 用户ID
            page_index: 页码
            page_size: 每页大小
            
        Returns:
            任务列表和总数
        """
        try:
            # 确保页码和每页数量有效
            if page_index < 1:
                page_index = 1
            if page_size < 1:
                page_size = 20
            
            # 计算跳过的记录数
            skip = (page_index - 1) * page_size
            
            # 查询满足条件的记录总数
            count_query = select(func.count()).select_from(GenerationTask).where(
                GenerationTask.user_id == user_id
            )
            total_count_result = await self.db.execute(count_query)
            total_count = total_count_result.scalar()
            
            # 查询分页数据
            query = select(GenerationTask).where(
                GenerationTask.user_id == user_id
            ).order_by(
                GenerationTask.id.desc()
            ).offset(skip).limit(page_size)
            
            result = await self.db.execute(query)
            items = list(result.scalars().all())
            
            return items, total_count
        except Exception as ex:
            print(f"获取用户任务列表失败，用户ID：{user_id}: {str(ex)}")
            raise
    
    async def get_pending_tasks_async(self, limit: int = 10) -> List[GenerationTask]:
        """
        获取待处理任务列表
        
        Args:
            limit: 限制数量
            
        Returns:
            任务列表
        """
        try:
            query = select(GenerationTask).where(
                GenerationTask.status == GenerationTaskStatus.PENDING
            ).order_by(
                GenerationTask.create_date
            ).limit(limit)
            
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as ex:
            print(f"获取待处理任务列表失败: {str(ex)}")
            raise
    
    async def add_task_platform_async(self, task_platform: GenerationTaskPlatform) -> int:
        """
        添加任务平台
        
        Args:
            task_platform: 任务平台实体
            
        Returns:
            任务平台ID
        """
        try:
            task_platform.id = generate_id()
            task_platform.status = int(GenerationTaskStatus.PENDING)
            now = datetime.datetime.now()
            task_platform.create_date = now
            task_platform.last_modify_date = now
            
            self.db.add(task_platform)
            await self.db.flush()
            await self.db.commit()  # 添加显式提交
            
            return task_platform.id
        except Exception as ex:
            print(f"添加任务平台失败，任务ID：{task_platform.task_id}, 平台ID：{task_platform.platform_id}: {str(ex)}")
            raise
    
    async def update_task_platform_status_async(self, id: int, status: int) -> bool:
        """
        更新任务平台状态
        
        Args:
            id: 任务平台ID
            status: 状态
            
        Returns:
            是否成功
        """
        try:
            query = update(GenerationTaskPlatform).where(
                GenerationTaskPlatform.id == id
            ).values(
                status=int(status),
                last_modify_date=datetime.datetime.now()
            )
            
            result = await self.db.execute(query)
            await self.db.commit()  # 添加显式提交
            return result.rowcount > 0
        except Exception as ex:
            print(f"更新任务平台状态失败，任务平台ID：{id}: {str(ex)}")
            raise
    
    async def get_task_platforms_async(self, task_id: int) -> List[GenerationTaskPlatform]:
        """
        获取任务平台列表
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务平台列表
        """
        try:
            query = select(GenerationTaskPlatform).where(
                GenerationTaskPlatform.task_id == task_id
            )
            
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as ex:
            print(f"获取任务平台列表失败，任务ID：{task_id}: {str(ex)}")
            raise
    
    async def add_task_image_async(self, task_image: GenerationTaskImage) -> int:
        """
        添加任务图片
        
        Args:
            task_image: 任务图片实体
            
        Returns:
            任务图片ID
        """
        try:
            task_image.id = generate_id()
            now = datetime.datetime.now()
            task_image.create_date = now
            task_image.last_modify_date = now
            
            self.db.add(task_image)
            await self.db.flush()
            await self.db.commit()  # 添加显式提交
            
            return task_image.id
        except Exception as ex:
            print(f"添加任务图片失败，任务ID：{task_image.task_id}: {str(ex)}")
            raise
    
    async def update_task_image_description_async(self, id: int, description: str) -> bool:
        """
        更新任务图片描述
        
        Args:
            id: 任务图片ID
            description: 图片描述
            
        Returns:
            是否成功
        """
        try:
            query = update(GenerationTaskImage).where(
                GenerationTaskImage.id == id
            ).values(
                image_description=description,
                last_modify_date=datetime.datetime.now()
            )
            
            result = await self.db.execute(query)
            await self.db.commit()  # 添加显式提交
            return result.rowcount > 0
        except Exception as ex:
            print(f"更新任务图片描述失败，任务图片ID：{id}: {str(ex)}")
            raise
    
    async def get_task_images_async(self, task_id: int) -> List[GenerationTaskImage]:
        """
        获取任务图片列表
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务图片列表
        """
        try:
            query = select(GenerationTaskImage).where(
                GenerationTaskImage.task_id == task_id
            )
            
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as ex:
            print(f"获取任务图片列表失败，任务ID：{task_id}: {str(ex)}")
            raise
    
    async def add_generated_content_async(self, generated_content: GeneratedContent) -> int:
        """
        添加生成内容
        
        Args:
            generated_content: 生成内容实体
            
        Returns:
            生成内容ID
        """
        try:
            generated_content.id = generate_id()
            now = datetime.datetime.now()
            generated_content.create_date = now
            generated_content.last_modify_date = now
            
            self.db.add(generated_content)
            await self.db.flush()
            await self.db.commit()  # 添加显式提交
            
            return generated_content.id
        except Exception as ex:
            print(f"添加生成内容失败，任务ID：{generated_content.task_id}, 平台ID：{generated_content.platform_id}: {str(ex)}")
            raise
    
    async def add_generated_contents_async(self, generated_contents: List[GeneratedContent]) -> bool:
        """
        批量添加生成内容
        
        Args:
            generated_contents: 生成内容实体列表
            
        Returns:
            是否成功
        """
        try:
            if not generated_contents:
                return True
            
            now = datetime.datetime.now()
            for content in generated_contents:
                content.id = generate_id()
                content.create_date = now
                content.last_modify_date = now
                self.db.add(content)
            
            await self.db.flush()
            await self.db.commit()  # 添加显式提交
            return True
        except Exception as ex:
            print(f"批量添加生成内容失败: {str(ex)}")
            raise
    
    async def get_task_generated_contents_async(self, task_id: int) -> List[GeneratedContent]:
        """
        获取任务生成内容列表
        
        Args:
            task_id: 任务ID
            
        Returns:
            生成内容列表
        """
        try:
            query = select(GeneratedContent).where(
                GeneratedContent.task_id == task_id
            ).order_by(
                GeneratedContent.platform_id,
                GeneratedContent.content_index
            )
            
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as ex:
            print(f"获取任务生成内容列表失败，任务ID：{task_id}: {str(ex)}")
            raise
    
    async def get_task_platform_generated_contents_async(self, task_platform_id: int) -> List[GeneratedContent]:
        """
        获取任务平台生成内容列表
        
        Args:
            task_platform_id: 任务平台ID
            
        Returns:
            生成内容列表
        """
        try:
            query = select(GeneratedContent).where(
                GeneratedContent.task_platform_id == task_platform_id
            ).order_by(
                GeneratedContent.content_index
            )
            
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as ex:
            print(f"获取任务平台生成内容列表失败，任务平台ID：{task_platform_id}: {str(ex)}")
            raise