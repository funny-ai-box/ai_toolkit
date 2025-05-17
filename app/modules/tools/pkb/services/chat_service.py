"""
聊天服务实现
"""
import datetime
import json
import logging
import uuid
from typing import List, Tuple, Any, Dict, Optional, Callable, Set
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai.chat.base import IChatAIService
from app.core.ai.vector.base import IUserDocsMilvusService
from app.core.ai.dtos import ChatRoleType, InputMessage, UserDocsVectorSearchResult
from app.core.config.settings import Settings
from app.core.exceptions import BusinessException
from app.core.utils.snowflake import generate_id
from app.core.dtos import DocumentAppType

from app.modules.base.prompts.services import PromptTemplateService

from app.modules.tools.pkb.models import ChatSession, ChatHistory
from app.modules.tools.pkb.repositories.interfaces.chat_session_repository import IChatSessionRepository
from app.modules.tools.pkb.repositories.interfaces.chat_history_repository import IChatHistoryRepository


logger = logging.getLogger(__name__)


class ChatService:
    """聊天服务"""

    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        chat_session_repository: IChatSessionRepository,
        chat_history_repository: IChatHistoryRepository,
        ai_service: IChatAIService,
        user_docs_service: IUserDocsMilvusService,
        prompt_template_service: PromptTemplateService,
    ):
        """
        初始化聊天服务

        Args:
            db: 数据库会话
            settings: 配置
            chat_session_repository: 聊天会话仓储
            chat_history_repository: 聊天历史仓储
            ai_service: AI服务
            user_docs_service: 用户文档向量服务
            prompt_template_service: 提示词模板服务
        """
        self.db = db
        self.settings = settings
        self.chat_session_repository = chat_session_repository
        self.chat_history_repository = chat_history_repository
        self.ai_service = ai_service
        self.user_docs_service = user_docs_service
        self.prompt_template_service = prompt_template_service
        
        # 从配置加载聊天设置
        self.max_context_messages = settings.PKB_CHAT_MAX_CONTEXT_MESSAGES or 10
        self.max_vector_search_results = settings.PKB_CHAT_MAX_VECTOR_SEARCH_RESULTS or 5
        self.min_vector_score = settings.PKB_CHAT_MIN_VECTOR_SCORE or 0.7

    async def create_session_async(
        self, user_id: int, document_id: int, session_name: str, prompt: Optional[str] = None
    ) -> int:
        """
        创建聊天会话

        Args:
            user_id: 用户ID
            document_id: 文档ID
            session_name: 会话名称
            prompt: 提示词

        Returns:
            会话ID
        """
        try:
            # 获取默认提示词
            default_prompt = await self.prompt_template_service.get_content_by_key_async("PKB_ROLE_DEFAULT_PROMPT")
            
            # 创建会话
            session = ChatSession()
            session.user_id = user_id
            session.document_id = document_id  # 为0不指定文档
            session.session_name = session_name if session_name else "新的会话"
            session.prompt = prompt if prompt is not None else default_prompt
            session.is_shared = False
            
            # 添加会话
            await self.chat_session_repository.add_async(session)
            return session.id
        except Exception as ex:
            logger.error(f"创建聊天会话失败: {ex}", exc_info=True)
            raise

    async def update_session_async(
        self, session_id: int, session_name: Optional[str] = None, prompt: Optional[str] = None
    ) -> bool:
        """
        更新聊天会话

        Args:
            session_id: 会话ID
            session_name: 会话名称
            prompt: 提示词

        Returns:
            操作结果
        """
        try:
            session = await self.chat_session_repository.get_by_id_async(session_id)
            if not session:
                return False

            if session_name is not None:
                session.session_name = session_name

            if prompt is not None:
                session.prompt = prompt

            return await self.chat_session_repository.update_async(session)
        except Exception as ex:
            logger.error(f"更新聊天会话失败: {ex}", exc_info=True)
            raise

    async def delete_session_async(self, session_id: int) -> bool:
        """
        删除聊天会话

        Args:
            session_id: 会话ID

        Returns:
            操作结果
        """
        try:
            # 删除会话的所有聊天历史
            await self.chat_history_repository.delete_by_session_id_async(session_id)
            
            # 删除会话
            return await self.chat_session_repository.delete_async(session_id)
        except Exception as ex:
            logger.error(f"删除聊天会话失败: {ex}", exc_info=True)
            raise

    async def share_session_async(self, session_id: int, is_shared: bool) -> str:
        """
        分享聊天会话

        Args:
            session_id: 会话ID
            is_shared: 是否分享

        Returns:
            分享码
        """
        try:
            session = await self.chat_session_repository.get_by_id_async(session_id)
            if not session:
                raise BusinessException(f"会话{session_id}不存在")

            session.is_shared = is_shared

            if is_shared and not session.share_code:
                # 生成分享码
                session.share_code = str(uuid.uuid4()).replace("-", "")[:8]

            await self.chat_session_repository.update_async(session)
            return session.share_code if is_shared else ""
        except Exception as ex:
            if isinstance(ex, BusinessException):
                raise
            logger.error(f"分享聊天会话失败: {ex}", exc_info=True)
            raise

    async def get_match_documents(
        self, user_id: int, document_id: int, message: str
    ) -> Tuple[str, List[UserDocsVectorSearchResult]]:
        """
        获取匹配的文档

        Args:
            user_id: 用户ID
            document_id: 文档ID
            message: 消息内容

        Returns:
            (向量ID列表JSON, 搜索结果列表)
        """
        # 向量搜索
        embedding = await self.ai_service.get_embedding_async(message)
        search_results = await self.user_docs_service.search_async(
            user_id=user_id,
            app_type=DocumentAppType.PKB,
            document_id=document_id,
            query_vector=embedding,
            top_k=self.max_vector_search_results,
            min_score=self.min_vector_score
        )

        # 检查是否找到了相关内容
        has_relevant_content = len(search_results) > 0
        
        # 记录搜索结果信息
        logger.info(f"向量搜索结果: 找到{len(search_results)}条相关内容, 阈值为{self.min_vector_score}")

        # 保存匹配的文档ID
        matched_vector_ids = ""
        if has_relevant_content:
            vector_ids = [r.id for r in search_results]
            matched_vector_ids = json.dumps(vector_ids)
            logger.info(f"匹配的向量ID: {matched_vector_ids}")
        else:
            logger.warning(f"没有找到与问题'{message}'相关的内容")

        return matched_vector_ids, search_results

    async def chat_async(
        self, user_id: int, session_id: int, message: str
    ) -> Tuple[str, int, List[UserDocsVectorSearchResult]]:
        """
        聊天

        Args:
            user_id: 用户ID
            session_id: 会话ID
            message: 用户消息

        Returns:
            (回复内容, 回复消息ID, 搜索结果列表)
        """
        try:
            # 获取会话信息
            session = await self.chat_session_repository.get_by_id_async(session_id)
            if not session:
                raise BusinessException(f"会话{session_id}不存在")

            # 检查是否是首次聊天
            history = await self.chat_history_repository.get_by_session_id_async(session_id, 1)
            is_first_chat = len(history) == 0

            # 获取匹配的文档
            matched_vector_ids, search_results = await self.get_match_documents(
                user_id, session.document_id, message
            )

            # 获取相关文本
            search_context = self._get_context_from_search_results(search_results)

            # 保存用户消息
            user_message = ChatHistory()
            user_message.session_id = session_id
            user_message.user_id = user_id
            user_message.role = "user"
            user_message.content = message
            user_message.vector_ids = matched_vector_ids
            await self.chat_history_repository.add_async(user_message)

            # 获取会话历史
            history = await self.chat_history_repository.get_by_session_id_async(
                session_id, self.max_context_messages * 2
            )
            history.sort(key=lambda h: h.create_date)

            # 构建聊天消息
            messages = await self._build_chat_messages(
                session.prompt or "", history, message, search_context
            )

            # 调用AI生成回复
            reply = await self.ai_service.chat_completion_async(messages)

            # 保存AI回复
            assistant_message = ChatHistory()
            assistant_message.session_id = session_id
            assistant_message.user_id = user_id
            assistant_message.role = "assistant"
            assistant_message.content = reply
            assistant_message.vector_ids = matched_vector_ids
            await self.chat_history_repository.add_async(assistant_message)

            # 如果是首次聊天且会话名称是默认的"新的会话"，则根据用户消息更新会话名称
            if is_first_chat and session.session_name == "新的会话":
                await self._update_session_name_from_first_message_async(session_id, message)

            return reply, assistant_message.id, search_results
        except Exception as ex:
            if isinstance(ex, BusinessException):
                raise
            logger.error(f"聊天失败: {ex}", exc_info=True)
            raise

    async def streaming_chat_async(
        self,
        user_id: int,
        session_id: int,
        message: str,
        on_chunk_received: Callable[[str], None],
        cancellation_token = None
    ) -> Tuple[str, int, List[UserDocsVectorSearchResult]]:
        """
        流式聊天

        Args:
            user_id: 用户ID
            session_id: 会话ID
            message: 用户消息
            on_chunk_received: 接收到数据块时的回调函数
            cancellation_token: 取消令牌

        Returns:
            (回复内容, 回复消息ID, 搜索结果列表)
        """
        try:
            # 获取会话信息
            session = await self.chat_session_repository.get_by_id_async(session_id)
            if not session:
                raise BusinessException(f"会话{session_id}不存在")

            # 检查是否是首次聊天
            history = await self.chat_history_repository.get_by_session_id_async(session_id, 1)
            is_first_chat = len(history) == 0

            # 获取匹配的文档
            matched_vector_ids, search_results = await self.get_match_documents(
                user_id, session.document_id, message
            )

            # 获取相关文本
            search_context = self._get_context_from_search_results(search_results)

            # 保存用户消息
            user_message = ChatHistory()
            user_message.session_id = session_id
            user_message.user_id = user_id
            user_message.role = "user"
            user_message.content = message
            user_message.vector_ids = matched_vector_ids
            await self.chat_history_repository.add_async(user_message)

            # 获取会话历史
            history = await self.chat_history_repository.get_by_session_id_async(
                session_id, self.max_context_messages * 2
            )
            history.sort(key=lambda h: h.create_date)

            # 构建聊天消息
            messages = await self._build_chat_messages(
                session.prompt or "", history, message, search_context
            )

            # 调用AI流式生成回复
            reply = ""
            async for chunk in self.ai_service.streaming_chat_completion_async(messages):
                if cancellation_token and cancellation_token.cancelled:
                    break
                reply += chunk
                on_chunk_received(chunk)
                
                # 简单的防止过长停顿
                await asyncio.sleep(0)

            # 保存AI回复
            assistant_message = ChatHistory()
            assistant_message.session_id = session_id
            assistant_message.user_id = user_id
            assistant_message.role = "assistant"
            assistant_message.content = reply
            assistant_message.vector_ids = matched_vector_ids
            await self.chat_history_repository.add_async(assistant_message)

            # 如果是首次聊天且会话名称是默认的"新的会话"，则根据用户消息更新会话名称
            if is_first_chat and session.session_name == "新的会话":
                await self._update_session_name_from_first_message_async(session_id, message)

            return reply, assistant_message.id, search_results
        except Exception as ex:
            if isinstance(ex, BusinessException):
                raise
            logger.error(f"流式聊天失败: {ex}", exc_info=True)
            raise
            
    async def _update_session_name_from_first_message_async(self, session_id: int, message: str) -> bool:
        """
        根据首次聊天内容更新会话名称

        Args:
            session_id: 会话ID
            message: 首次聊天内容

        Returns:
            更新结果
        """
        try:
            # 截取用户消息的前20个字符作为会话名称
            # 如果消息很短，则使用全部内容
            if len(message) <= 20:
                new_session_name = message
            else:
                # 尝试找到一个合适的截断点，比如句号或问号
                end_pos = -1
                for i in range(min(len(message), 30)):
                    if message[i] in ['.', '?', '!', '。', '？', '！']:
                        end_pos = i
                        break

                # 如果找不到合适的截断点，就截取前20个字符
                if end_pos == -1 or end_pos > 20:
                    new_session_name = message[:20] + "..."
                else:
                    new_session_name = message[:end_pos + 1]

            # 更新会话名称
            session = await self.chat_session_repository.get_by_id_async(session_id)
            if session and session.session_name == "新的会话":
                session.session_name = new_session_name
                return await self.chat_session_repository.update_async(session)

            return False
        except Exception as ex:
            logger.error(f"更新会话名称失败: {ex}", exc_info=True)
            return False

    def _get_context_from_search_results(self, search_results: List[UserDocsVectorSearchResult]) -> str:
        """
        从搜索结果获取上下文

        Args:
            search_results: 搜索结果

        Returns:
            上下文文本
        """
        if not search_results:
            return ""

        context = ["以下是从知识库中找到的相关信息:", ""]
        
        for result in search_results:
            context.append(f"[相关度: {result.score:.1%}]")
            context.append(result.content)
            context.append("---")
        
        return "\n".join(context)

    async def _build_chat_messages(
        self, prompt: str, history: List[ChatHistory], message: str, context: str
    ) -> List[InputMessage]:
        """
        构建聊天消息

        Args:
            prompt: 系统提示词
            history: 历史消息
            message: 当前消息
            context: 上下文

        Returns:
            聊天消息列表
        """
        messages = []
        
        # 基础的系统提示词
        messages.append(InputMessage(role=ChatRoleType.System, content=prompt))

        # 构建完整的系统提示词，明确告知AI是否有找到相关内容 
        if context:
            knowledge_prompt = await self.prompt_template_service.get_content_by_key_async("PKB_MATCH_KNOWLEDGE_PROMPT")
            knowledge_prompt = knowledge_prompt.replace("{Context}", context)
        else:
            # 当找不到相关知识库内容时
            knowledge_prompt = await self.prompt_template_service.get_content_by_key_async("PKB_MATCH_NOT_KNOWLEDGE_PROMPT")

        messages.append(InputMessage(role=ChatRoleType.System, content=knowledge_prompt))

        # 智能选择历史消息
        selected_history = self._select_relevant_history(history, message, self.max_context_messages)

        # 添加选择的历史消息
        for item in selected_history:
            if item.role == "user":
                messages.append(InputMessage(role=ChatRoleType.User, content=item.content or ""))
            else:
                messages.append(InputMessage(role=ChatRoleType.Assistant, content=item.content or ""))

        # 如果当前消息不在历史记录中，添加它
        current_message_in_history = any(h.role == "user" and h.content == message for h in selected_history)
        if not current_message_in_history:
            messages.append(InputMessage(role=ChatRoleType.User, content=message))

        return messages

    def _select_relevant_history(
        self, history: List[ChatHistory], current_message: str, max_messages: int
    ) -> List[ChatHistory]:
        """
        智能选择相关历史消息

        Args:
            history: 所有历史消息
            current_message: 当前消息
            max_messages: 最大消息数量

        Returns:
            选择的历史消息
        """
        if not history:
            return []

        # 对历史按时间排序
        ordered_history = sorted(history, key=lambda h: h.create_date)

        # 估算消息token总数
        ESTIMATED_TOKENS_PER_CHARACTER = 4  # 每个字符大约4个token
        MAX_TOTAL_TOKENS = 8000  # 最大token数，根据模型调整
        MINIMUM_RECENT_TURNS = 3  # 至少保留最近的3轮对话

        # 选择策略：
        # 1. 总是包含最近的几轮对话
        # 2. 如果空间允许，添加更早的对话
        # 3. 如果总大小超过限制，截断较早的对话

        result = []
        remaining_tokens = MAX_TOTAL_TOKENS

        # 计算当前消息的token数
        current_message_tokens = len(current_message or "") * ESTIMATED_TOKENS_PER_CHARACTER
        remaining_tokens -= current_message_tokens

        # 确保最近的几轮对话被包
        # 确保最近的几轮对话被包含
        recent_messages = ordered_history[-min(len(ordered_history), MINIMUM_RECENT_TURNS * 2):]
        for msg in recent_messages:
            result.append(msg)
            remaining_tokens -= len(msg.content or "") * ESTIMATED_TOKENS_PER_CHARACTER

        # 如果还有空间，添加更早的对话
        if remaining_tokens > 0 and len(ordered_history) > len(recent_messages):
            earlier_messages = ordered_history[:-len(recent_messages)]

            # 从最近到最早尝试添加
            for i in range(len(earlier_messages) - 1, -1, -1):
                msg = earlier_messages[i]
                msg_tokens = len(msg.content or "") * ESTIMATED_TOKENS_PER_CHARACTER

                if msg_tokens <= remaining_tokens:
                    result.insert(0, msg)  # 插入到最前面，保持时间顺序
                    remaining_tokens -= msg_tokens
                else:
                    # 如果这条消息太大，跳过并继续检查更早的消息
                    continue

                # 如果已经达到最大消息数，停止添加
                if len(result) >= max_messages:
                    break

        # 确保结果按时间排序
        return sorted(result, key=lambda h: h.create_date)

    async def get_session_history_async(self, session_id: int, limit: int = 20) -> List[ChatHistory]:
        """
        获取会话历史

        Args:
            session_id: 会话ID
            limit: 数量限制

        Returns:
            聊天历史
        """
        try:
            history = await self.chat_history_repository.get_by_session_id_async(session_id, limit)
            return sorted(history, key=lambda h: h.create_date)
        except Exception as ex:
            logger.error(f"获取聊天历史失败: {ex}", exc_info=True)
            raise

    async def get_session_by_share_code_async(self, share_code: str) -> Optional[ChatSession]:
        """
        通过分享码获取会话

        Args:
            share_code: 分享码

        Returns:
            会话信息
        """
        try:
            return await self.chat_session_repository.get_by_share_code_async(share_code)
        except Exception as ex:
            logger.error(f"通过分享码获取会话失败: {ex}", exc_info=True)
            raise