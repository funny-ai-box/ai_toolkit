"""
AI 生成面试问题服务实现

基于AI能力自动生成面试问题，根据场景和职位信息，分析文档内容，生成适合的面试问题。
"""
import json
from typing import List, Tuple, Optional, Dict, Any
import logging
from datetime import datetime

from app.core.ai.chat.base import IChatAIService
from app.core.ai.chat.factory import get_chat_ai_service

from app.core.config.settings import Settings
from app.modules.base.prompts.services import PromptTemplateService
from app.modules.tools.interview.models import InterviewScenario, JobPosition
from app.modules.tools.interview.dtos import AIQuestionResponseDto


class AIQuestionService:
    """AI 生成面试问题服务"""
    
    def __init__(
        self,
        settings: Settings,
        logger: logging.Logger,
        prompt_template_service: PromptTemplateService,
        ai_service: IChatAIService
    ):
        """
        初始化 AI 生成面试问题服务
        
        Args:
            settings: 应用配置
            logger: 日志记录器
            prompt_template_service: 提示词模板服务
            ai_service: AI聊天服务
        """
        self.settings = settings
        self.logger = logger
        self.prompt_template_service = prompt_template_service
        self.ai_service = ai_service
    
    async def generate_questions_for_position(
        self,
        scenario: InterviewScenario,
        position: JobPosition,
        document_content: str
    ) -> Tuple[bool, str, Optional[List[AIQuestionResponseDto]]]:
        """
        为特定职位生成面试问题
        
        Args:
            scenario: 场景
            position: 职位
            document_content: 文档内容
            
        Returns:
            操作结果
        """
        try:
            # 获取系统提示词模板
            system_prompt = await self.prompt_template_service.get_content_by_key_async("INTERVIEW_QUESTION_GENERATION_PROMPT")
            system_prompt = system_prompt.replace("{scenario.Name}", scenario.name)
            system_prompt = system_prompt.replace("{position.Name}", position.name)
            system_prompt = system_prompt.replace("{position.Level}", position.level.name)
            
            # 构建文档提示词
            user_prompt = f"""相关文档内容：
--- begin 文档内容
{document_content}
--- end 文档内容"""
            
            # 调用AI服务生成问题
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await self.ai_service.chat_completion_async(messages)
            
            try:
                # 解析JSON响应
                ai_questions = json.loads(response)
                # 转换为DTO对象
                questions = []
                for q in ai_questions:
                    questions.append(AIQuestionResponseDto(
                        type=q.get("type"),
                        difficulty=q.get("difficulty"),
                        content=q.get("content"),
                        answer=q.get("answer"),
                        sort_order=q.get("sortOrder", 0)
                    ))
                return True, "", questions
            except json.JSONDecodeError as e:
                print(f"解析AI响应失败: {e}")
                return False, f"解析AI响应失败: {str(e)}", None
            
        except Exception as e:
            error_msg = f"为职位 {position.name} 生成面试问题时发生错误: {str(e)}"
            print(error_msg)
            return False, error_msg, None