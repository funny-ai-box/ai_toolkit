# app/modules/tools/social_content/repositories/platform_repository.py
from typing import List, Optional, Dict, Any, Tuple
import datetime
import logging
from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.utils.snowflake import generate_id
from app.modules.tools.social_content.models import Platform, PlatformTemplate, PlatformTemplateUser, PromptTypeEnum


class PlatformRepository:
    """平台仓储实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化平台仓储
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    async def get_all_platforms_async(self, active_only: bool = True) -> List[Platform]:
        """
        获取所有平台
        
        Args:
            active_only: 是否只获取启用的平台
            
        Returns:
            平台列表
        """
        try:
            query = select(Platform)
            
            if active_only:
                query = query.where(Platform.is_active == True)
            
            result = await self.db.execute(query.order_by(Platform.id))
            return list(result.scalars().all())
        except Exception as ex:
            self.logger.error(f"获取所有平台失败: {str(ex)}")
            raise
    
    async def get_platform_async(self, id: int) -> Optional[Platform]:
        """
        获取平台详情
        
        Args:
            id: 平台ID
            
        Returns:
            平台实体
        """
        try:
            query = select(Platform).where(Platform.id == id)
            result = await self.db.execute(query)
            return result.scalars().first()
        except Exception as ex:
            self.logger.error(f"获取平台详情失败，平台ID：{id}: {str(ex)}")
            raise
    
    async def get_platform_prompts_async(self, platform_id: int) -> List[PlatformTemplate]:
        """
        获取平台模板列表
        
        Args:
            platform_id: 平台ID
            
        Returns:
            模板列表
        """
        try:
            query = select(PlatformTemplate).where(
                PlatformTemplate.platform_id == platform_id
            ).order_by(PlatformTemplate.id)
            
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as ex:
            self.logger.error(f"获取平台模板列表失败，平台ID：{platform_id}: {str(ex)}")
            raise
    
    async def get_platform_prompt_async(self, id: int) -> Optional[PlatformTemplate]:
        """
        获取平台模板详情
        
        Args:
            id: 模板ID
            
        Returns:
            模板实体
        """
        try:
            query = select(PlatformTemplate).where(PlatformTemplate.id == id)
            result = await self.db.execute(query)
            return result.scalars().first()
        except Exception as ex:
            self.logger.error(f"获取平台模板详情失败，模板ID：{id}: {str(ex)}")
            raise
    
    async def get_user_prompts_async(self, user_id: int, platform_id: Optional[int] = None) -> List[PlatformTemplateUser]:
        """
        获取用户平台模板列表
        
        Args:
            user_id: 用户ID
            platform_id: 平台ID
            
        Returns:
            用户模板列表
        """
        try:
            query = select(PlatformTemplateUser).where(
                PlatformTemplateUser.user_id == user_id
            )
            
            if platform_id is not None:
                query = query.where(PlatformTemplateUser.platform_id == platform_id)
            
            query = query.order_by(PlatformTemplateUser.platform_id, PlatformTemplateUser.id)
            
            result = await self.db.execute(query)
            return list(result.scalars().all())
        except Exception as ex:
            self.logger.error(f"获取用户平台模板列表失败，用户ID：{user_id}: {str(ex)}")
            raise
    
    async def get_user_all_prompts_async(self, user_id: int, platform_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取用户自定义和系统预置的合体模板列表
        
        Args:
            user_id: 用户ID
            platform_id: 平台ID
            
        Returns:
            用户模板列表
        """
        try:
            # 系统的提示词模板
            system_query = select(PlatformTemplate)
            if platform_id is not None:
                system_query = system_query.where(PlatformTemplate.platform_id == platform_id)
            
            system_query = system_query.order_by(PlatformTemplate.platform_id, PlatformTemplate.id)
            system_result = await self.db.execute(system_query)
            system_prompts = list(system_result.scalars().all())
            
            # 用户自定义的提示词模板
            user_query = select(PlatformTemplateUser).where(
                PlatformTemplateUser.user_id == user_id
            )
            
            if platform_id is not None:
                user_query = user_query.where(PlatformTemplateUser.platform_id == platform_id)
            
            user_query = user_query.order_by(PlatformTemplateUser.platform_id, PlatformTemplateUser.id)
            user_result = await self.db.execute(user_query)
            user_prompts = list(user_result.scalars().all())
            
            result = []
            
            # 添加系统提示词
            for system_prompt in system_prompts:
                result.append({
                    "id": system_prompt.id,
                    "prompt_type": PromptTypeEnum.SYSTEM,
                    "platform_id": system_prompt.platform_id,
                    "template_name": system_prompt.template_name,
                    "template_content": system_prompt.template_content,
                    "system_prompt": system_prompt.system_prompt
                })
            
            # 添加用户自定义提示词
            for user_prompt in user_prompts:
                result.append({
                    "id": user_prompt.id,
                    "prompt_type": PromptTypeEnum.USER,
                    "platform_id": user_prompt.platform_id,
                    "template_name": user_prompt.template_name,
                    "template_content": user_prompt.template_content,
                    "system_prompt": user_prompt.system_prompt
                })
            
            return result
        except Exception as ex:
            self.logger.error(f"获取用户合体模板列表失败，用户ID：{user_id}: {str(ex)}")
            raise
    
    async def get_user_prompt_async(self, id: int) -> Optional[PlatformTemplateUser]:
        """
        获取用户平台模板详情
        
        Args:
            id: 用户模板ID
            
        Returns:
            用户模板实体
        """
        try:
            query = select(PlatformTemplateUser).where(PlatformTemplateUser.id == id)
            result = await self.db.execute(query)
            return result.scalars().first()
        except Exception as ex:
            self.logger.error(f"获取用户平台模板详情失败，模板ID：{id}: {str(ex)}")
            raise
    
    async def add_user_prompt_async(self, user_prompt: PlatformTemplateUser) -> int:
        """
        添加用户平台模板
        
        Args:
            user_prompt: 用户模板实体
            
        Returns:
            用户模板ID
        """
        try:
            user_prompt.id = generate_id()
            now = datetime.datetime.now()
            user_prompt.create_date = now
            user_prompt.last_modify_date = now
            
            self.db.add(user_prompt)
            await self.db.flush()
            
            return user_prompt.id
        except Exception as ex:
            self.logger.error(f"添加用户平台模板失败，用户ID：{user_prompt.user_id}, 平台ID：{user_prompt.platform_id}: {str(ex)}")
            raise
    
    async def update_user_prompt_async(self, user_prompt: PlatformTemplateUser) -> bool:
        """
        更新用户平台模板
        
        Args:
            user_prompt: 用户模板实体
            
        Returns:
            是否成功
        """
        try:
            user_prompt.last_modify_date = datetime.datetime.now()
            
            query = update(PlatformTemplateUser).where(
                PlatformTemplateUser.id == user_prompt.id
            ).values(
                template_name=user_prompt.template_name,
                template_content=user_prompt.template_content,
                system_prompt=user_prompt.system_prompt,
                last_modify_date=user_prompt.last_modify_date
            )
            
            result = await self.db.execute(query)
            return result.rowcount > 0
        except Exception as ex:
            self.logger.error(f"更新用户平台模板失败，模板ID：{user_prompt.id}: {str(ex)}")
            raise
    
    async def delete_user_prompt_async(self, id: int, user_id: int) -> bool:
        """
        删除用户平台模板
        
        Args:
            id: 用户模板ID
            user_id: 用户ID
            
        Returns:
            是否成功
        """
        try:
            query = delete(PlatformTemplateUser).where(
                and_(
                    PlatformTemplateUser.id == id,
                    PlatformTemplateUser.user_id == user_id
                )
            )
            
            result = await self.db.execute(query)
            return result.rowcount > 0
        except Exception as ex:
            self.logger.error(f"删除用户平台模板失败，模板ID：{id}, 用户ID：{user_id}: {str(ex)}")
            raise