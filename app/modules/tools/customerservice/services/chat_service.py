"""
聊天服务实现
"""
import logging
import uuid
from typing import List, Optional, Tuple
from datetime import datetime
from fastapi import UploadFile

from app.core.storage.base import IStorageService
from app.core.exceptions import BusinessException, NotFoundException
from app.core.config.settings import Settings
from app.core.dtos import PagedResultDto
from app.core.ai.dtos import ChatRoleType

from app.modules.tools.customerservice.entities.chat import ChatSession, ChatSessionStatus, ChatHistory, ChatConnection
from app.modules.tools.customerservice.repositories.iface.chat_session_repository import IChatSessionRepository
from app.modules.tools.customerservice.repositories.iface.chat_history_repository import IChatHistoryRepository
from app.modules.tools.customerservice.repositories.iface.chat_connection_repository import IChatConnectionRepository
from app.modules.tools.customerservice.services.chat_ai_service import ChatAIService
from app.modules.tools.customerservice.services.iface.chat_service import IChatService
from app.modules.tools.customerservice.services.dtos.chat_dto import (
    ChatSessionDto, ChatSessionListRequestDto, ChatSessionListItemDto,
    ChatHistoryListRequestDto, ChatHistoryDto, ChatMessageRequestDto,
    ChatMessageResultDto
)

class ChatService(IChatService):
    """智能客服服务实现"""
    
    def __init__(
        self,
        session_repository: IChatSessionRepository,
        history_repository: IChatHistoryRepository,
        connection_repository: IChatConnectionRepository,
        storage_service: Optional[IStorageService],
        chat_ai_service: ChatAIService,
        settings: Settings
    ):
        """
        初始化聊天服务
        
        Args:
            session_repository: 会话仓储
            history_repository: 历史记录仓储
            connection_repository: 连接仓储
            storage_service: 存储服务
            chat_ai_service: 聊天AI服务
            settings: 配置
        """
        self.session_repository = session_repository
        self.history_repository = history_repository
        self.connection_repository = connection_repository
        self.storage_service = storage_service
        self.chat_ai_service = chat_ai_service
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        
        # 从配置中获取上下文消息数量限制
        customer_service_config = settings.get_or_default("CustomerService", {})
        chat_config = customer_service_config.get("Chat", {})
        self.max_context_messages = int(chat_config.get("MaxContextMessages", 10))
    
    async def create_session_async(self, user_id: int, user_name: str) -> ChatSessionDto:
        """
        创建会话
        
        Args:
            user_id: 用户ID
            user_name: 用户姓名
            
        Returns:
            会话信息
        """
        try:
            session = ChatSession(
                user_id=user_id,
                user_name=user_name,
                session_name=f"{user_name}的会话", # 可以根据需要自定义会话名称
                status=ChatSessionStatus.ACTIVE.value
            )
            
            await self.session_repository.create_async(session)
            
            # 添加一条系统欢迎消息
            welcome_message = ChatHistory(
                session_id=session.id,
                role=ChatRoleType.ASSISTANT,
                content=f"您好，{user_name}！我是您的智能客服助手，有什么可以帮您的吗？",
            )
            
            await self.history_repository.add_async(welcome_message)
            
            # 构建结果
            result = ChatSessionDto(
                id=session.id,
                user_id=session.user_id,
                user_name=session.user_name,
                session_name=session.session_name,
                status=session.status,
                session_key=session.session_key,
                create_date=session.create_date,
                last_modify_date=session.last_modify_date,
                recent_history=[
                    ChatHistoryDto(
                        id=welcome_message.id,
                        session_id=welcome_message.session_id,
                        role=welcome_message.role,
                        content=welcome_message.content,
                        create_date=welcome_message.create_date
                    )
                ]
            )
            
            return result
        except Exception as ex:
            self.logger.error(f"创建会话失败，用户ID: {user_id}, 用户名: {user_name}, 错误: {str(ex)}")
            raise
    
    async def get_session_async(self, user_id: int, session_id: int) -> Optional[ChatSessionDto]:
        """
        获取会话
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            
        Returns:
            会话信息
        """
        try:
            session = await self.session_repository.get_by_id_async(session_id)
            if not session or session.user_id != user_id:
                raise BusinessException("会话不存在或无权限访问")
            
            # 获取最近的聊天记录
            recent_history = await self.history_repository.get_recent_history_async(session_id, 20)
            
            return self._map_session_to_dto(session, recent_history)
        except BusinessException:
            raise
        except Exception as ex:
            self.logger.error(f"获取会话失败，会话ID: {session_id}, 错误: {str(ex)}")
            raise
    
    async def get_session_by_key_async(self, session_key: str) -> Optional[ChatSessionDto]:
        """
        根据会话Key获取会话
        
        Args:
            session_key: 会话Key
            
        Returns:
            会话信息
        """
        try:
            session = await self.session_repository.get_by_session_key_async(session_key)
            if not session:
                return None
            
            # 获取最近的聊天记录
            recent_history = await self.history_repository.get_recent_history_async(session.id, 20)
            
            return self._map_session_to_dto(session, recent_history)
        except Exception as ex:
            self.logger.error(f"根据会话Key获取会话失败，会话Key: {session_key}, 错误: {str(ex)}")
            raise
    
    async def get_user_sessions_async(self, user_id: int, request: ChatSessionListRequestDto) -> PagedResultDto[ChatSessionListItemDto]:
        """
        获取用户的会话列表
        
        Args:
            user_id: 用户ID
            request: 分页请求
            
        Returns:
            分页会话列表
        """
        try:
            sessions, total_count = await self.session_repository.get_user_sessions_paginated_async(
                user_id, request.page_index, request.page_size, request.include_ended
            )
            
            result = []
            
            for session in sessions:
                # 获取最后一条消息
                last_messages = await self.history_repository.get_recent_history_async(session.id, 1)
                last_message_text = last_messages[0].content if last_messages else None
                last_message_time = last_messages[0].create_date if last_messages else None
                
                result.append(ChatSessionListItemDto(
                    id=session.id,
                    user_name=session.user_name,
                    session_name=session.session_name,
                    status=session.status,
                    session_key=session.session_key,
                    last_message=last_message_text,
                    last_message_time=last_message_time,
                    create_date=session.create_date,
                    last_modify_date=session.last_modify_date
                ))
            
            return PagedResultDto[ChatSessionListItemDto](
                items=result,
                total_count=total_count,
                page_index=request.page_index,
                page_size=request.page_size,
                total_pages=(total_count + request.page_size - 1) // request.page_size
            )
        except Exception as ex:
            self.logger.error(f"获取用户会话列表失败，用户ID: {user_id}, 错误: {str(ex)}")
            raise
    
    async def end_session_async(self, session_id: int) -> bool:
        """
        结束会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            操作结果
        """
        try:
            result = await self.session_repository.end_session_async(session_id)
            
            # 同时关闭所有连接
            await self.connection_repository.delete_session_connections_async(session_id)
            
            return result
        except Exception as ex:
            self.logger.error(f"结束会话失败，会话ID: {session_id}, 错误: {str(ex)}")
            raise
    
    async def get_session_history_async(self, user_id: int, request: ChatHistoryListRequestDto) -> PagedResultDto[ChatHistoryDto]:
        """
        获取会话历史记录
        
        Args:
            user_id: 用户ID
            request: 分页请求
            
        Returns:
            分页会话历史记录
        """
        try:
            session = await self.session_repository.get_by_id_async(request.session_id)
            if not session or session.user_id != user_id:
                raise BusinessException("会话不存在或无权限访问")
            
            items, total_count = await self.history_repository.get_session_history_paginated_async(
                request.session_id, request.page_index, request.page_size
            )
            
            result = PagedResultDto[ChatHistoryDto](
                items=[
                    ChatHistoryDto(
                        id=h.id,
                        session_id=h.session_id,
                        role=h.role,
                        content=h.content,
                        intent=h.intent,
                        call_datas=h.call_datas,
                        image_url=h.image_url,
                        create_date=h.create_date
                    ) for h in items
                ],
                total_count=total_count,
                page_index=request.page_index,
                page_size=request.page_size,
                total_pages=(total_count + request.page_size - 1) // request.page_size
            )
            
            return result
        except BusinessException:
            raise
        except Exception as ex:
            self.logger.error(f"获取会话历史记录失败，会话ID: {request.session_id}, 错误: {str(ex)}")
            raise
    
    async def send_message_async(self, user_id: int, request: ChatMessageRequestDto) -> ChatMessageResultDto:
        """
        发送消息
        
        Args:
            user_id: 用户ID
            request: 消息请求
            
        Returns:
            发送结果
        """
        try:
            session = await self.session_repository.get_by_id_async(request.session_id)
            if not session or session.user_id != user_id:
                raise BusinessException("会话不存在或无权限访问")
            
            # 获取历史记录
            history = await self.history_repository.get_recent_history_async(
                request.session_id, self.max_context_messages * 2
            )
            history_dtos = [
                ChatHistoryDto(
                    id=h.id,
                    session_id=h.session_id,
                    role=h.role,
                    content=h.content,
                    intent=h.intent,
                    call_datas=h.call_datas,
                    image_url=h.image_url,
                    create_date=h.create_date
                ) for h in history
            ]
            
            # 记录用户消息
            user_message = ChatHistory(
                session_id=request.session_id,
                role=ChatRoleType.USER,
                content=request.content,
            )
            await self.history_repository.add_async(user_message)
            
            # 识别用户意图
            intent_result = await self.chat_ai_service.analysis_intent_async(
                user_id,
                history_dtos,
                request.content or ""
            )
            call_datas = "" if not intent_result.id_datas else ",".join(intent_result.id_datas)
            
            # 记录意图到用户消息
            user_message.intent = intent_result.intent
            await self.history_repository.update_async(user_message)
            
            # 生成回复
            reply = await self.chat_ai_service.generate_reply_async(
                user_message.content or "",
                history_dtos,
                intent_result.intent or "",
                intent_result.context
            )
            
            # 记录AI回复
            assistant_message = ChatHistory(
                session_id=request.session_id,
                role=ChatRoleType.ASSISTANT,
                content=reply,
                intent=intent_result.intent,
                call_datas=call_datas,
            )
            await self.history_repository.add_async(assistant_message)
            
            # 更新会话最后修改时间
            session.last_modify_date = datetime.now()
            await self.session_repository.update_async(session)
            
            return ChatMessageResultDto(
                message_id=assistant_message.id,
                session_id=request.session_id,
                reply=reply,
                intent=intent_result.intent,
                call_datas=call_datas,
                success=True
            )
        except Exception as ex:
            self.logger.error(f"发送消息失败，会话ID: {request.session_id}，错误: {str(ex)}")
            return ChatMessageResultDto(
                session_id=request.session_id,
                success=False,
                error_message=f"发送消息失败: {str(ex)}"
            )
    
    async def send_image_async(self, user_id: int, session_id: int, image: UploadFile) -> ChatMessageResultDto:
        """
        发送图片消息
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            image: 图片文件
            
        Returns:
            发送结果
        """
        try:
            session = await self.session_repository.get_by_id_async(session_id)
            if not session or session.user_id != user_id:
                raise BusinessException("会话不存在或无权限访问")
            
            # 上传图片
            if not self.storage_service:
                raise BusinessException("存储服务未配置")
                
            file_key = f"customerservice/chat/{session_id}/{datetime.now().strftime('%Y%m%d%H%M%S')}{image.filename}"
            content_type = image.content_type or "application/octet-stream"
            
            # 上传图片
            image_url = await self.storage_service.upload_async(image.file, file_key, content_type)
            
            # 分析图片内容
            image_analysis = await self.chat_ai_service.analyze_image_async(image_url)
            
            # 记录用户图片消息
            user_message = ChatHistory(
                session_id=session_id,
                role=ChatRoleType.USER,
                content=f"[图片] {image_analysis.description}",
                image_url=image_url,
            )
            await self.history_repository.add_async(user_message)
            
            # 获取历史记录
            history = await self.history_repository.get_recent_history_async(
                session_id, self.max_context_messages * 2
            )
            history_dtos = [
                ChatHistoryDto(
                    id=h.id,
                    session_id=h.session_id,
                    role=h.role,
                    content=h.content,
                    intent=h.intent,
                    call_datas=h.call_datas,
                    image_url=h.image_url,
                    create_date=h.create_date
                ) for h in history
            ]
            
            # 识别用户意图
            intent_result = await self.chat_ai_service.analysis_intent_async(
                user_id,
                history_dtos,
                f"我发送了一张图片：{image_analysis.description}"
            )
            call_datas = "" if not intent_result.id_datas else ",".join(intent_result.id_datas)
            
            # 记录意图到用户消息
            user_message.intent = intent_result.intent
            await self.history_repository.update_async(user_message)
            
            # 构建提示消息，包含图片分析信息
            prompt = f"用户发送了一张图片。图片分析结果：{image_analysis.description}。"
            
            # 生成回复
            reply = await self.chat_ai_service.generate_reply_async(
                prompt,
                history_dtos,
                intent_result.intent or "",
                intent_result.context
            )
            
            # 记录AI回复
            assistant_message = ChatHistory(
                session_id=session_id,
                role=ChatRoleType.ASSISTANT,
                content=reply,
                intent=intent_result.intent,
                call_datas=call_datas,
            )
            await self.history_repository.add_async(assistant_message)
            
            # 更新会话最后修改时间
            session.last_modify_date = datetime.now()
            await self.session_repository.update_async(session)
            
            return ChatMessageResultDto(
                message_id=assistant_message.id,
                session_id=session_id,
                reply=reply,
                intent=intent_result.intent,
                call_datas=call_datas,
                success=True
            )
        except Exception as ex:
            self.logger.error(f"发送图片消息失败，会话ID: {session_id}，错误: {str(ex)}")
            return ChatMessageResultDto(
                session_id=session_id,
                success=False,
                error_message=f"发送图片消息失败: {str(ex)}"
            )
    
    async def establish_connection_async(self, session_id: int, connection_id: str, client_type: str) -> bool:
        """
        建立实时连接
        
        Args:
            session_id: 会话ID
            connection_id: 连接ID
            client_type: 客户端类型
            
        Returns:
            连接结果
        """
        try:
            connection = ChatConnection(
                session_id=session_id,
                connection_id=connection_id,
                client_type=client_type,
                is_active=1,
                last_active_time=datetime.now()
            )
            
            return await self.connection_repository.add_async(connection)
        except Exception as ex:
            self.logger.error(f"建立实时连接失败，会话ID: {session_id}, 连接ID: {connection_id}, 错误: {str(ex)}")
            raise
    
    async def close_connection_async(self, connection_id: str) -> bool:
        """
        关闭实时连接
        
        Args:
            connection_id: 连接ID
            
        Returns:
            操作结果
        """
        try:
            return await self.connection_repository.delete_async(connection_id)
        except Exception as ex:
            self.logger.error(f"关闭实时连接失败，连接ID: {connection_id}, 错误: {str(ex)}")
            raise
    
    async def keep_connection_alive_async(self, connection_id: str) -> bool:
        """
        更新连接活跃状态
        
        Args:
            connection_id: 连接ID
            
        Returns:
            操作结果
        """
        try:
            return await self.connection_repository.update_last_active_time_async(connection_id)
        except Exception as ex:
            self.logger.error(f"更新连接活跃状态失败，连接ID: {connection_id}, 错误: {str(ex)}")
            raise
    
    def _map_session_to_dto(self, session: ChatSession, history: List[ChatHistory]) -> ChatSessionDto:
        """
        将会话实体转换为DTO
        
        Args:
            session: 会话实体
            history: 历史记录
            
        Returns:
            会话DTO
        """
        return ChatSessionDto(
            id=session.id,
            user_id=session.user_id,
            user_name=session.user_name,
            session_name=session.session_name,
            status=session.status,
            session_key=session.session_key,
            create_date=session.create_date,
            last_modify_date=session.last_modify_date,
            recent_history=[
                ChatHistoryDto(
                    id=h.id,
                    session_id=h.session_id,
                    role=h.role,
                    content=h.content,
                    intent=h.intent,
                    call_datas=h.call_datas,
                    image_url=h.image_url,
                    create_date=h.create_date
                ) for h in (history or [])
            ]
        )