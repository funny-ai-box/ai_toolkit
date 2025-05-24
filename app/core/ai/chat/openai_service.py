# app/core/ai/chat/openai_service.py - 修复角色转换
import logging
import httpx
from typing import List, Dict, Any, AsyncGenerator, Optional

from openai import AsyncOpenAI, OpenAIError
from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion import ChatCompletion

from app.core.config.settings import settings
from app.core.ai.chat.base import IChatAIService
from app.core.ai.dtos import (
    ChatAIUploadFileDto, InputMessage, ChatRoleType, 
    InputContentType, InputTextContent, InputImageContent, InputImageSourceType
)
from app.core.exceptions import BusinessException, NotFoundException

logger = logging.getLogger(__name__)

class OpenAIService(IChatAIService):
    """使用 OpenAI API 的聊天服务实现"""
    
    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        """初始化 OpenAI 异步客户端"""
        if not settings.OPENAI_API_KEY:
            raise ValueError("OpenAI API Key 未在配置中设置。")

        try:
            effective_http_client = http_client if http_client else httpx.AsyncClient(timeout=180.0)

            self.client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=None,
                http_client=effective_http_client
            )
            self.embedding_model = settings.OPENAI_EMBEDDING_MODEL
            self.chat_model = settings.OPENAI_CHAT_MODEL
            self.max_tokens = settings.OPENAI_MAX_TOKENS
            self.dimension = settings.OPENAI_DIMENSION
            logger.info(f"OpenAI 服务已初始化。聊天模型: {self.chat_model}, 嵌入模型: {self.embedding_model}")
        except Exception as e:
            logger.error(f"初始化 OpenAI 客户端失败: {e}")
            raise RuntimeError(f"初始化 OpenAI 客户端失败: {e}") from e

    def _convert_input_to_openai_message(self, message: InputMessage) -> Dict[str, Any]:
        """将内部 InputMessage 转换为 OpenAI API 需要的格式"""
        # 使用 openai_role 属性获取字符串角色
        openai_role = message.role.openai_role

        # 处理 content
        openai_content: Any = ""
        if len(message.content) == 1 and isinstance(message.content[0], InputTextContent):
            openai_content = message.content[0].text
        else:
            openai_content_parts = []
            for part in message.content:
                if isinstance(part, InputTextContent):
                    openai_content_parts.append({"type": "text", "text": part.text})
                elif isinstance(part, InputImageContent):
                    image_part = {"type": "image_url"}
                    if part.source.type == InputImageSourceType.URL:
                        image_part["image_url"] = {
                            "url": part.source.url,
                            "detail": "low"
                        }
                    elif part.source.type == InputImageSourceType.BASE64:
                        base64_url = f"data:{part.source.media_type};base64,{part.source.data}"
                        image_part["image_url"] = {
                            "url": base64_url,
                            "detail": "low"
                        }
                    else:
                         logger.warning(f"不支持的图片源类型: {part.source.type}")
                         continue
                    openai_content_parts.append(image_part)
            openai_content = openai_content_parts

        return {"role": openai_role, "content": openai_content}

    def _convert_messages_to_openai_format(self, messages: List[InputMessage]) -> List[Dict[str, Any]]:
        """将 InputMessage 列表转换为 OpenAI API 格式"""
        return [self._convert_input_to_openai_message(msg) for msg in messages]

    async def get_embedding_async(self, text: str) -> List[float]:
        """获取单个文本的嵌入向量"""
        try:
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
                dimensions=self.dimension
            )
            if response.data and len(response.data) > 0:
                embedding = response.data[0].embedding
                return list(embedding) if embedding else []
            else:
                 logger.error("OpenAI embedding API 返回了空数据。")
                 raise BusinessException("获取文本嵌入失败 (API 返回空)")
        except OpenAIError as e:
            logger.error(f"OpenAI API 嵌入请求失败: {e}")
            raise BusinessException(f"获取文本嵌入失败: {e.type} - {e.message}") from e
        except Exception as e:
            logger.error(f"获取文本嵌入时发生未知错误: {e}")
            raise BusinessException(f"获取文本嵌入时发生未知错误: {str(e)}") from e

    async def get_embeddings_async(self, texts: List[str]) -> List[List[float]]:
        """批量获取多个文本的嵌入向量"""
        if not texts:
            return []
        try:
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=texts,
                dimensions=self.dimension
            )
            embeddings = [item.embedding for item in response.data if item.embedding]
            return [list(emb) for emb in embeddings]
        except OpenAIError as e:
            logger.error(f"OpenAI API 批量嵌入请求失败: {e}")
            raise BusinessException(f"批量获取文本嵌入失败: {e.type} - {e.message}") from e
        except Exception as e:
            logger.error(f"批量获取文本嵌入时发生未知错误: {e}")
            raise BusinessException(f"批量获取文本嵌入时发生未知错误: {str(e)}") from e

    async def upload_file_async(self, file_path: str) -> ChatAIUploadFileDto:
        """OpenAI 的聊天接口不直接支持这种方式的文件上传供 chat 使用"""
        logger.warning("OpenAI Chat Completion API 不支持通过此方法上传文件供直接访问。")
        raise NotImplementedError("OpenAI 服务未实现 UploadFileAsync 功能。请使用 Assistant API 或其他方式处理文件。")

    async def chat_completion_async(self, messages: List[InputMessage]) -> str:
        """执行一次完整的聊天补全请求"""
        if not messages:
            return ""
        openai_messages = self._convert_messages_to_openai_format(messages)

        try:
            completion: ChatCompletion = await self.client.chat.completions.create(
                model=self.chat_model,
                messages=openai_messages,
                max_tokens=self.max_tokens,
                temperature=0.7,
            )
            if completion.choices and completion.choices[0].message:
                content = completion.choices[0].message.content
                return content if content else ""
            else:
                logger.warning("OpenAI chat completion API 返回结果中无有效回复。")
                return "[模型未返回有效内容]"

        except OpenAIError as e:
            logger.error(f"OpenAI API 聊天补全请求失败: {e}")
            if "context_length_exceeded" in str(e):
                 raise BusinessException("输入内容过长，请减少输入或缩短对话历史。", code=400) from e
            raise BusinessException(f"AI 聊天服务出错: {e.type} - {e.message}") from e
        except Exception as e:
            logger.error(f"聊天补全时发生未知错误: {e}")
            raise BusinessException(f"AI 聊天服务发生未知错误: {str(e)}") from e

    async def streaming_chat_completion_async(
        self, messages: List[InputMessage]
    ) -> AsyncGenerator[str, None]:
        """执行流式聊天补全请求"""
        if not messages:
            yield ""
            return

        openai_messages = self._convert_messages_to_openai_format(messages)

        try:
            stream = await self.client.chat.completions.create(
                model=self.chat_model,
                messages=openai_messages,
                max_tokens=self.max_tokens,
                temperature=0.7,
                stream=True,
            )
            async for chunk in stream:
                 if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                     content_piece = chunk.choices[0].delta.content
                     yield content_piece

        except OpenAIError as e:
            logger.error(f"OpenAI API 流式聊天补全请求失败: {e}")
            yield f"[AI Error: {e.type} - {e.message}]"
        except Exception as e:
            logger.error(f"流式聊天补全时发生未知错误: {e}")
            yield f"[Unknown AI Error: {str(e)}]"