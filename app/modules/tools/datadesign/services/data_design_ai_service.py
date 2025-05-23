import logging
import json
import re
from typing import List, Callable, Optional, AsyncGenerator

from app.core.ai.chat.base import IChatAIService, InputMessage
from app.core.ai.dtos import ChatRoleType
from app.core.exceptions import BusinessException
from app.modules.base.prompts.services import PromptTemplateService
from app.modules.tools.datadesign.entities import DesignChat #, DesignTask
from app.modules.tools.datadesign.enums import AssistantRoleType
from app.modules.tools.datadesign.repositories.design_task_repository import DesignTaskRepository
from app.modules.tools.datadesign.repositories.design_chat_repository import DesignChatRepository
from app.modules.tools.datadesign.dtos import (
    DesignChatRequestDto, 
    DesignDialogResultDto,
    DatabaseDesignJsonDto # Use the JsonDto for parsing AI output
)

from app.modules.tools.datadesign.services.text_extraction_helper import AIResultTextExtractionHelper

class DataDesignAIService:
    """AI对话服务，处理数据设计相关的AI交互流程"""

    def __init__(
        self,
        logger: logging.Logger,
        design_task_repository: DesignTaskRepository,
        design_chat_repository: DesignChatRepository,
        ai_service: IChatAIService,
        prompt_template_service: PromptTemplateService
    ):
        """
        构造函数

        Args:
            logger: 日志记录器
            design_task_repository: 设计任务仓储
            design_chat_repository: 设计聊天仓储
            ai_service: AI聊天服务
            prompt_template_service: 提示词模板服务
        """
        self._logger = logger
        self._design_task_repository = design_task_repository
        self._design_chat_repository = design_chat_repository
        self._ai_service = ai_service
        self._prompt_template_service = prompt_template_service

    async def _build_business_analysis_prompt_messages(
        self,
        current_user_message: str,
        latest_business_analysis_content: Optional[str],
        user_history: List[DesignChat]
    ) -> List[InputMessage]:
        """构建业务分析阶段的提示词消息列表"""
        messages: List[InputMessage] = []
        
        if not user_history: # 首次对话
            system_prompt_key = "DATADESIGN_BUSINESS_ANALYSIS_FIRST_PROMPT"
            system_prompt = await self._prompt_template_service.get_content_by_key_async(system_prompt_key)
            if not system_prompt:
                raise BusinessException(f"提示词模板 '{system_prompt_key}' 未找到")
            messages.append(InputMessage(role=ChatRoleType.SYSTEM, content=system_prompt))
            messages.append(InputMessage(role=ChatRoleType.USER, content=current_user_message))
        else: # 非首次对话
            system_prompt_key = "DATADESIGN_BUSINESS_ANALYSIS_SECOND_PROMPT"
            system_prompt = await self._prompt_template_service.get_content_by_key_async(system_prompt_key)
            if not system_prompt:
                raise BusinessException(f"提示词模板 '{system_prompt_key}' 未找到")
            messages.append(InputMessage(role=ChatRoleType.SYSTEM, content=system_prompt))

            user_history_text = "\n".join(
                [f"- {msg.create_date.strftime('%Y-%m-%d %H:%M:%S')},{msg.content}" for msg in user_history if msg.role == ChatRoleType.USER]
            )
            if user_history_text:
                messages.append(InputMessage(role=ChatRoleType.ASSISTANT, content=f"--用户历史需求：\n{user_history_text}"))
            
            if latest_business_analysis_content:
                messages.append(InputMessage(role=ChatRoleType.ASSISTANT, content=f"--你(AI)的业务分析输出：\n{latest_business_analysis_content}"))
            
            messages.append(InputMessage(role=ChatRoleType.USER, content=f"--用户当前需求：\n{current_user_message}\n\n请根据我的新需求更新业务分析，首先列出变更点，然后使用标记输出完整的业务分析。"))
        
        return messages

    async def _process_business_analysis_async(
        self,
        task_id: int,
        current_user_message: str,
        latest_business_analysis_content: Optional[str],
        user_history: List[DesignChat],
        on_chunk_received: Optional[Callable[[str], None]]
    ) -> DesignChat:
        """处理业务分析阶段"""
        messages = await self._build_business_analysis_prompt_messages(
            current_user_message, latest_business_analysis_content, user_history
        )
        
        analysis_content_full = ""
        if on_chunk_received:
            async for chunk in self._ai_service.streaming_chat_completion_async(messages):
                analysis_content_full += chunk
                on_chunk_received(f"business_analyst|{chunk}")
        else:
            analysis_content_full = await self._ai_service.chat_completion_async(messages)

        # 提取标记内的内容进行保存，如果标记不存在，则保存全部
        extracted_analysis_content = AIResultTextExtractionHelper.extract_complete_business_analysis(analysis_content_full, self._logger)
        
        business_analysis_chat = DesignChat(
            task_id=task_id,
            role=ChatRoleType.ASSISTANT,
            assistant_role=AssistantRoleType.BUSINESS_ANALYST,
            content=extracted_analysis_content, # Store extracted or full content
            is_latest_analysis=True # Will be set by repository logic
        )
        return await self._design_chat_repository.add_async(business_analysis_chat)

    async def _build_database_design_prompt_messages(
        self,
        current_user_message: str,
        new_business_analysis_content: str,
        latest_business_analysis_content: Optional[str],
        latest_database_design_content: Optional[str],
        user_history: List[DesignChat]
    ) -> List[InputMessage]:
        """构建数据库设计阶段的提示词消息列表"""
        messages: List[InputMessage] = []

        if not user_history: # 首次对话 (Technically, user_history will have at least one item by now)
            system_prompt_key = "DATADESIGN_DBDESIGN_FIRST_PROMPT"
            system_prompt = await self._prompt_template_service.get_content_by_key_async(system_prompt_key)
            if not system_prompt:
                 raise BusinessException(f"提示词模板 '{system_prompt_key}' 未找到")
            messages.append(InputMessage(role=ChatRoleType.SYSTEM, content=system_prompt))
            messages.append(InputMessage(role=ChatRoleType.ASSISTANT, content=f"--用户需求：\n{current_user_message}")) # Use current_user_message for context
            messages.append(InputMessage(role=ChatRoleType.ASSISTANT, content=f"--业务分析结果：\n{new_business_analysis_content}"))
            messages.append(InputMessage(role=ChatRoleType.USER, content="请根据上述业务分析，设计一个合适的数据库结构。请确保表结构清晰、规范、易于扩展，并使用标记输出完整的数据库设计。"))
        else:
            system_prompt_key = "DATADESIGN_DBDESIGN_SECOND_PROMPT"
            system_prompt = await self._prompt_template_service.get_content_by_key_async(system_prompt_key)
            if not system_prompt:
                 raise BusinessException(f"提示词模板 '{system_prompt_key}' 未找到")
            messages.append(InputMessage(role=ChatRoleType.SYSTEM, content=system_prompt))

            user_history_text = "\n".join(
                [f"- {msg.create_date.strftime('%Y-%m-%d %H:%M:%S')},{msg.content}" for msg in user_history if msg.role == ChatRoleType.USER]
            )
            if user_history_text:
                 messages.append(InputMessage(role=ChatRoleType.ASSISTANT, content=f"--用户历史需求：\n{user_history_text}"))

            if latest_business_analysis_content:
                messages.append(InputMessage(role=ChatRoleType.ASSISTANT, content=f"--之前的业务分析：\n{latest_business_analysis_content}"))
            
            if latest_database_design_content:
                messages.append(InputMessage(role=ChatRoleType.ASSISTANT, content=f"--之前的数据库设计：\n{latest_database_design_content}"))

            messages.append(InputMessage(role=ChatRoleType.ASSISTANT, content=f"--用户当前需求：\n{current_user_message}"))
            messages.append(InputMessage(role=ChatRoleType.ASSISTANT, content=f"--更新后的业务分析：\n{new_business_analysis_content}"))
            messages.append(InputMessage(role=ChatRoleType.USER, content="请根据更新后的业务分析调整数据库设计，首先列出变更点，然后使用标记输出完整的数据库设计。"))
        
        return messages

    async def _process_database_design_async(
        self,
        task_id: int,
        current_user_message: str,
        new_business_analysis_content: str,
        latest_business_analysis_content: Optional[str],
        latest_database_design_content: Optional[str],
        user_history: List[DesignChat],
        on_chunk_received: Optional[Callable[[str], None]]
    ) -> DesignChat:
        """处理数据库设计阶段"""
        messages = await self._build_database_design_prompt_messages(
            current_user_message, new_business_analysis_content, 
            latest_business_analysis_content, latest_database_design_content, user_history
        )
        
        design_content_full = ""
        if on_chunk_received:
            async for chunk in self._ai_service.streaming_chat_completion_async(messages):
                design_content_full += chunk
                on_chunk_received(f"database_architect|{chunk}")
        else:
            design_content_full = await self._ai_service.chat_completion_async(messages)
        
        extracted_design_content = AIResultTextExtractionHelper.extract_complete_database_design(design_content_full, self._logger)

        database_design_chat = DesignChat(
            task_id=task_id,
            role=ChatRoleType.ASSISTANT,
            assistant_role=AssistantRoleType.DATABASE_ARCHITECT,
            content=extracted_design_content,
            is_latest_analysis=True # Will be set by repository
        )
        return await self._design_chat_repository.add_async(database_design_chat)

    async def _process_json_structure_async(
        self,
        task_id: int,
        database_design_content: str, # This should be the extracted, clean design
        on_chunk_received: Optional[Callable[[str], None]]
    ) -> DesignChat:
        """处理数据库结构的JSON结构生成阶段"""
        system_prompt_key = "DATADESIGN_JSON_STRUCTURE_PROMPT"
        system_prompt = await self._prompt_template_service.get_content_by_key_async(system_prompt_key)
        if not system_prompt:
            raise BusinessException(f"提示词模板 '{system_prompt_key}' 未找到")

        messages = [
            InputMessage(role=ChatRoleType.SYSTEM, content=system_prompt),
            InputMessage(role=ChatRoleType.ASSISTANT, content=f"--数据库设计：\n{database_design_content}"),
            InputMessage(role=ChatRoleType.USER, content="请将上述数据库设计转换为JSON结构格式。确保包含所有表、字段、索引和关系信息，并保持表名、字段名和注释的一致性。")
        ]

        json_content_full = ""
        if on_chunk_received:
            async for chunk in self._ai_service.streaming_chat_completion_async(messages):
                json_content_full += chunk
                on_chunk_received(f"database_operator|{chunk}")
        else:
            json_content_full = await self._ai_service.chat_completion_async(messages)
        
        # Attempt to extract JSON block if AI wraps it in markdown
        try:
            match = re.search(r"```json\s*([\s\S]+?)\s*```", json_content_full, re.DOTALL)
            if match:
                cleaned_json_content = match.group(1).strip()
                self._logger.info(f"Extracted JSON block from AI response for JSON structure.")
            else:
                cleaned_json_content = json_content_full.strip() # Assume it's raw JSON if no markdown
                self._logger.info(f"No JSON markdown block found, using raw AI response for JSON structure.")
        except Exception as e:
            self._logger.warning(f"Error cleaning JSON response, using raw: {e}")
            cleaned_json_content = json_content_full.strip()


        json_structure_chat = DesignChat(
            task_id=task_id,
            role=ChatRoleType.ASSISTANT,
            assistant_role=AssistantRoleType.DATABASE_OPERATOR,
            content=cleaned_json_content, # Store potentially cleaned JSON
            is_latest_analysis=True # Will be set by repository
        )
        return await self._design_chat_repository.add_async(json_structure_chat)

    def _extract_database_design_dto(self, json_content: Optional[str]) -> Optional[DatabaseDesignJsonDto]:
        """从JSON内容提取数据库设计DTO"""
        if not json_content:
            return None
        try:
            # Ensure json_content is valid JSON before parsing
            # Sometimes AI might return non-JSON text before/after the JSON block
            json_data = json.loads(json_content) # First validate it's loadable JSON
            return DatabaseDesignJsonDto.model_validate(json_data) # Then parse with Pydantic
        except json.JSONDecodeError as e:
            self._logger.error(f"解析数据库设计JSON失败 (JSONDecodeError): {e}. Content: {json_content[:500]}...") # Log snippet
        except Exception as ex: # Catches Pydantic validation errors too
            self._logger.error(f"解析数据库设计DTO失败: {ex}. Content: {json_content[:500]}...")
        return None

    async def process_async(
        self,
        user_id: int,
        request: DesignChatRequestDto,
        on_chunk_received: Optional[Callable[[str], None]] = None,
    ) -> DesignDialogResultDto:
        """
        处理对话 (包括业务分析, 数据库设计, JSON结构生成)

        Args:
            user_id: 用户ID
            request: 聊天请求
            on_chunk_received: 接收到数据块时的回调函数

        Returns:
            DesignDialogResultDto: 对话结果
        """
        try:
            task = await self._design_task_repository.get_by_id_async(request.task_id)
            if not task or task.user_id != user_id:
                raise BusinessException("设计任务不存在或无权限访问")

            # 1. 记录用户消息
            user_message_chat = DesignChat(
                task_id=request.task_id,
                role=ChatRoleType.USER,
                content=request.message,
                is_latest_analysis=False # User messages are not 'analysis'
            )
            await self._design_chat_repository.add_async(user_message_chat) # This now returns the added entity

            # 2. 获取历史和最新状态
            user_history = await self._design_chat_repository.get_user_message_history_async(request.task_id)
            latest_biz_analysis_chat = await self._design_chat_repository.get_latest_business_analysis_async(request.task_id)
            latest_db_design_chat = await self._design_chat_repository.get_latest_database_design_async(request.task_id)
            
            latest_biz_analysis_content = latest_biz_analysis_chat.content if latest_biz_analysis_chat else None
            latest_db_design_content = latest_db_design_chat.content if latest_db_design_chat else None

            # 3. 阶段1: 业务分析
            current_business_analysis_chat = await self._process_business_analysis_async(
                request.task_id, request.message, latest_biz_analysis_content, user_history, on_chunk_received
            )
            
            # 4. 阶段2: 数据库设计
            # Use the content from the *newly generated* business analysis for this stage
            current_database_design_chat = await self._process_database_design_async(
                request.task_id, request.message, 
                current_business_analysis_chat.content or "", # Use the newly generated analysis
                latest_biz_analysis_content, # Pass previous for context if it's a modification
                latest_db_design_content, 
                user_history, 
                on_chunk_received
            )

            # 5. 阶段3: JSON结构生成
            # Use the content from the *newly generated* database design for this stage
            json_structure_chat = await self._process_json_structure_async(
                request.task_id, 
                current_database_design_chat.content or "", # Use the newly generated design
                on_chunk_received
            )
            
            # 6. 准备结果
            result_dto = DesignDialogResultDto(
                user_message=request.message,
                business_analysis=current_business_analysis_chat.content,
                database_design=current_database_design_chat.content,
                json_structure=json_structure_chat.content
            )

            if json_structure_chat.content:
                result_dto.database_design_dto = self._extract_database_design_dto(json_structure_chat.content)
                if result_dto.database_design_dto is None:
                    self._logger.warning(f"Task {request.task_id}: Failed to parse DatabaseDesignJsonDto from AI's JSON structure output.")


            return result_dto

        except BusinessException:
            raise
        except Exception as ex:
            self._logger.error(f"处理数据设计AI对话失败 (task_id: {request.task_id}): {ex}")
            raise BusinessException(f"处理AI对话时发生内部错误: {str(ex)}")