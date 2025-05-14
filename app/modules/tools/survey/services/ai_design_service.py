import json
import datetime
import re
from typing import List, Dict, Any, Optional, Tuple, Callable
import logging

from app.core.ai.chat.base import IChatAIService
from app.core.ai.chat.factory import get_chat_ai_service
from app.core.ai.dtos import ChatRoleType

from app.modules.base.prompts.services import PromptTemplateService
from app.modules.tools.survey.repositories import SurveyDesignHistoryRepository
from app.modules.tools.survey.models import SurveyDesignHistory, SurveyTask, SurveyTab, SurveyField
from app.modules.tools.survey.dtos import TabDesignDto, FieldDesignDto, FieldConfigDto, AIDesignResponseDto

# 日志记录器
logger = logging.getLogger(__name__)


class AIDesignService:
    """问卷设计AI服务实现"""

    def __init__(
        self,
        ai_service: IChatAIService,
        prompt_template_service: PromptTemplateService,
        design_history_repository: SurveyDesignHistoryRepository,
        max_context_messages: int = 10
    ):
        """
        初始化问卷设计AI服务
        
        Args:
            ai_service: AI服务实例
            prompt_template_service: 提示词模板服务
            design_history_repository: 设计历史仓储
            max_context_messages: 最大上下文消息数
        """
        self.ai_service = ai_service
        self.prompt_template_service = prompt_template_service
        self.design_history_repository = design_history_repository
        self.max_context_messages = max_context_messages
        
        # 是否可能包含JSON标记的正则表达式
        self.contains_json_regex = re.compile(r"```json|<json>", re.IGNORECASE)

    async def ai_design_fields_async(
        self,
        user_id: int,
        task: SurveyTask,
        user_message: str,
        on_chunk_received: Callable[[str], None],
        tabs: Optional[List[SurveyTab]] = None,
        fields: Optional[List[SurveyField]] = None,
        cancellation_token = None
    ) -> AIDesignResponseDto:
        """
        流式AI设计问卷字段
        
        Args:
            user_id: 用户ID
            task: 问卷任务对象
            user_message: 用户消息
            on_chunk_received: 接收到数据块时的回调函数
            tabs: 已存在的Tab页列表（可选）
            fields: 已存在的字段列表（可选）
            cancellation_token: 取消令牌
            
        Returns:
            设计响应
        """
        try:
            # 构建智能聊天上下文
            messages = await self.build_smart_chat_messages_async(task, user_message, tabs, fields)

            # 用于构建完整响应
            complete_response = []

            # 调用流式AI服务
            async for chunk in self.ai_service.streaming_chat_completion_async(messages):
                complete_response.append(chunk)
                on_chunk_received(chunk)
                
                if cancellation_token and cancellation_token.cancelled:
                    break

            # 合并所有响应块
            ai_response = ''.join(complete_response)

            # 保存用户消息到历史
            user_history_id = await self.save_design_history_message(
                user_id, task.id, ChatRoleType.USER, user_message
            )

            # 检查AI回复是否包含完整的JSON配置
            if self.contains_json_regex.search(ai_response):
                # 解析AI回复，提取JSON部分
                text_response, tabs_design = self.parse_ai_response(ai_response)

                # 如果成功解析出JSON配置，将其保存到历史记录中
                json_config = None
                if tabs_design and len(tabs_design) > 0:
                    json_config = json.dumps(
                        [tab.model_dump(by_alias=True) for tab in tabs_design],
                        ensure_ascii=False, 
                        indent=2
                    )

                # 保存AI回复到历史
                ai_history_id = await self.save_design_history_message(
                    user_id, task.id, ChatRoleType.ASSISTANT, text_response, json_config
                )

                return AIDesignResponseDto(
                    message=text_response,
                    tabs=tabs_design
                )
            else:
                # 保存AI回复到历史
                ai_history_id = await self.save_design_history_message(
                    user_id, task.id, ChatRoleType.ASSISTANT, ai_response
                )

                # 如果AI回复不包含JSON，则返回文本响应
                return AIDesignResponseDto(
                    message=ai_response,
                    tabs=[]
                )
        except Exception as ex:
            logger.error(f"流式AI设计问卷字段失败: {str(ex)}", exc_info=True)
            raise

    def parse_ai_response(self, ai_response: str) -> Tuple[str, List[TabDesignDto]]:
        """
        解析AI响应
        
        Args:
            ai_response: AI响应内容
            
        Returns:
            文本响应和Tab设计列表的元组
        """
        try:
            # 尝试提取JSON部分（使用正则表达式查找代码块或JSON标记）
            json_matches = re.finditer(r"```json\s*([\s\S]*?)\s*```|<json>\s*([\s\S]*?)\s*</json>", ai_response)
            
            for json_match in json_matches:
                # 使用第一个匹配的JSON
                json_content = json_match.group(1) if json_match.group(1) else json_match.group(2)
                
                # 解析JSON为Tab设计列表
                try:
                    tabs_data = json.loads(json_content)
                    if isinstance(tabs_data, list):
                        tabs_design = [TabDesignDto(**tab) for tab in tabs_data]
                        
                        # 移除AI回复中的JSON代码块，只保留文本说明部分
                        text_response = re.sub(r"```json\s*[\s\S]*?\s*```|<json>\s*[\s\S]*?\s*</json>", "", ai_response).strip()
                        
                        return text_response, tabs_design
                except json.JSONDecodeError:
                    logger.warning(f"JSON解析失败: {json_content}")
                    continue
                except Exception as ex:
                    logger.warning(f"转换为TabDesignDto失败: {str(ex)}")
                    continue
            
            # 如果没有找到JSON，则尝试将整个响应作为JSON解析
            try:
                tabs_data = json.loads(ai_response)
                if isinstance(tabs_data, list):
                    tabs_design = [TabDesignDto(**tab) for tab in tabs_data]
                    # 如果成功解析，说明整个响应就是JSON，文本部分为空
                    return "", tabs_design
            except Exception:
                # 解析失败，说明没有有效的JSON，返回原文本和空列表
                logger.warning("AI响应中未找到有效的JSON结构")
            
            return ai_response, []
        except Exception as ex:
            logger.error(f"解析AI响应失败: {str(ex)}", exc_info=True)
            return ai_response, []

    async def build_smart_chat_messages_async(
        self,
        task: SurveyTask,
        user_message: str,
        tabs: Optional[List[SurveyTab]] = None,
        fields: Optional[List[SurveyField]] = None
    ) -> List[Dict[str, Any]]:
        """
        构建智能聊天上下文
        
        Args:
            task: 问卷任务对象
            user_message: 用户消息
            tabs: 已存在的Tab页列表（可选）
            fields: 已存在的字段列表（可选）
            
        Returns:
            聊天消息列表
        """
        messages = []
        
        # 准备系统提示词
        system_prompt = await self.prompt_template_service.get_content_by_key_async("SURVEY_DESIGN_PROMPT")
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # 构建当前问卷配置
        current_config_json = await self.get_current_actual_config_async(task.id, tabs, fields)
        
        if current_config_json:
            # 修改的提示词
            system_edit_prompt = await self.prompt_template_service.get_content_by_key_async("SURVEY_DESIGN_EDIT_PROMPT")
            if system_edit_prompt:
                messages.append({"role": "system", "content": system_edit_prompt})
            
            # 存在当前配置，将其添加到系统提示中
            now_config = f"\n\n当前问卷配置如下:\n```json\n{current_config_json}\n```\n\n"
            messages.append({"role": "system", "content": now_config})
            
            # 找到包含最新JSON配置的历史记录（用于确定时间点）
            json_config_history = await self.design_history_repository.get_latest_complete_json_config_async(task.id)
            
            if json_config_history:
                # 获取JSON配置之后的对话历史
                all_history = await self.design_history_repository.get_by_task_id_async(task.id)
                # 根据创建时间排序，找到包含JSON配置的记录之后的历史
                for history in all_history:
                    if history.complete_json_config == json_config_history:
                        json_history_id = history.id
                        break
                else:
                    json_history_id = 0
                
                recent_history = [h for h in all_history if h.id > json_history_id]
                for history in sorted(recent_history, key=lambda x: x.create_date):
                    if history.role == ChatRoleType.USER:
                        messages.append({"role": "user", "content": history.content})
                    elif history.role == ChatRoleType.ASSISTANT:
                        messages.append({"role": "assistant", "content": history.content})
        else:
            # 没有现有配置，添加标准对话流程指南
            system_new_prompt = await self.prompt_template_service.get_content_by_key_async("SURVEY_DESIGN_NEW_PROMPT")
            if system_new_prompt:
                messages.append({"role": "system", "content": system_new_prompt})
            
            # 没有历史JSON配置，获取最近的对话历史
            recent_history = await self.design_history_repository.get_recent_history_async(
                task.id, self.max_context_messages
            )
            
            for history in recent_history:
                if history.role == ChatRoleType.USER:
                    messages.append({"role": "user", "content": history.content})
                elif history.role == ChatRoleType.ASSISTANT:
                    messages.append({"role": "assistant", "content": history.content})
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})
        
        return messages

    async def get_current_actual_config_async(
        self,
        task_id: int,
        tabs: Optional[List[SurveyTab]] = None,
        fields: Optional[List[SurveyField]] = None
    ) -> Optional[str]:
        """
        从数据库获取当前实际的完整问卷配置
        
        Args:
            task_id: 任务ID
            tabs: 已加载的Tab页列表（可选）
            fields: 已加载的字段列表（可选）
            
        Returns:
            JSON格式的完整配置或None
        """
        try:
            # 使用传入的tabs和fields，如果有的话
            tabs_list = tabs if tabs is not None else []
            fields_list = fields if fields is not None else []
            
            if not tabs_list:
                return None  # 没有现有配置
            
            if not fields_list:
                return None  # 没有现有字段
            
            # 构建配置对象
            tab_configs = []
            for tab in sorted(tabs_list, key=lambda t: t.order_no):
                tab_fields = [f for f in fields_list if f.tab_id == tab.id]
                if not tab_fields:
                    continue
                
                tab_config = {
                    "name": tab.name,
                    "orderNo": tab.order_no,
                    "fields": []
                }
                
                for field in sorted(tab_fields, key=lambda f: f.order_no):
                    field_config = None
                    if field.config:
                        try:
                            field_config = json.loads(field.config)
                        except json.JSONDecodeError:
                            field_config = {}
                    
                    field_dto = {
                        "fieldKey": field.field_key,
                        "name": field.name,
                        "type": field.type,
                        "isRequired": field.is_required,
                        "config": field_config or {},
                        "placeholder": field.placeholder,
                        "orderNo": field.order_no
                    }
                    tab_config["fields"].append(field_dto)
                
                tab_configs.append(tab_config)
            
            # 序列化为JSON
            if tab_configs:
                return json.dumps(tab_configs, ensure_ascii=False, indent=2)
            return None
        except Exception as ex:
            logger.error(f"获取当前问卷配置失败: {str(ex)}", exc_info=True)
            return None

    async def save_design_history_message(
        self,
        user_id: int,
        task_id: int,
        role: ChatRoleType,
        content: str,
        json_config: Optional[str] = None
    ) -> int:
        """
        保存设计历史消息
        
        Args:
            user_id: 用户ID
            task_id: 任务ID
            role: 角色
            content: 内容
            json_config: 完整JSON配置（可选）
            
        Returns:
            创建的历史记录ID
        """
        history = SurveyDesignHistory(
            user_id=user_id,
            task_id=task_id,
            role=role,
            content=content,
            complete_json_config=json_config
        )
        
        await self.design_history_repository.add_async(history)
        return history.id