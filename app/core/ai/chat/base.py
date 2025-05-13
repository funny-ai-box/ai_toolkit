# app/core/ai/chat/base.py
from typing import List, Protocol, runtime_checkable, AsyncGenerator, Any
from abc import abstractmethod

from app.core.ai.dtos import ChatAIUploadFileDto
from app.core.ai.dtos import InputMessage # 修正：从 dtos 导入

# 使用 Protocol 定义接口 (Pythonic way)
@runtime_checkable # 允许运行时检查实现
class IChatAIService(Protocol):
    """
    AI 聊天服务的接口协议。
    定义了聊天和嵌入所需的基本方法。
    """

    @abstractmethod
    async def get_embedding_async(self, text: str) -> List[float]:
        """
        获取单个文本的嵌入向量。

        Args:
            text: 需要获取嵌入的文本。

        Returns:
            表示文本嵌入的浮点数列表。

        Raises:
            Exception: 如果获取嵌入过程中发生错误。
        """
        ...

    @abstractmethod
    async def get_embeddings_async(self, texts: List[str]) -> List[List[float]]:
        """
        批量获取多个文本的嵌入向量。

        Args:
            texts: 需要获取嵌入的文本列表。

        Returns:
            一个列表，其中每个元素是对应文本的嵌入向量（浮点数列表）。

        Raises:
            Exception: 如果获取嵌入过程中发生错误。
        """
        ...

    @abstractmethod
    async def upload_file_async(self, file_path: str) -> ChatAIUploadFileDto:
        """
        上传文件供 AI 服务访问（如果支持）。

        Args:
            file_path: 要上传的本地文件路径。

        Returns:
            包含文件信息（如 ID 或 URI）的 DTO。

        Raises:
            NotImplementedError: 如果 AI 服务不支持文件上传。
            Exception: 如果上传过程中发生错误。
        """
        ...

    @abstractmethod
    async def chat_completion_async(self, messages: List[InputMessage]) -> str:
        """
        执行一次完整的聊天补全请求。

        Args:
            messages: 对话历史消息列表。

        Returns:
            AI 生成的回复文本。

        Raises:
            Exception: 如果聊天补全过程中发生错误。
        """
        ...

    # Python 中流式处理通常使用异步生成器 (AsyncGenerator)
    @abstractmethod
    async def streaming_chat_completion_async(
        self, messages: List[InputMessage]
    ) -> AsyncGenerator[str, None]:
        """
        执行流式聊天补全请求。

        Args:
            messages: 对话历史消息列表。

        Returns:
            一个异步生成器，每次迭代产生一部分 AI 回复文本块 (chunk)。

        Raises:
            Exception: 如果流式聊天补全过程中发生错误。
        """
        ...