"""
AI提示词服务，用于获取预定义的系统提示词
"""
from app.modules.base.prompts.services import PromptTemplateService


class AIPromptService:
    """AI提示词服务"""
    
    @staticmethod
    async def global_system_prompt() -> str:
        """
        全局系统指令，定义AI的行为和流程
        
        Returns:
            系统提示词
        """
        return await PromptTemplateService.get_content_by_key_async("PROTOTYPE_GLOBAL_FLOW_PROMPT")
    
    @staticmethod
    async def collecting_prompt() -> str:
        """
        需求收集阶段的提示词
        
        Returns:
            系统提示词
        """
        return await PromptTemplateService.get_content_by_key_async("PROTOTYPE_COLLECTING_PROMPT")
    
    @staticmethod
    async def analyzing_prompt() -> str:
        """
        需求分析阶段的提示词
        
        Returns:
            系统提示词
        """
        return await PromptTemplateService.get_content_by_key_async("PROTOTYPE_ANALYZING_PROMPT")
    
    @staticmethod
    async def designing_prompt() -> str:
        """
        页面结构设计阶段的提示词
        
        Returns:
            系统提示词
        """
        return await PromptTemplateService.get_content_by_key_async("PROTOTYPE_DESIGNING_PROMPT")
    
    @staticmethod
    async def generating_prompt_template() -> str:
        """
        页面生成阶段的提示词模板
        
        Returns:
            系统提示词模板
        """
        return await PromptTemplateService.get_content_by_key_async("PROTOTYPE_GENERATING_PROMPT")
    
    @staticmethod
    async def editing_prompt_template() -> str:
        """
        修改与优化阶段的提示词模板
        
        Returns:
            系统提示词模板
        """
        return await PromptTemplateService.get_content_by_key_async("PROTOTYPE_EDITING_PROMPT")
    
    @staticmethod
    async def completed_prompt() -> str:
        """
        完成阶段的提示词
        
        Returns:
            系统提示词
        """
        return await PromptTemplateService.get_content_by_key_async("PROTOTYPE_COMPLETED_PROMPT")