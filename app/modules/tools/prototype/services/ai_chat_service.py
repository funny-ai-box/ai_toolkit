# app/modules/tools/prototype/services/ai_chat_service.py
import re
from typing import List, Optional, Tuple, Dict, Any, Callable, AsyncGenerator
import json
import logging
import datetime
from fastapi import UploadFile

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai.chat.base import IChatAIService, InputMessage
from app.core.ai.chat.factory import ChatAIProviderType, get_chat_ai_service

from app.core.ai.dtos import ChatRoleType
from app.core.config.settings import settings
from app.core.exceptions import BusinessException, ForbiddenException
# app/modules/tools/prototype/services/ai_chat_service.py (continued)
from app.core.storage.base import IStorageService, StorageProviderType

from app.modules.base.prompts.services import PromptTemplateService
from app.modules.tools.prototype.config import prototype_config
from app.modules.tools.prototype.constants import (
    PrototypeMessageType, PrototypePageStatus, PrototypeSessionStatus, CurrentStageType
)
from app.modules.tools.prototype.dtos import (
    AIChatRequestDto, MessageDto, SessionStageDto, PageStructureDto, PageInfoDto
)
from app.modules.tools.prototype.models import (
    PrototypeSession, PrototypePage, PrototypePageHistory, PrototypeMessage, PrototypeResource
)
from app.modules.tools.prototype.repositories import (
    PrototypeSessionRepository, PrototypePageRepository, 
    PrototypePageHistoryRepository, PrototypeMessageRepository, 
    PrototypeResourceRepository
)
from app.modules.tools.prototype.services.ai_prompt_service import AIPromptService

def json_serialize(obj):
    """Convert object to JSON string"""
    import json
    return json.dumps(obj, ensure_ascii=False, default=lambda o: o.__dict__)

def json_deserialize(json_str, target_class):
    """Convert JSON string to object of target_class"""
    import json
    data = json.loads(json_str)
    return target_class(**data)
class AIChatService:
    """AI对话服务实现"""
    
    def __init__(
        self,
        db: AsyncSession,
        ai_service: IChatAIService,
        storage_service: IStorageService,
        prompt_service: PromptTemplateService,
        session_repository: PrototypeSessionRepository,
        page_repository: PrototypePageRepository,
        page_history_repository: PrototypePageHistoryRepository,
        message_repository: PrototypeMessageRepository,
        resource_repository: PrototypeResourceRepository,
        logger: Optional[logging.Logger] = None
    ):
        """
        初始化
        
        Args:
            db: 数据库会话
            ai_service: AI服务
            storage_service: 存储服务
            prompt_service: 提示词模板服务
            session_repository: 会话仓储
            page_repository: 页面仓储
            page_history_repository: 页面历史版本仓储
            message_repository: 消息仓储
            resource_repository: 资源仓储
            logger: 日志记录器
        """
        self.db = db
        self.ai_service = ai_service
        self.storage_service = storage_service
        self.ai_prompt_service = AIPromptService(prompt_service)
        self.session_repository = session_repository
        self.page_repository = page_repository
        self.page_history_repository = page_history_repository
        self.message_repository = message_repository
        self.resource_repository = resource_repository
        self.logger = logger or logging.getLogger(__name__)
        self.chat_ai_provider_type = prototype_config.chat_ai_provider_type
    
    async def send_ai_chat_async(
    self, 
    user_id: int, 
    request: AIChatRequestDto, 
    on_chunk_received: Optional[Callable[[str], str]] = None
) -> MessageDto:
      """
      发送AI对话消息
      
      Args:
            user_id: 用户ID
            request: AI对话请求
            on_chunk_received: 数据块接收回调，接收数据块并返回事件字符串
                  
      Returns:
            AI回复消息DTO
      """
      try:
            # 检查用户权限
            session = await self.session_repository.get_by_id_async(request.session_id)
            if session is None or session.user_id != user_id:
                  raise ForbiddenException("无权访问该会话")
            
            # 如果是首次聊天且会话名称是默认的"新的会话"，则根据用户消息更新会话名称
            if session.name == "新的会话":
                  await self.session_repository.update_session_name_from_first_message_async(
                  request.session_id, request.user_message
                  )
            
            if session.is_generating_code:
                  raise BusinessException("我正在编写页面代码中，请稍候跟我对话...")
            
            ai_message_id, ai_response = await self._ai_generate_flow_async(
                  request, on_chunk_received
            )
            
            # 创建回复DTO
            response_dto = MessageDto(
                  id=ai_message_id,
                  session_id=request.session_id,
                  message_type=PrototypeMessageType.AI,
                  message_type_description="AI",
                  content=ai_response,
                  create_date=datetime.datetime.now()
            )
            
            return response_dto
            
      except Exception as ex:
            if isinstance(ex, ForbiddenException):
                  raise
            
            self.logger.error(f"发送AI对话消息失败: {str(ex)}")
            raise BusinessException(f"发送AI对话消息失败: {str(ex)}")
    
    async def upload_reference_image_async(
        self, user_id: int, session_id: int, file: UploadFile
    ) -> Tuple[int, str]:
        """
        上传参考图片
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            file: 图片文件
            
        Returns:
            附件ID和URL
        """
        try:
            # 检查用户权限
            session = await self.session_repository.get_by_id_async(session_id)
            if session is None or session.user_id != user_id:
                raise ForbiddenException("无权访问该会话")
            
            # 检查文件类型
            file_extension = file.filename.split(".")[-1].lower() if file.filename and "." in file.filename else ""
            allowed_extensions = ["jpg", "jpeg", "png", "gif", "webp"]
            
            if file_extension not in allowed_extensions:
                raise BusinessException("不支持的文件类型，仅支持JPG、PNG、GIF和WEBP格式")
            
            # 生成文件名
            file_name = f"prototype/reference/{session_id}/{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.{file_extension}"
            
            # 读取文件内容
            file_content = await file.read()
            
            # 上传文件
            file_url = await self.storage_service.upload_async(
                file_content, file_name, file.content_type or f"image/{file_extension}"
            )
            
            # 构建保存的实体
            resource = PrototypeResource(
                user_id=user_id,
                session_id=session_id,
                name=file.filename,
                resource_type="image",
                url=file_url
            )
            
            # Gemini需要上传到Google，不能用外部图片
            if self.chat_ai_provider_type == ChatAIProviderType.GEMINI:
                # 在实际实现中应有对应逻辑处理
                pass
            
            # 添加资源记录
            file_id = await self.resource_repository.add_async(resource)
            
            return file_id, file_url
            
        except Exception as ex:
            if isinstance(ex, ForbiddenException):
                raise
            
            self.logger.error(f"上传参考图片失败: {str(ex)}")
            raise BusinessException(f"上传参考图片失败: {str(ex)}")
    
    async def _ai_generate_flow_async(
        self,
        request: AIChatRequestDto,
        on_chunk_received: Optional[Callable[[str], str]] = None,
        cancel_token: Any = None
    ) -> Tuple[int, str]:
        """
        AI生成内容的流程
        
        Args:
            request: AI对话请求
            on_chunk_received: 数据块接收回调
            cancel_token: 取消令牌
            
        Returns:
            (消息ID, AI回复内容)
        """
        # 获取会话信息
        session = await self.session_repository.get_by_id_async(request.session_id)
        
        # 构建发送给AI的消息体
        messages = await self._build_send_messages(session, request)
        
        # 调用AI服务获取回复
        ai_response = ""
        if on_chunk_received:
            # 流式生成
            async for chunk in self.ai_service.streaming_chat_completion_async(messages):
                if on_chunk_received:
                    on_chunk_received(chunk)
                ai_response += chunk
        else:
            # 一次性生成
            ai_response = await self.ai_service.chat_completion_async(messages)
        
        # 存储AI回复
        ai_message_entity = PrototypeMessage(
            session_id=request.session_id,
            user_id=session.user_id,
            message_type=PrototypeMessageType.AI,
            content=ai_response
        )
        ai_message_id = await self.message_repository.add_async(ai_message_entity)
        
        # 从AI回复中提取阶段信息
        stage_data = self._extract_stage_info(ai_response)
        
        # 更新会话状态，与当前阶段保持一致
        await self._update_session_status_based_on_stage(session.id, stage_data.current_stage)
        
        try:
            # 处理特定阶段的自动操作
            if stage_data.current_stage == CurrentStageType.COLLECTING:
                await self._deal_stage_collecting(session, stage_data, ai_response, on_chunk_received, cancel_token)
            elif stage_data.current_stage == CurrentStageType.ANALYZING:
                await self._deal_stage_analyzing(session, stage_data, ai_response, on_chunk_received, cancel_token)
            elif stage_data.current_stage == CurrentStageType.DESIGNING:
                await self._deal_stage_designing(session, stage_data, ai_response)
            elif stage_data.current_stage == CurrentStageType.GENERATING:
                await self._deal_stage_generating(session, stage_data, ai_response)
            elif stage_data.current_stage == CurrentStageType.EDITING:
                await self._deal_stage_editing(session, stage_data, ai_response)
            elif stage_data.current_stage == CurrentStageType.COMPLETED:
                await self._deal_stage_completed(session, stage_data, ai_response)
        except Exception as ex:
            self.logger.error(f"自动处理下一步时出错: {str(ex)}")
        
        return ai_message_id, ai_response
    
    async def _build_send_messages(
        self, session: PrototypeSession, request: AIChatRequestDto
    ) -> List[InputMessage]:
        """
        构建发送给AI的消息体
        
        Args:
            session: 会话信息
            request: AI对话请求
            
        Returns:
            消息体列表
        """
        # 构建AI请求消息
        messages = [
            # 全局系统指令
            InputMessage(ChatRoleType.SYSTEM, await self.ai_prompt_service.global_system_prompt())
        ]
        
        # 添加当前会话状态相关的提示词
        messages.append(InputMessage(ChatRoleType.SYSTEM, await self._get_stage_prompt(session)))
        
        # 如果已有需求描述和页面结构，一并发送
        if session.requirements:
            messages.append(InputMessage(ChatRoleType.SYSTEM, f"用户之前确认的需求描述: {session.requirements}"))
        
        if session.page_structure:
            messages.append(InputMessage(ChatRoleType.SYSTEM, f"用户之前确认的页面结构: {session.page_structure}"))
        
        # 获取会话历史消息
        recent_messages = await self._get_chat_history_async(request.session_id)
        # 添加对话历史
        messages.extend(await self._convert_chat_history_async(recent_messages))
        
        # 标记是否为内部系统消息（不需要存储到消息历史中）
        is_system_message = request.user_message.startswith("$$SYSTEM_") if request.user_message else False
        
        # 如果是系统内部"继续"消息
        if request.user_message == "$$SYSTEM_CONTINUE$$":
            messages.append(InputMessage(ChatRoleType.USER, "请继续"))
        # 如果是系统内部"生成页面"消息
        elif request.user_message and request.user_message.startswith("$$SYSTEM_GENERATE_PAGE:"):
            page_info = request.user_message[len("$$SYSTEM_GENERATE_PAGE:"):]
            messages.append(InputMessage(ChatRoleType.SYSTEM, f"当前目标页面：{page_info}"))
            messages.append(InputMessage(ChatRoleType.USER, f"请生成{page_info}页面的代码"))
        # 如果是系统内部"继续生成页面"消息
        elif request.user_message == "$$SYSTEM_CONTINUE_PAGE$$":
            pages = await self.page_repository.get_by_session_id_async(session.id)
            incomplete_page = next((p for p in pages if not p.is_complete and p.partial_content), None)
            
            if incomplete_page:
                messages.append(InputMessage(ChatRoleType.SYSTEM, await self.ai_prompt_service.global_system_prompt()))
                messages.append(InputMessage(
                    ChatRoleType.SYSTEM,
                    f'页面 "{incomplete_page.name}" 的代码输出被截断，请**接着剩下部分继续输出 HTML，不要重复前面的内容**，不要从头开始生成。'
                ))
                messages.append(InputMessage(ChatRoleType.USER, "继续生成页面 HTML，接着上次的部分输出，不要重复。"))
        # 否则添加用户输入
        elif not is_system_message:
            messages.append(InputMessage(ChatRoleType.USER, request.user_message))
        
        # 非系统内部消息存储用户输入，注意需要在处理完历史消息后再写入，不然会多出消息
        if not is_system_message:
            img_ids = ""
            img_urls = ""
            if request.attachments:
                resources = await self.resource_repository.get_by_ids_async(request.attachments)
                if resources:
                    img_ids = ",".join(str(r.id) for r in resources)
                    img_urls = ",".join(r.url for r in resources if r.url)
            
            user_message = PrototypeMessage(
                session_id=request.session_id,
                user_id=session.user_id,
                message_type=PrototypeMessageType.USER,
                content=request.user_message,
                attachment_ids=img_ids,
                attachment_urls=img_urls,
            )
            await self.message_repository.add_async(user_message)
        
        # 根据图片附件添加额外内容
        # 如果有图片，则加入到会话上下文中
        await self._add_image_source_to_messages(request.attachments or [], messages)
        
        return messages
    
    async def _get_chat_history_async(self, session_id: int) -> List[PrototypeMessage]:
        """
        获取聊天历史
        
        Args:
            session_id: 会话ID
            
        Returns:
            聊天消息列表
        """
        messages = await self.message_repository.get_by_session_id_async(session_id)
        
        # 只获取最近的20条消息
        return [
            m for m in messages
            if m.message_type in (PrototypeMessageType.USER, PrototypeMessageType.AI)
        ][-20:] if len(messages) > 20 else [
            m for m in messages
            if m.message_type in (PrototypeMessageType.USER, PrototypeMessageType.AI)
        ]
    
    async def _convert_chat_history_async(self, recent_messages: List[PrototypeMessage]) -> List[InputMessage]:
        """
        将聊天历史转为ChatMessage
        
        Args:
            recent_messages: 聊天历史
            
        Returns:
            输入消息列表
        """
        chat_messages = []
        
        for message in recent_messages:
            if message.message_type == PrototypeMessageType.USER:
                attachment_ids = []
                if message.attachment_ids:
                    ids = message.attachment_ids.split(",")
                    for id_str in ids:
                        try:
                            attachment_ids.append(int(id_str))
                        except ValueError:
                            pass
                
                if not attachment_ids:  # 没有图片
                    chat_messages.append(InputMessage(ChatRoleType.USER, message.content or ""))
                else:
                    # 如果有图片，则加入到会话上下文中
                    await self._add_image_source_to_messages(attachment_ids, chat_messages)
            else:
                chat_messages.append(InputMessage(ChatRoleType.ASSISTANT, message.content or ""))
        
        return chat_messages
    
    async def _add_image_source_to_messages(self, attachments: List[int], messages: List[InputMessage]) -> None:
        """
        如果有图片，则加入到会话上下文中
        
        Args:
            attachments: 附件ID列表
            messages: 消息列表
        """
        if attachments:
            resources = await self.resource_repository.get_by_ids_async(attachments)
            if resources:
                  image_urls = []
                  for resource in resources:
                        if self.chat_ai_provider_type == ChatAIProviderType.GEMINI:
                              image_urls.append(resource.gemini_url)
                        else:
                              image_urls.append(resource.url)
            
                
                  messages.append(InputMessage.from_text_and_image_urls(
    role=ChatRoleType.USER,
    text="我上传了参考图片，请结合图片内容来设计。",
    image_urls=image_urls,
    media_type="image/jpeg"  # Adjust this based on your image types
))
    
    async def _get_stage_prompt(self, session: PrototypeSession) -> str:
        """
        根据会话状态获取相应阶段的提示词
        
        Args:
            session: 会话实体
            
        Returns:
            阶段提示词
        """
        if session.status == PrototypeSessionStatus.REQUIREMENT_GATHERING:
            return await self.ai_prompt_service.collecting_prompt()
        elif session.status == PrototypeSessionStatus.REQUIREMENT_ANALYZING:
            return await self.ai_prompt_service.analyzing_prompt()
        elif session.status == PrototypeSessionStatus.STRUCTURE_CONFIRMATION:
            return await self.ai_prompt_service.designing_prompt()
        elif session.status == PrototypeSessionStatus.PAGE_GENERATION:
            return "当前阶段：Generating\n请生成当前目标页面的完整代码。"
        elif session.status == PrototypeSessionStatus.COMPLETED:
            return await self.ai_prompt_service.completed_prompt()
        else:
            return await self.ai_prompt_service.collecting_prompt()  # 默认使用需求收集阶段提示词
    
    def _extract_stage_info(self, ai_response: str) -> SessionStageDto:
        """
        从AI回复中提取阶段信息
        
        Args:
            ai_response: AI回复
            
        Returns:
            会话阶段信息
        """
        current_stage = CurrentStageType.COLLECTING
        current_stage_str = ""
        next_stage_str = ""
        next_stage = CurrentStageType.NONE
        
        current_page = ""
        modified_page = ""
        
        # 提取当前阶段
        stage_match = re.search(r"<STAGE:(\w+)>", ai_response)
        if stage_match and len(stage_match.groups()) > 0:
            current_stage_str = stage_match.group(1).strip()
            try:
                current_stage = CurrentStageType[current_stage_str.upper()]
            except (KeyError, ValueError):
                pass
        
        # 提取下一阶段（如果有）
        next_stage_match = re.search(r"<NEXT_STAGE:(\w+)>", ai_response)
        if next_stage_match and len(next_stage_match.groups()) > 0:
            next_stage_str = next_stage_match.group(1).strip()
            try:
                next_stage = CurrentStageType[next_stage_str.upper()]
            except (KeyError, ValueError):
                pass
        
        # 提取当前生成的页面（仅在Generating阶段）
        if current_stage == CurrentStageType.GENERATING:
            current_page_match = re.search(r"<CURRENT_PAGE:([^>]+)>", ai_response)
            if current_page_match and len(current_page_match.groups()) > 0:
                current_page = current_page_match.group(1).strip()
        
        # 提取被修改的页面和组件（仅在Editing阶段）
        if current_stage == CurrentStageType.EDITING:
            modified_page_match = re.search(r"<MODIFIED_PAGE:([^>]+)>", ai_response)
            if modified_page_match and len(modified_page_match.groups()) > 0:
                modified_page = modified_page_match.group(1).strip()
        
        return SessionStageDto(
            current_stage=current_stage,
            next_stage=next_stage,
            current_page=current_page,
            modified_page=modified_page
        )
    
    async def _update_session_status_based_on_stage(self, session_id: int, stage: CurrentStageType) -> bool:
        """
        根据当前阶段更新会话状态
        
        Args:
            session_id: 会话ID
            stage: 当前阶段
            
        Returns:
            操作结果
        """
        status_mapping = {
            CurrentStageType.COLLECTING: PrototypeSessionStatus.REQUIREMENT_GATHERING,
            CurrentStageType.ANALYZING: PrototypeSessionStatus.REQUIREMENT_ANALYZING,
            CurrentStageType.DESIGNING: PrototypeSessionStatus.STRUCTURE_CONFIRMATION,
            CurrentStageType.GENERATING: PrototypeSessionStatus.PAGE_GENERATION,
            CurrentStageType.COMPLETED: PrototypeSessionStatus.COMPLETED
        }
        
        if stage in status_mapping:
            return await self.session_repository.update_status_async(session_id, status_mapping[stage])
        
        return False
    
    async def _deal_stage_collecting(
        self,
        session: PrototypeSession,
        stage_data: SessionStageDto,
        ai_response: str,
        on_chunk_received: Optional[Callable[[str], None]] = None,
        cancel_token: Any = None
    ) -> None:
        """
        处理收集阶段的动作
        
        Args:
            session: 会话
            stage_data: 阶段数据
            ai_response: AI回复
            on_chunk_received: 数据块接收回调
            cancel_token: 取消令牌
        """
        # 如果明确指示进入分析阶段，自动进行处理
        if stage_data.next_stage == CurrentStageType.ANALYZING:
            # 添加系统消息
            await self._add_system_message_async(session.user_id, session.id, "需求收集完成，开始需求分析")
            
            # 需要将状态改为需求分析（从需求收集=>需求分析）
            await self._update_session_status_based_on_stage(session.id, CurrentStageType.ANALYZING)
            
            # 自动发送继续消息，进入需求分析阶段
            await self._ai_generate_flow_async(
                AIChatRequestDto(
                    session_id=session.id,
                    user_message="$$SYSTEM_CONTINUE$$"
                ),
                on_chunk_received,
                cancel_token
            )
    
    async def _deal_stage_analyzing(
        self,
        session: PrototypeSession,
        stage_data: SessionStageDto,
        ai_response: str,
        on_chunk_received: Optional[Callable[[str], None]] = None,
        cancel_token: Any = None
    ) -> None:
        """
        处理分析阶段的动作
        
        Args:
            session: 会话
            stage_data: 阶段数据
            ai_response: AI回复
            on_chunk_received: 数据块接收回调
            cancel_token: 取消令牌
        """
        # 提取需求分析结果
        requirement_pattern = r"```需求分析结果\s*([\s\S]*?)\s*```"
        requirement_match = re.search(requirement_pattern, ai_response)
        requirement = ""
        if requirement_match and len(requirement_match.groups()) > 0:
            requirement = requirement_match.group(1).strip()
        else:
            requirement = ai_response
        
        # 无论是否有下一阶段标记，都保存需求分析结果
        await self.session_repository.update_requirements_async(session.id, requirement)
        
        # 如果明确指示进入设计阶段，自动进行处理
        if stage_data.next_stage == CurrentStageType.DESIGNING:
            # 添加系统消息
            await self._add_system_message_async(session.user_id, session.id, "需求分析完成，开始设计页面结构")
            
            # 需要将状态改为页面设计（从需求分析=>页面设计）
            await self._update_session_status_based_on_stage(session.id, CurrentStageType.DESIGNING)
            
            # 自动发送继续消息，进入页面结构设计阶段
            await self._ai_generate_flow_async(
                AIChatRequestDto(
                    session_id=session.id,
                    user_message="$$SYSTEM_CONTINUE$$"
                ),
                on_chunk_received,
                cancel_token
            )
    
    async def _deal_stage_designing(
        self,
        session: PrototypeSession,
        stage_data: SessionStageDto,
        ai_response: str
    ) -> None:
        """
        处理设计阶段的动作
        
        Args:
            session: 会话
            stage_data: 阶段数据
            ai_response: AI回复
        """
        # 尝试提取JSON结构
        page_structure = self._extract_json_from_markdown(ai_response)
        if page_structure:
            try:
                # 验证JSON有效性
                structure_obj = json_deserialize(page_structure, PageStructureDto)
                if structure_obj and structure_obj.pages:
                    # 保存页面结构
                    await self.session_repository.update_page_structure_async(session.id, page_structure)
                    
                    # 如果明确指示进入生成阶段，自动进行处理
                    if stage_data.next_stage == CurrentStageType.GENERATING:
                        # 更新会话状态
                        await self._update_session_status_based_on_stage(session.id, CurrentStageType.GENERATING)
                        
                        # 添加系统消息
                        await self._add_system_message_async(
                            session.user_id, session.id,
                            f"页面结构设计完成，共 {len(structure_obj.pages)} 个页面，开始生成页面代码"
                        )
                        
                        # 异步开始生成页面，那么此时的会话需要锁定，用户不能发送消息
                        # 在实际生产环境中，最好使用消息队列或后台任务系统
                        import asyncio
                        asyncio.create_task(self._generate_all_page_async(session.user_id, session.id, structure_obj))
            except Exception as ex:
                self.logger.error(f"解析页面结构失败: {str(ex)}")
                await self._add_system_message_async(session.user_id, session.id, f"解析页面结构失败: {str(ex)}")
    
    async def _deal_stage_generating(
        self,
        session: PrototypeSession,
        stage_data: SessionStageDto,
        ai_response: str
    ) -> None:
        """
        处理代码生成阶段的动作
        
        Args:
            session: 会话
            stage_data: 阶段数据
            ai_response: AI回复
        """
        # 如果在生成阶段已标记了下一阶段为完成，处理完整流程结束
        if stage_data.next_stage == CurrentStageType.COMPLETED:
            # 更新会话状态为已完成
            await self.session_repository.update_status_async(session.id, PrototypeSessionStatus.COMPLETED)
            
            # 添加系统消息
            await self._add_system_message_async(
                session.user_id, session.id,
                "所有页面已生成完成，原型设计已完成。您可以预览原型或继续修改页面。"
            )
    
    async def _deal_stage_editing(
        self,
        session: PrototypeSession,
        stage_data: SessionStageDto,
        ai_response: str
    ) -> None:
        """
        处理代码编辑阶段的动作
        
        Args:
            session: 会话
            stage_data: 阶段数据
            ai_response: AI回复
        """
        # 如果是编辑阶段且已明确指出修改的页面，保存修改
        if stage_data.modified_page:
            try:
                # 查找被修改的页面
                # app/modules/tools/prototype/services/ai_chat_service.py (continued)
                # 查找被修改的页面
                pages = await self.page_repository.get_by_session_id_async(session.id)
                page = next((p for p in pages if p.name and p.name.lower() == stage_data.modified_page.lower()), None)
                
                if page:
                    # 提取更新后的代码
                    updated_code = self._extract_code_from_markdown(ai_response)
                    if updated_code:
                        # 保存历史版本
                        page_history = PrototypePageHistory(
                            page_id=page.id,
                            session_id=session.id,
                            user_id=session.user_id,
                            content=page.content,
                            version=page.version,
                            change_description=f"修改页面 '{stage_data.modified_page}' 前的版本"
                        )
                        await self.page_history_repository.add_async(page_history)
                        
                        # 更新页面内容
                        await self.page_repository.update_content_async(page.id, updated_code)
                        await self.page_repository.update_status_async(page.id, PrototypePageStatus.MODIFIED)
                        
                        # 添加系统消息
                        await self._add_system_message_async(
                            session.user_id, session.id,
                            f"页面 {stage_data.modified_page} 的已修改"
                        )
            except Exception as ex:
                self.logger.error(f"保存修改的页面时出错: {str(ex)}")
                await self._add_system_message_async(session.user_id, session.id, f"保存修改的页面时出错: {str(ex)}")
    
    async def _deal_stage_completed(
        self,
        session: PrototypeSession,
        stage_data: SessionStageDto,
        ai_response: str
    ) -> None:
        """
        处理完成阶段的动作
        
        Args:
            session: 会话
            stage_data: 阶段数据
            ai_response: AI回复
        """
        if stage_data.next_stage == CurrentStageType.EDITING:
            # 从完成阶段返回到编辑阶段
            await self._add_system_message_async(session.user_id, session.id, "开始修改页面")
    
    async def _generate_all_page_async(
        self, user_id: int, session_id: int, page_structure: PageStructureDto
    ) -> bool:
        """
        生成所有页面
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            page_structure: 页面结构
            
        Returns:
            操作结果
        """
        try:
            # 锁定正在编写代码过程中
            await self.session_repository.lock_generating_code_async(session_id, True)
            
            # 遍历生成每个页面
            for i, page_info in enumerate(page_structure.pages):
                # 稍等片刻，然后生成下一个页面
                import asyncio
                await asyncio.sleep(1)
                await self._generate_next_page_async(user_id, session_id, page_structure, i)
            
            # 更新会话状态为已完成
            await self.session_repository.update_status_async(session_id, PrototypeSessionStatus.COMPLETED)
            
            # 添加完成消息
            await self._add_system_message_async(
                user_id, session_id,
                "所有页面已生成完成，原型设计已完成。您可以预览原型或继续修改页面。"
            )
            
            return True
        except Exception as ex:
            self.logger.error(f"生成页面时出错: {str(ex)}")
            await self._add_system_message_async(user_id, session_id, f"生成页面时出错: {str(ex)}")
            return False
        finally:
            # 取消锁定正在编写代码过程中
            await self.session_repository.lock_generating_code_async(session_id, False)
    
    async def _generate_next_page_async(
        self, user_id: int, session_id: int, page_structure: PageStructureDto, page_index: int
    ) -> None:
        """
        生成下一个HTML页面
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            page_structure: 页面结构
            page_index: 页面索引
        """
        # 获取要生成的页面信息
        page_info = page_structure.pages[page_index]
        
        # 构建代码生成阶段的消息
        messages = await self._build_generate_messages(user_id, session_id, page_structure, page_index)
        
        # 发送生成请求
        ai_response = await self.ai_service.chat_completion_async(messages)
        
        # 提交AI的响应中的代码并保存
        await self._extract_ai_generate_message_code(user_id, session_id, page_structure, page_index, ai_response)
    
    async def _build_generate_messages(
        self, user_id: int, session_id: int, page_structure: PageStructureDto, page_index: int
    ) -> List[InputMessage]:
        """
        构建代码生成阶段的消息
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            page_structure: 页面结构
            page_index: 页面索引
            
        Returns:
            消息列表
        """
        page_info = page_structure.pages[page_index]
        
        # 添加系统消息
        await self._add_system_message_async(
            user_id, session_id,
            f"开始生成页面 ({page_index + 1}/{len(page_structure.pages)}): {page_info.name}"
        )
        
        # 获取设计系统信息
        design_system_info = self._extract_design_system_info(page_structure)
        
        # 构建AI请求消息
        messages = [
            # 全局系统指令
            InputMessage(ChatRoleType.SYSTEM, await self.ai_prompt_service.global_system_prompt()),
            
            # 强调当前任务
            InputMessage(ChatRoleType.SYSTEM, f"你正在生成原型的第 {page_index+1}/{len(page_structure.pages)} 个页面: {page_info.name}"),
            
            # 指定渲染技术
            InputMessage(ChatRoleType.SYSTEM, "请使用HTML+CSS创建页面，不要使用React或JavaScript框架。使用TailwindCSS提供美观的UI。"),
            
            # 强调必须添加状态标记
            InputMessage(ChatRoleType.SYSTEM, f"生成代码后必须在回复的最后一行添加:<STAGE:Generating><CURRENT_PAGE:{page_info.name}>")
        ]
        
        # 添加页面结构上下文
        messages.append(InputMessage(ChatRoleType.SYSTEM, f"完整页面结构: {json_serialize(page_structure)}"))
        
        # 获取会话需求分析结果
        session = await self.session_repository.get_by_id_async(session_id)
        if session and session.requirements:
            messages.append(InputMessage(ChatRoleType.SYSTEM, f"需求分析结果: {session.requirements}"))
        
        # 如果有其他已生成页面，添加作为参考
        existing_pages = await self.page_repository.get_by_session_id_async(session_id)
        generated_pages = [
            p for p in existing_pages
            if p.status == PrototypePageStatus.GENERATED and p.content
        ][:1]  # 只取第一个作为参考
        
        if generated_pages:
            reference_pages_prompt = "参考已生成的页面代码，确保设计风格一致：\n\n"
            
            for ref_page in generated_pages:
                reference_pages_prompt += f'页面 "{ref_page.name}":\n```html\n{ref_page.content}\n```\n\n'
            
            messages.append(InputMessage(ChatRoleType.SYSTEM, reference_pages_prompt))
        
        # 添加当前页面与其他页面的关系
        page_relationships = "这个页面与其他页面的关系：\n"
        for other_page in page_structure.pages:
            if other_page.name != page_info.name:
                page_relationships += f"- {page_info.name} 应该链接到 {other_page.name} ({other_page.path})\n"
        
        messages.append(InputMessage(ChatRoleType.SYSTEM, page_relationships))
        
        # 添加页面生成指令
        generating_prompt = await self.ai_prompt_service.generating_prompt_template()
        messages.append(InputMessage(
            ChatRoleType.USER,
            generating_prompt.replace("{0}", page_info.name)
                           .replace("{1}", page_info.path)
                           .replace("{2}", page_info.description)
                           .replace("{3}", design_system_info)
        ))
        
        return messages
    
    async def _extract_ai_generate_message_code(
        self, user_id: int, session_id: int, page_structure: PageStructureDto, page_index: int, ai_response: str
    ) -> bool:
        """
        提交AI的响应中的代码并保存
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            page_structure: 页面结构
            page_index: 页面索引
            ai_response: AI回复
            
        Returns:
            操作结果
        """
        # 存储AI回复
        ai_message_entity = PrototypeMessage(
            session_id=session_id,
            user_id=user_id,
            message_type=PrototypeMessageType.AI,
            content=ai_response,
            is_code=False  # 是否是代码内容
        )
        
        page_info = page_structure.pages[page_index]
        
        # 提取HTML代码并保存页面
        extract_code_status = False
        page_code = self._extract_html_from_markdown(ai_response)
        
        if page_code:
            # 验证提取的HTML代码
            if "<section" not in page_code and "<div" not in page_code:
                # 尝试更宽松的提取
                page_code = self._extract_code_any_type(ai_response)
            
            if page_code:
                page = await self.page_repository.get_by_path_async(session_id, page_info.path)
                
                if page is None:
                    ai_message_entity.is_code = True  # 记录是代码
                    # 创建新页面记录
                    new_page = PrototypePage(
                        user_id=user_id,
                        session_id=session_id,
                        name=page_info.name,
                        path=page_info.path,
                        description=page_info.description,
                        content=page_code,
                        status=PrototypePageStatus.GENERATED,
                        is_complete=True,  # 全部完成，未截断
                        partial_content=None,
                        error_message=None,
                        order=page_index,
                        version=1
                    )
                    await self.page_repository.add_async(new_page)
                else:
                    # 更新现有页面
                    await self.page_repository.update_content_async(page.id, page_code)
                    await self.page_repository.update_status_async(page.id, PrototypePageStatus.GENERATED)
                
                extract_code_status = True
        
        await self.message_repository.add_async(ai_message_entity)
        
        if not extract_code_status:
            # 如果无法提取代码，添加错误消息
            await self._add_system_message_async(
                user_id, session_id,
                f"警告:无法从AI响应中提取有效HTML代码。请检查响应内容。"
            )
        else:
            # 添加成功的系统消息
            await self._add_system_message_async(
                user_id, session_id,
                f"页面 {page_info.name} 代码已保存 ({page_index + 1}/{len(page_structure.pages)})"
            )
        
        return extract_code_status
    
    def _extract_design_system_info(self, page_structure: PageStructureDto) -> str:
        """
        从页面结构中提取设计系统信息
        
        Args:
            page_structure: 页面结构
            
        Returns:
            设计系统信息文本
        """
        design_style_builder = [
            f"设计风格: {page_structure.design_style}",
            f"配色方案: {page_structure.color_scheme}",
            f"目标设备: {page_structure.target_device}",
            f"交互风格: {page_structure.interaction_style}"
        ]
        
        return "\n".join(design_style_builder)
    
    def _extract_html_from_markdown(self, markdown: str) -> str:
        """
        从Markdown文本中提取HTML代码块
        
        Args:
            markdown: Markdown文本
            
        Returns:
            HTML代码字符串
        """
        # 尝试提取html代码块
        html_pattern = r"```html\s*([\s\S]*?)\s*```"
        html_match = re.search(html_pattern, markdown)
        
        if html_match and len(html_match.groups()) > 0:
            return html_match.group(1).strip()
        
        return ""
    
    def _extract_code_any_type(self, text: str) -> str:
        """
        尝试提取任何类型的代码
        
        Args:
            text: 文本内容
            
        Returns:
            代码字符串
        """
        # 尝试提取任意代码块
        any_pattern = r"```\w*\s*([\s\S]*?)\s*```"
        any_match = re.search(any_pattern, text)
        
        if any_match and len(any_match.groups()) > 0:
            return any_match.group(1).strip()
        
        # 提取HTML标签开始的部分
        html_tag_pattern = r"(<[\w\s=""'-]+>[\s\S]*)"
        html_tag_match = re.search(html_tag_pattern, text)
        
        if html_tag_match and len(html_tag_match.groups()) > 0:
            return html_tag_match.group(1).strip()
        
        # 如果以上都失败，尝试查找包含"<section"或"<div"的段落
        paragraphs = re.split(r"\n\n|\r\n\r\n", text)
        for paragraph in paragraphs:
            if "<section" in paragraph or "<div" in paragraph:
                return paragraph.strip()
        
        # 没有找到任何代码
        return ""
    
    def _extract_code_from_markdown(self, markdown: str) -> str:
        """
        从Markdown文本中提取代码块
        
        Args:
            markdown: Markdown文本
            
        Returns:
            代码字符串
        """
        # 尝试提取jsx代码块
        jsx_pattern = r"```jsx\s*([\s\S]*?)\s*```"
        jsx_match = re.search(jsx_pattern, markdown)
        
        if jsx_match and len(jsx_match.groups()) > 0:
            return jsx_match.group(1).strip()
        
        # 尝试提取js代码块
        js_pattern = r"```js\s*([\s\S]*?)\s*```"
        js_match = re.search(js_pattern, markdown)
        
        if js_match and len(js_match.groups()) > 0:
            return js_match.group(1).strip()
        
        # 尝试提取javascript代码块
        javascript_pattern = r"```javascript\s*([\s\S]*?)\s*```"
        javascript_match = re.search(javascript_pattern, markdown)
        
        if javascript_match and len(javascript_match.groups()) > 0:
            return javascript_match.group(1).strip()
        
        # 尝试提取react代码块
        react_pattern = r"```react\s*([\s\S]*?)\s*```"
        react_match = re.search(react_pattern, markdown)
        
        if react_match and len(react_match.groups()) > 0:
            return react_match.group(1).strip()
        
        # 尝试提取任意代码块
        any_pattern = r"```\w*\s*([\s\S]*?)\s*```"
        any_match = re.search(any_pattern, markdown)
        
        if any_match and len(any_match.groups()) > 0:
            return any_match.group(1).strip()
        
        # 如果没有找到代码块，返回原始文本（去除可能的说明文字）
        return self._cleanup_code_text(markdown)
    
    def _cleanup_code_text(self, text: str) -> str:
        """
        清理代码文本，去除不必要的说明性文字
        
        Args:
            text: 代码文本
            
        Returns:
            清理后的代码
        """
        # 尝试移除开头和结尾的说明性文字
        lines = text.split('\n')
        code_lines = []
        in_code_block = False
        
        for line in lines:
            # 检测代码开始的标志：import语句或React组件声明
            if (not in_code_block and (line.startswith("import ") or
                                     "function " in line or
                                     ("const " in line and " = (" in line) or
                                     ("class " in line and " extends " in line))):
                in_code_block = True
            
            if in_code_block:
                code_lines.append(line)
            
            # 检测代码结束的标志
            if in_code_block and "export default " in line:
                # 确保添加了最后一行代码后，如果有后续说明内容，不再添加
                in_code_block = False
        
        if code_lines:
            return "\n".join(code_lines)
        
        # 如果无法识别代码块，返回原始文本
        return text
    
    def _extract_json_from_markdown(self, markdown: str) -> str:
        """
        从Markdown文本中提取JSON代码块
        
        Args:
            markdown: Markdown文本
            
        Returns:
            JSON字符串
        """
        json_pattern = r"```json\s*([\s\S]*?)\s*```"
        match = re.search(json_pattern, markdown)
        
        if match and len(match.groups()) > 0:
            return match.group(1).strip()
        
        return ""
    
    async def _add_system_message_async(self, user_id: int, session_id: int, content: str) -> int:
        """
        添加系统消息
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            content: 消息内容
            
        Returns:
            消息ID
        """
        system_message = PrototypeMessage(
            session_id=session_id,
            user_id=user_id,
            message_type=PrototypeMessageType.SYSTEM,
            content=content
        )
        return await self.message_repository.add_async(system_message)