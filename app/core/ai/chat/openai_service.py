# app/core/ai/chat/openai_service.py
import logging
import httpx
from typing import List, Dict, Any, AsyncGenerator, cast, Optional

from openai import AsyncOpenAI, OpenAIError # 使用异步客户端
from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion import ChatCompletion

from app.core.config.settings import settings
from app.core.ai.chat.base import IChatAIService
from app.core.ai.dtos import ChatAIUploadFileDto, InputMessage, ChatRoleType, InputContentType, InputTextContent, InputImageContent, InputImageSourceType
from app.core.exceptions import BusinessException, NotFoundException # 使用自定义异常

logger = logging.getLogger(__name__)

class OpenAIService(IChatAIService):
    """
    使用 OpenAI API 的聊天服务实现。
    """
    def __init__(self, http_client: Optional[httpx.AsyncClient] = None): # <--- 接收可选的 client
        """初始化 OpenAI 异步客户端"""
        if not settings.OPENAI_API_KEY:
            raise ValueError("OpenAI API Key 未在配置中设置。")

        try:
            # 配置异步客户端
            # 可以添加 base_url, http_client (例如使用 httpx 并配置代理) 等参数
            # http_client = httpx.AsyncClient(proxies=...) # 如果需要代理            
            # --- 使用传入的 http_client (如果提供) ---
            effective_http_client = http_client if http_client else httpx.AsyncClient(timeout=180.0) # 否则创建默认的

            self.client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                # organization=settings.OPENAI_ORGANIZATION, # 如果有组织 ID
                timeout=None, # 超时由 httpx client 控制
                http_client=effective_http_client # 如果配置了带代理的 httpx 客户端
            )
            self.embedding_model = settings.OPENAI_EMBEDDING_MODEL
            self.chat_model = settings.OPENAI_CHAT_MODEL
            self.max_tokens = settings.OPENAI_MAX_TOKENS
            self.dimension = settings.OPENAI_DIMENSION
            logger.info(f"OpenAI 服务已初始化。聊天模型: {self.chat_model}, 嵌入模型: {self.embedding_model}")
        except Exception as e:
            logger.error(f"初始化 OpenAI 客户端失败: {e}", exc_info=True)
            raise RuntimeError(f"初始化 OpenAI 客户端失败: {e}") from e

    def _convert_input_to_openai_message(self, message: InputMessage) -> Dict[str, Any]:
        """将内部 InputMessage 转换为 OpenAI API 需要的格式"""
        openai_role = message.role.value # 直接使用枚举值 "system", "user", "assistant"

        # 处理 content (可能是文本，也可能是包含文本和图片的列表)
        openai_content: Any = "" # 默认是字符串
        if len(message.content) == 1 and isinstance(message.content[0], InputTextContent):
            # 如果只有一个文本块，content 就是字符串
            openai_content = message.content[0].text
        else:
            # 如果有多个块，或者包含图片，content 是一个列表
            openai_content_parts = []
            for part in message.content:
                if isinstance(part, InputTextContent):
                    openai_content_parts.append({"type": "text", "text": part.text})
                elif isinstance(part, InputImageContent):
                    image_part = {"type": "image_url"}
                    if part.source.type == InputImageSourceType.URL:
                        image_part["image_url"] = {
                            "url": part.source.url,
                            # OpenAI 支持 detail: low, high, auto
                            "detail": "low" # 使用低分辨率以节省 token
                        }
                    elif part.source.type == InputImageSourceType.BASE64:
                        # OpenAI 需要 base64 URL 格式: data:{media_type};base64,{data}
                        base64_url = f"data:{part.source.media_type};base64,{part.source.data}"
                        image_part["image_url"] = {
                            "url": base64_url,
                            "detail": "low"
                        }
                    else:
                         logger.warning(f"不支持的图片源类型: {part.source.type}")
                         continue # 跳过无效的图片类型
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
                dimensions=self.dimension # 指定维度
            )
            # 检查返回的数据结构
            if response.data and len(response.data) > 0:
                embedding = response.data[0].embedding
                # 确保返回的是 list[float]
                return list(embedding) if embedding else []
            else:
                 logger.error("OpenAI embedding API 返回了空数据。")
                 raise BusinessException("获取文本嵌入失败 (API 返回空)")
        except OpenAIError as e:
            logger.error(f"OpenAI API 嵌入请求失败: {e}", exc_info=True)
            raise BusinessException(f"获取文本嵌入失败: {e.type} - {e.message}") from e
        except Exception as e:
            logger.error(f"获取文本嵌入时发生未知错误: {e}", exc_info=True)
            raise BusinessException(f"获取文本嵌入时发生未知错误: {str(e)}") from e

    async def get_embeddings_async(self, texts: List[str]) -> List[List[float]]:
        """批量获取多个文本的嵌入向量"""
        if not texts:
            return []
        try:
            # OpenAI API 接受字符串列表作为输入
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=texts,
                dimensions=self.dimension
            )
            # 确保返回的嵌入列表与输入文本列表顺序一致
            # response.data 是 Embedding 对象的列表，按输入顺序排列
            embeddings = [item.embedding for item in response.data if item.embedding]
            # 确保是 list[float]
            return [list(emb) for emb in embeddings]
        except OpenAIError as e:
            logger.error(f"OpenAI API 批量嵌入请求失败: {e}", exc_info=True)
            raise BusinessException(f"批量获取文本嵌入失败: {e.type} - {e.message}") from e
        except Exception as e:
            logger.error(f"批量获取文本嵌入时发生未知错误: {e}", exc_info=True)
            raise BusinessException(f"批量获取文本嵌入时发生未知错误: {str(e)}") from e

    async def upload_file_async(self, file_path: str) -> ChatAIUploadFileDto:
        """OpenAI 的聊天接口不直接支持这种方式的文件上传供 chat 使用"""
        # 如果将来需要使用 File API，可以在这里实现
        logger.warning("OpenAI Chat Completion API 不支持通过此方法上传文件供直接访问。")
        raise NotImplementedError("OpenAI 服务未实现 UploadFileAsync 功能。请使用 Assistant API 或其他方式处理文件。")
        # 如果是 Assistant API:
        # try:
        #     with open(file_path, "rb") as f:
        #         openai_file = await self.client.files.create(file=f, purpose='assistants')
        #     return ChatAIUploadFileDto(
        #         mimeType=openai_file.mime_type, # 需要确认 OpenAI File 对象是否有 mime_type
        #         uri=openai_file.id # 使用 OpenAI 返回的文件 ID
        #     )
        # except Exception as e:
        #     logger.error(f"上传文件到 OpenAI 失败: {e}", exc_info=True)
        #     raise BusinessException(f"上传文件失败: {str(e)}") from e

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
                # 可以添加其他参数，如 top_p, frequency_penalty, presence_penalty
            )
            # 检查是否有回复内容
            if completion.choices and completion.choices[0].message:
                content = completion.choices[0].message.content
                return content if content else ""
            else:
                logger.warning("OpenAI chat completion API 返回结果中无有效回复。")
                return "[模型未返回有效内容]" # 或者返回空字符串或抛出异常

        except OpenAIError as e:
            logger.error(f"OpenAI API 聊天补全请求失败: {e}", exc_info=True)
            # 可以根据 e.type 或 e.code 区分不同错误类型
            if "context_length_exceeded" in str(e):
                 raise BusinessException("输入内容过长，请减少输入或缩短对话历史。", code=400) from e
            raise BusinessException(f"AI 聊天服务出错: {e.type} - {e.message}") from e
        except Exception as e:
            logger.error(f"聊天补全时发生未知错误: {e}", exc_info=True)
            raise BusinessException(f"AI 聊天服务发生未知错误: {str(e)}") from e

    async def streaming_chat_completion_async(
        self, messages: List[InputMessage]
    ) -> AsyncGenerator[str, None]:
        """执行流式聊天补全请求"""
        if not messages:
            yield "" # 如果输入为空，返回一个空生成器
            return

        openai_messages = self._convert_messages_to_openai_format(messages)

        try:
            stream = await self.client.chat.completions.create(
                model=self.chat_model,
                messages=openai_messages,
                max_tokens=self.max_tokens,
                temperature=0.7,
                stream=True, # 开启流式输出
            )
            async for chunk in stream:
                 # 检查流式块中是否有内容更新
                 if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                     content_piece = chunk.choices[0].delta.content
                     yield content_piece # 产生文本块

        except OpenAIError as e:
            logger.error(f"OpenAI API 流式聊天补全请求失败: {e}", exc_info=True)
            # 在流式接口中，通常不直接抛出异常中断，而是产生一个错误消息
            yield f"[AI Error: {e.type} - {e.message}]"
            # 或者根据需要抛出异常，让上层处理
            # raise BusinessException(f"AI 聊天服务出错: {e.type} - {e.message}") from e
        except Exception as e:
            logger.error(f"流式聊天补全时发生未知错误: {e}", exc_info=True)
            yield f"[Unknown AI Error: {str(e)}]"
            # raise BusinessException(f"AI 聊天服务发生未知错误: {str(e)}") from e