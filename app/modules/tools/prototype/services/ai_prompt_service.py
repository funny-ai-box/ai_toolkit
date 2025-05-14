# app/modules/tools/prototype/services/ai_prompt_service.py
from app.modules.base.prompts.services import PromptTemplateService


class AIPromptService:
    """AI 提示词服务"""
    
    def __init__(self, prompt_template_service: PromptTemplateService):
        """
        初始化 AI 提示词服务
        
        Args:
            prompt_template_service: 提示词模板服务
        """
        self.prompt_template_service = prompt_template_service
    
    async def global_system_prompt(self) -> str:
        """
        全局系统指令，定义AI的行为和流程
        
        Returns:
            系统提示词
        """
        return await self.prompt_template_service.get_content_by_key_async("PROTOTYPE_GLOBAL_FLOW_PROMPT")
    
    async def collecting_prompt(self) -> str:
        """
        需求收集阶段的提示词
        
        Returns:
            阶段提示词
        """
        return await self.prompt_template_service.get_content_by_key_async("PROTOTYPE_COLLECTING_PROMPT")
    
    async def analyzing_prompt(self) -> str:
        """
        需求分析阶段的提示词
        
        Returns:
            阶段提示词
        """
        return await self.prompt_template_service.get_content_by_key_async("PROTOTYPE_ANALYZING_PROMPT")
    
    async def designing_prompt(self) -> str:
        """
        页面结构设计阶段的提示词
        
        Returns:
            阶段提示词
        """
        return await self.prompt_template_service.get_content_by_key_async("PROTOTYPE_DESIGNING_PROMPT")
    
    async def generating_prompt_template(self) -> str:
        """
        页面生成阶段的提示词模板
        
        Returns:
            提示词模板
        """
        return await self.prompt_template_service.get_content_by_key_async("PROTOTYPE_GENERATING_PROMPT")
    
    async def editing_prompt_template(self) -> str:
        """
        修改与优化阶段的提示词模板
        
        Returns:
            提示词模板
        """
        return await self.prompt_template_service.get_content_by_key_async("PROTOTYPE_EDITING_PROMPT")
    
    async def completed_prompt(self) -> str:
        """
        完成阶段的提示词
        
        Returns:
            阶段提示词
        """
        return await self.prompt_template_service.get_content_by_key_async("PROTOTYPE_COMPLETED_PROMPT")