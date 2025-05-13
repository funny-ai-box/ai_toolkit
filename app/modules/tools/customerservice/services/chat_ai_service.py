"""
客服AI服务实现
"""
import json
import logging
from typing import List, Optional, Dict, Any, AsyncGenerator

from app.core.ai.chat.base import IChatAIService
from app.core.ai.dtos import ChatRoleType, InputMessage
from app.modules.base.prompts.services import PromptTemplateService
from app.modules.tools.customerservice.dtos import IntentRecognitionResultDto, ImageAnalysisResultDto

logger = logging.getLogger(__name__)


class ChatAIService:
    """AI服务类"""

    def __init__(
        self, 
        ai_service: IChatAIService, 
        prompt_template_service: PromptTemplateService,
        sensitive_words: str
    ):
        """
        初始化AI服务类
        
        Args:
            ai_service: AI服务
            prompt_template_service: 提示词模板服务
            sensitive_words: 敏感词
        """
        self.ai_service = ai_service
        self.prompt_template_service = prompt_template_service
        self.sensitive_words = sensitive_words

    async def get_embedding_async(self, text: str) -> List[float]:
        """
        获取文本嵌入
        
        Args:
            text: 文本
            
        Returns:
            嵌入向量
        """
        return await self.ai_service.get_embedding_async(text)

    async def analysis_intent_async(
        self, 
        user_id: int, 
        history: List[Dict[str, Any]], 
        message: str
    ) -> IntentRecognitionResultDto:
        """
        根据会话上下文分析用户意图
        
        Args:
            user_id: 用户ID
            history: 会话上下文
            message: 用户消息
            
        Returns:
            意图识别结果
        """
        try:
            # 构建消息列表
            messages = []
            
            # 添加意图分析的提示词
            system_prompt = await self.prompt_template_service.get_content_by_key_async("CUSTOMERSERVICE_ANALYSISINTENT_PROMPT")
            messages.append(InputMessage(role=ChatRoleType.SYSTEM, content=system_prompt))
            messages.append(InputMessage(role=ChatRoleType.SYSTEM, content=f"敏感词包括：{self.sensitive_words}"))
            
            # 添加历史记录，帮助AI更好地理解上下文
            if history and len(history) > 0:
                history_content = "###下面是对话历史信息\n"
                
                for item in history:
                    if item['role'] == ChatRoleType.USER:
                        history_content += f"用户:{item['content']}\n"
                    elif item['role'] == ChatRoleType.ASSISTANT:
                        msg = f"客服:{item['content']}"
                        if item.get('intent') and item.get('callDatas'):
                            msg += f" [此回复通过工具查询，涉及的实体ID: {item['callDatas']}]"
                        history_content += msg + "\n"
                
                messages.append(InputMessage(role=ChatRoleType.USER, content=history_content))
            
            # 添加当前问题
            messages.append(InputMessage(role=ChatRoleType.USER, content=f"###用户当前问题：{message}"))
            
            # 调用AI服务
            response = await self.ai_service.chat_completion_async(messages)
            
            # 解析结果
            try:
                result_dto = IntentRecognitionResultDto(**json.loads(response))
                return result_dto
            except Exception as ex:
                logger.error(f"解析意图识别结果JSON失败: {response}", exc_info=ex)
                
                # 如果解析失败，返回一个默认的结果
                return IntentRecognitionResultDto(
                    intent="GENERAL_QUERY",
                    context="",
                    id_datas=None
                )
                
        except Exception as ex:
            logger.error("分析用户意图失败", exc_info=ex)
            raise

    async def analyze_image_async(self, image_url: str) -> ImageAnalysisResultDto:
        """
        分析图片内容
        
        Args:
            image_url: 图片URL
            
        Returns:
            图片分析结果
        """
        try:
            # 构建消息列表
            messages = []
            
            # 系统提示词
            system_prompt = await self.prompt_template_service.get_content_by_key_async("CUSTOMERSERVICE_ANALYZEIMAGE_PROMPT")
            messages.append(InputMessage(role=ChatRoleType.SYSTEM, content=system_prompt))
            
            # 发送图片给模型
            messages.append(InputMessage.from_text_and_image_urls(
                role=ChatRoleType.USER,
                text="请描述图片.",
                image_urls=[image_url]
            ))
        # 调用AI服务分析图片内容
            response = await self.ai_service.chat_completion_async(messages)
            
            try:
                # 尝试解析AI返回的JSON结果
                result = ImageAnalysisResultDto(**json.loads(response))
                return result
            except json.JSONDecodeError:
                # 如果解析失败，构造一个简单的结果对象
                return ImageAnalysisResultDto(
                    description=response,
                    tags=[]
                )
        except Exception as ex:
            logger.error("分析图片内容失败", exc_info=ex)
            raise

    async def generate_reply_async(
        self, 
        query: str, 
        history: List[Dict[str, Any]], 
        intent: str, 
        context: Optional[str] = None
    ) -> str:
        """
        使用AI生成回复
        
        Args:
            query: 用户查询
            history: 历史记录
            intent: 识别的意图
            context: 函数工具的调用结果
            
        Returns:
            AI回复
        """
        try:
            messages = []
            
            # 添加回复提示词
            system_prompt = await self.prompt_template_service.get_content_by_key_async("CUSTOMERSERVICE_REPLY_PROMPT")
            messages.append(InputMessage(role=ChatRoleType.SYSTEM, content=system_prompt))
            
            # 添加敏感词
            messages.append(InputMessage(role=ChatRoleType.SYSTEM, content=f"敏感词包括：{self.sensitive_words}"))
            
            # 添加知识库知识的限定
            knowledge_prompt = ""
            if context:
                knowledge_prompt += "根据以下查询的结果和知识信息回答（这是唯一可信的专业信息来源）：\n"
                knowledge_prompt += context
            else:
                # 如果没有知识库信息，添加额外警告
                knowledge_prompt = await self.prompt_template_service.get_content_by_key_async("CUSTOMERSERVICE_REPLY_NOKNOWLEDGE_PROMPT")
                
            messages.append(InputMessage(role=ChatRoleType.SYSTEM, content=knowledge_prompt))
            
            # 添加历史对话
            if history and len(history) > 0:
                for item in history:
                    if item['role'] == ChatRoleType.USER:
                        messages.append(InputMessage(role=ChatRoleType.USER, content=item['content']))
                    elif item['role'] == ChatRoleType.ASSISTANT:
                        messages.append(InputMessage(role=ChatRoleType.ASSISTANT, content=item['content']))
            
            # 添加用户查询
            messages.append(InputMessage(role=ChatRoleType.USER, content=query))
            
            # 调用AI服务生成回复
            return await self.ai_service.chat_completion_async(messages)
            
        except Exception as ex:
            logger.error("生成AI回复失败", exc_info=ex)
            raise