"""
AI 评估面试结果服务实现

基于AI能力评估面试回答，计算分数并给出评价，最终生成总体面试评估。
"""
import json
from typing import List, Tuple, Optional, Dict, Any
import logging
from datetime import datetime

from app.core.ai.chat.base import IChatAIService
from app.core.ai.chat.factory import get_chat_ai_service

from app.core.config.settings import Settings
from app.modules.base.prompts.services import PromptTemplateService
from app.modules.tools.interview.models import InterviewInteraction, JobPosition
from app.modules.tools.interview.enums import QuestionDifficulty


class AIEvaluateAnswerService:
    """AI 评估面试结果服务"""
    
    def __init__(
        self,
        settings: Settings,
        logger: logging.Logger,
        prompt_template_service: PromptTemplateService,
        ai_service: IChatAIService
    ):
        """
        初始化 AI 评估面试结果服务
        
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
    
    async def evaluate_answer(
        self,
        question: str,
        answer: str,
        standard_answer: str,
        position_level: QuestionDifficulty
    ) -> Tuple[bool, int, Optional[str]]:
        """
        评估单个回答
        
        Args:
            question: 问题
            answer: 回答
            standard_answer: 标准答案
            position_level: 职位级别
            
        Returns:
            评分和评语
        """
        try:
            # 获取系统提示词模板
            system_prompt = await self.prompt_template_service.get_content_by_key_async("INTERVIEW_EVALUATE_ANSWER_PROMPT")
            
            # 构建评估提示词
            user_prompt = f"""请根据以下信息评估候选人的回答：

职位级别：{position_level.name}

问题：{question}

候选人回答：{answer}
"""
            
            if standard_answer:
                user_prompt += f"\n标准参考答案：{standard_answer}"
            
            # 调用AI进行评估
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await self.ai_service.chat_completion_async(messages)
            
            try:
                # 解析JSON响应
                result = json.loads(response)
                score = result.get("score", 0)
                evaluation = result.get("evaluation", "")
                return True, score, evaluation
            except json.JSONDecodeError as e:
                print(f"解析AI响应失败: {e}")
                return False, 0, f"评估过程中发生错误: 无法解析结果 - {str(e)}"
            
        except Exception as e:
            error_msg = f"评估答案时发生错误: {str(e)}"
            print(error_msg, exc_info=True)
            return False, 0, error_msg
    
    async def generate_overall_evaluation(self, interactions: List[InterviewInteraction], position: JobPosition) -> str:
        """
        生成总体评估
        
        Args:
            interactions: 交互记录列表
            position: 职位
            
        Returns:
            总体评估
        """
        try:
            # 构建总结内容
            summary = "面试问答记录：\n\n"
            
            for interaction in interactions:
                summary += f"问题 {interaction.interaction_order}：{interaction.question}\n"
                summary += f"回答：{interaction.answer}\n"
                if interaction.score is not None:
                    summary += f"得分：{interaction.score}\n"
                if interaction.evaluation:
                    summary += f"评价：{interaction.evaluation}\n"
                summary += "\n"
            
            # 获取系统提示词模板
            system_prompt = await self.prompt_template_service.get_content_by_key_async("INTERVIEW_EVALUATE_OVERALL_PROMPT")
            
            # 构建提示词
            user_prompt = f"""请基于以下面试记录，提供详细的总体评估：

职位：{position.name}
职位级别：{position.level.name}

{summary}"""
            
            # 调用AI进行评估
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = await self.ai_service.chat_completion_async(messages)
            
            return response
            
        except Exception as e:
            error_msg = f"生成总体评估时发生错误: {str(e)}"
            print(error_msg, exc_info=True)
            return "无法生成总体评估，请稍后再试。"