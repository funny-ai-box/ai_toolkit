"""
聊天AI服务实现
"""
import logging
import json
from typing import List, Optional, Dict, Any
import httpx

from app.core.ai.chat.base import IChatAIService
from app.core.ai.dtos import ChatRoleType, InputMessage
from app.core.config.settings import Settings
from app.modules.base.prompts.services import PromptTemplateService
from app.modules.tools.customerservice.services.chat_tools_service import ChatToolsService
from app.modules.tools.customerservice.services.dtos.chat_dto import (
    IntentRecognitionResultDto, ImageAnalysisResultDto, ChatHistoryDto
)

class ChatAIService:
    """AI服务类"""
    
    def __init__(
        self,
        ai_service: IChatAIService,
        chat_tools_service: ChatToolsService,
        prompt_service: PromptTemplateService,
        settings: Settings
    ):
        """
        初始化聊天AI服务
        
        Args:
            ai_service: AI服务
            chat_tools_service: 聊天工具服务
            prompt_service: 提示词模板服务
            settings: 配置
        """
        self.ai_service = ai_service
        self.chat_tools_service = chat_tools_service
        self.prompt_service = prompt_service
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        
        # 从配置中获取敏感词
        customer_service_config = settings.get_or_default("CustomerService", {})
        chat_config = customer_service_config.get("Chat", {})
        self.sensitive_words = chat_config.get("SensitiveWords", "色情、赌博、毒品、暴力等违法内容")
    
    async def get_embedding_async(self, text: str) -> List[float]:
        """
        获取文本嵌入向量
        
        Args:
            text: 文本
            
        Returns:
            嵌入向量
        """
        return await self.ai_service.get_embedding_async(text)
    
    async def analysis_intent_async(
        self,
        user_id: int,
        history: List[ChatHistoryDto],
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
            system_prompt = await self.prompt_service.get_content_by_key_async("CUSTOMERSERVICE_ANALYSISINTENT_PROMPT")
            if not system_prompt:
                system_prompt = "你是一个智能客服助手，请分析用户的意图并提取关键信息。"
            
            messages.append(InputMessage(ChatRoleType.SYSTEM, system_prompt))
            messages.append(InputMessage(ChatRoleType.SYSTEM, f"敏感词包括：{self.sensitive_words}"))
            
            # 添加历史记录，帮助AI更好地理解上下文
            if history and len(history) > 0:
                messages.append(InputMessage(ChatRoleType.USER, "###下面是对话历史信息"))
                history_text = ""
                for item in history:
                    if item.role == ChatRoleType.USER:
                        history_text += f"用户:{item.content}\n"
                    elif item.role == ChatRoleType.ASSISTANT:
                        history_msg = f"客服:{item.content}"
                        if item.intent and item.call_datas:
                            history_msg += f" [此回复通过工具查询，涉及的实体ID: {item.call_datas}]"
                        history_text += f"{history_msg}\n"
                messages.append(InputMessage(ChatRoleType.USER, history_text))
            
            # 添加当前用户消息
            messages.append(InputMessage(ChatRoleType.USER, f"###用户当前问题：{message}"))
            
            # 调用AI服务分析
            response = await self.ai_service.chat_completion_async(messages)
            
            # 解析结果
            try:
                result = json.loads(response)
                return IntentRecognitionResultDto(**result)
            except json.JSONDecodeError:
                print("解析意图识别结果JSON失败")
                # 如果解析失败，返回一个默认的结果
                return IntentRecognitionResultDto(
                    intent="GENERAL_QUERY",
                    context="",
                    id_datas=None
                )
        except Exception as ex:
            print(f"分析用户意图失败, 错误: {str(ex)}")
            # 返回一个默认的结果
            return IntentRecognitionResultDto(
                intent="GENERAL_QUERY",
                context="",
                id_datas=None
            )
    
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
            system_prompt = await self.prompt_service.get_content_by_key_async("CUSTOMERSERVICE_ANALYZEIMAGE_PROMPT")
            if not system_prompt:
                system_prompt = "请分析图片内容，提供详细描述和标签。"
                
            messages.append(InputMessage(ChatRoleType.SYSTEM, system_prompt))
            
            # 发送图片给模型
            messages.append(InputMessage.from_text_and_image_urls(
    ChatRoleType.USER,
    "请描述图片.",
    [image_url]
))
            
            # 调用AI服务分析图片内容
            response = await self.ai_service.chat_completion_async(messages)
            
            try:
                # 尝试解析AI返回的JSON结果
                result = json.loads(response)
                return ImageAnalysisResultDto(**result)
            except json.JSONDecodeError:
                # 如果解析失败，构造一个简单的结果对象
                return ImageAnalysisResultDto(
                    description=response,
                    tags=[]
                )
        except Exception as ex:
            print(f"分析图片内容失败, 错误: {str(ex)}")
            raise
    
    async def generate_reply_async(
        self,
        query: str,
        history: List[ChatHistoryDto],
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
            system_prompt = await self.prompt_service.get_content_by_key_async("CUSTOMERSERVICE_REPLY_PROMPT")
            if not system_prompt:
                system_prompt = "你是一个智能客服助手，请基于提供的知识回答用户的问题。"
                
            messages.append(InputMessage(ChatRoleType.SYSTEM, system_prompt))
            
            # 添加敏感词
            messages.append(InputMessage(ChatRoleType.SYSTEM, f"敏感词包括：{self.sensitive_words}"))
            
            # 添加知识库知识的限定
            knowledge_prompt = ""
            if context:
                knowledge_prompt += "根据以下查询的结果和知识信息回答（这是唯一可信的专业信息来源）：\n"
                knowledge_prompt += context
            else:
                # 如果没有知识库信息，添加额外警告
                knowledge_prompt = await self.prompt_service.get_content_by_key_async("CUSTOMERSERVICE_REPLY_NOKNOWLEDGE_PROMPT")
                if not knowledge_prompt:
                    knowledge_prompt = "注意：我没有查询到相关的知识库信息，以下回答基于我的通用知识。"
                    
            messages.append(InputMessage(ChatRoleType.SYSTEM, knowledge_prompt))
            
            # 添加历史对话
            if history and len(history) > 0:
                for item in history:
                    if item.role == ChatRoleType.USER:
                        messages.append(InputMessage(ChatRoleType.USER, item.content))
                    elif item.role == ChatRoleType.ASSISTANT:
                        messages.append(InputMessage(ChatRoleType.ASSISTANT, item.content))
            
            # 添加用户查询
            messages.append(InputMessage(ChatRoleType.USER, query))
            
            # 调用AI服务生成回复
            return await self.ai_service.chat_completion_async(messages)
        except Exception as ex:
            print(f"生成AI回复失败, 错误: {str(ex)}")
            raise