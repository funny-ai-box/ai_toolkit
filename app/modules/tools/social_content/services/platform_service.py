# app/modules/tools/social_content/services/platform_service.py
from typing import List, Optional, Dict, Any
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException
from app.modules.tools.social_content.repositories.platform_repository import PlatformRepository
from app.modules.tools.social_content.models import Platform, PlatformTemplate, PlatformTemplateUser
from app.modules.tools.social_content.dtos.platform_dtos import (
    PlatformDto, PlatformPromptDto, UserPromptDto, 
    AddUserPromptRequestDto, UpdateUserPromptRequestDto
)


class PlatformService:
    """平台服务实现"""
    
    def __init__(self, db: AsyncSession):
        """
        初始化平台服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self.platform_repository = PlatformRepository(db)
        self.logger = logging.getLogger(__name__)
    
    async def get_all_platforms_async(self) -> List[PlatformDto]:
        """
        获取所有平台
        
        Returns:
            平台列表
        """
        try:
            platforms = await self.platform_repository.get_all_platforms_async()
            return [
                PlatformDto(
                    id=p.id,
                    name=p.name,
                    code=p.code,
                    icon=p.icon,
                    description=p.description
                )
                for p in platforms
            ]
        except Exception as ex:
            print(f"获取所有平台失败: {str(ex)}")
            raise
    
    async def get_platform_prompts_async(self, platform_id: int) -> List[PlatformPromptDto]:
        """
        获取平台模板列表
        
        Args:
            platform_id: 平台ID
            
        Returns:
            模板列表
        """
        try:
            prompts = await self.platform_repository.get_platform_prompts_async(platform_id)
            return [
                PlatformPromptDto(
                    id=p.id,
                    platformId=p.platform_id,
                    templateName=p.template_name,
                    templateContent=p.template_content,
                    systemPrompt=p.system_prompt
                )
                for p in prompts
            ]
        except Exception as ex:
            print(f"获取平台模板列表失败，平台ID：{platform_id}: {str(ex)}")
            raise
    
    async def get_user_prompts_async(self, user_id: int, platform_id: Optional[int] = None) -> List[UserPromptDto]:
        """
        获取用户平台模板列表
        
        Args:
            user_id: 用户ID
            platform_id: 平台ID
            
        Returns:
            用户模板列表
        """
        try:
            user_prompts = await self.platform_repository.get_user_prompts_async(user_id, platform_id)
            
            # 获取所有平台
            platforms = await self.platform_repository.get_all_platforms_async()
            platform_dict = {p.id: p.name for p in platforms}
            
            return [
                UserPromptDto(
                    id=p.id,
                    platformId=p.platform_id,
                    platformName=platform_dict.get(p.platform_id, "未知平台"),
                    templateName=p.template_name,
                    templateContent=p.template_content,
                    systemPrompt=p.system_prompt,
                    createDate=p.create_date
                )
                for p in user_prompts
            ]
        except Exception as ex:
            print(f"获取用户平台模板列表失败，用户ID：{user_id}: {str(ex)}")
            raise
    
    async def get_user_prompt_async(self, user_id: int, prompt_id: int) -> UserPromptDto:
        """
        获取用户模板详情
        
        Args:
            user_id: 用户ID
            prompt_id: 模板ID
            
        Returns:
            用户模板详情
        """
        try:
            prompt = await self.platform_repository.get_user_prompt_async(prompt_id)
            
            if not prompt or prompt.user_id != user_id:
                raise BusinessException("模板不存在或无权限访问")
            
            # 获取平台
            platform = await self.platform_repository.get_platform_async(prompt.platform_id)
            
            return UserPromptDto(
                id=prompt.id,
                platformId=prompt.platform_id,
                platformName=platform.name if platform else "未知平台",
                templateName=prompt.template_name,
                templateContent=prompt.template_content,
                systemPrompt=prompt.system_prompt,
                createDate=prompt.create_date
            )
        except BusinessException:
            raise
        except Exception as ex:
            print(f"获取用户模板详情失败，用户ID：{user_id}, 模板ID：{prompt_id}: {str(ex)}")
            raise
    
    async def add_user_prompt_async(self, user_id: int, request: AddUserPromptRequestDto) -> int:
        """
        添加用户模板
        
        Args:
            user_id: 用户ID
            request: 添加请求
            
        Returns:
            模板ID
        """
        try:
            # 验证平台是否存在
            platform = await self.platform_repository.get_platform_async(request.platform_id)
            if not platform:
                raise BusinessException("平台不存在")
            
            user_prompt = PlatformTemplateUser(
                user_id=user_id,
                platform_id=request.platform_id,
                template_name=request.template_name,
                template_content=request.template_content,
                system_prompt=request.system_prompt
            )
            
            prompt_id = await self.platform_repository.add_user_prompt_async(user_prompt)
            await self.db.commit()  # 添加显式提交 - 确保repository中的操作被提交
            return prompt_id
        except BusinessException:
            raise
        except Exception as ex:
            print(f"添加用户模板失败，用户ID：{user_id}: {str(ex)}")
            raise
    
    async def update_user_prompt_async(self, user_id: int, request: UpdateUserPromptRequestDto) -> bool:
        """
        更新用户模板
        
        Args:
            user_id: 用户ID
            request: 更新请求
            
        Returns:
            是否成功
        """
        try:
            # 检查模板是否存在并属于该用户
            existing_prompt = await self.platform_repository.get_user_prompt_async(request.id)
            if not existing_prompt or existing_prompt.user_id != user_id:
                raise BusinessException("模板不存在或无权限修改")
            
            existing_prompt.template_name = request.template_name
            existing_prompt.template_content = request.template_content
            existing_prompt.system_prompt = request.system_prompt
            
            result = await self.platform_repository.update_user_prompt_async(existing_prompt)
            await self.db.commit()  # 添加显式提交 - 确保repository中的操作被提交
            return result
        except BusinessException:
            raise
        except Exception as ex:
            print(f"更新用户模板失败，用户ID：{user_id}, 模板ID：{request.id}: {str(ex)}")
            raise
    
    async def delete_user_prompt_async(self, user_id: int, prompt_id: int) -> bool:
        """
        删除用户模板
        
        Args:
            user_id: 用户ID
            prompt_id: 模板ID
            
        Returns:
            是否成功
        """
        try:
            result = await self.platform_repository.delete_user_prompt_async(prompt_id, user_id)
            await self.db.commit()  # 添加显式提交 - 确保repository中的操作被提交
            return result
        except Exception as ex:
            print(f"删除用户模板失败，用户ID：{user_id}, 模板ID：{prompt_id}: {str(ex)}")
            raise