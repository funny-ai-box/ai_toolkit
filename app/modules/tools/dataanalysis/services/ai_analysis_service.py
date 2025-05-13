# app/modules/dataanalysis/services/ai_analysis_service.py
import json
import logging
from typing import List, Optional, Dict, Any
import re
from app.core.ai.chat.base import IChatAIService
from app.core.utils import json_utils
from app.modules.tools.dataanalysis.models import DataTable
from app.modules.tools.dataanalysis.dtos import OpenAiResponseDto, SqlQueryDto
from app.modules.base.prompts.services import PromptTemplateService

class AIAnalysisService:
    """AI 分析服务实现"""
    
    def __init__(self, ai_service: IChatAIService,prompt_template_service: PromptTemplateService):
        """
        初始化 AI 分析服务
        
        Args:
            ai_service: AI 服务
       
        """
        self.prompt_template_service = prompt_template_service
        self.ai_service = ai_service
    
    
    async def get_completion_async(self, prompt: str) -> str:
        """
        获取AI完成响应
        
        Args:
            prompt: 提示词
        
        Returns:
            AI响应内容
        """
        messages = [
            {"role": "system", "content": "你是一个专业的数据分析师和SQL专家。"},
            {"role": "user", "content": prompt}
        ]
        return await self.ai_service.chat_completion_async(messages)
    
    async def pre_select_tables_async(self, query: str, tables: List[DataTable]) -> List[int]:
        """
        预筛选查询可能需要的数据表
        
        Args:
            query: 用户查询
            tables: 所有可用数据表列表
        
        Returns:
            筛选后可能相关的数据表ID列表
        """
        if not tables:
            return []
        
        # 如果表的数量较少，直接返回所有表
        if len(tables) <= 3:
            return [table.id for table in tables]
        
        # 构建预筛选提示词
        prompt_tables_text = "\n".join([
            f"- 表ID: {table.id}, 表名: {table.table_name}, 显示名称: {table.display_name}"
            for table in tables
        ])
        
        system_prompt = await self.prompt_template_service.get_content_by_key_async("DATAANALYSIS_PRESELECTTABLES_PROMPT")
        system_prompt = system_prompt.replace("{Query}", query)
        system_prompt = system_prompt.replace("{Tables}", prompt_tables_text)
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # 调用AI
        try:
            response = await self.ai_service.chat_completion_async(messages)
            
            # 尝试解析JSON数组
            try:
                selected_table_ids = json.loads(response)
                if isinstance(selected_table_ids, list) and all(isinstance(id, int) for id in selected_table_ids):
                    # 验证返回的ID是否存在于原表列表中
                    valid_ids = [id for id in selected_table_ids if any(t.id == id for t in tables)]
                    
                    # 如果筛选后没有表，则返回所有表
                    if not valid_ids:
                        return [table.id for table in tables]
                    
                    return valid_ids
            except Exception:
                # JSON解析失败，尝试正则匹配数字
                matches = re.findall(r'\d+', response)
                if matches:
                    selected_table_ids = [int(m) for m in matches]
                    valid_ids = [id for id in selected_table_ids if any(t.id == id for t in tables)]
                    
                    if valid_ids:
                        return valid_ids
        except Exception as ex:
            print(f"预筛选表失败: {str(ex)}")
        
        # 默认返回所有表
        return [table.id for table in tables]
    
    async def get_data_analysis_async(self, query: str, tables: List[DataTable]) -> OpenAiResponseDto:
        """
        基于用户查询和表结构获取SQL和可视化建议
        
        Args:
            query: 用户查询
            tables: 数据表列表
        
        Returns:
            OpenAI响应DTO
        """
        try:
            # 第一步：预筛选可能相关的表
            selected_table_ids = await self.pre_select_tables_async(query, tables)
            selected_tables = [t for t in tables if t.id in selected_table_ids]
            
            # 第二步：使用筛选后的表构建详细提示词
            system_prompt = await self.prompt_template_service.get_content_by_key_async("DATAANALYSIS_DATA_ANALYSIS_PROMPT")
            
            # 加入表结构描述
            table_prompt = await self._build_data_analysis_table_prompt_async(query, selected_tables)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "system", "content": table_prompt}
            ]
            
            # 调用AI API
            response = await self.ai_service.chat_completion_async(messages)
            
            try:
                # 处理可能的控制字符
                response = self._replace_control_chars_with_space(response)
                
                # 解析响应
                return json_utils.parse_json(response, OpenAiResponseDto)
            except Exception as ex:
                print(f"解析AI响应失败: {str(ex)}")
                
                # 创建一个默认响应
                return OpenAiResponseDto(
                    queries=[],
                    message=f"解析OpenAI响应时出错: {str(ex)}\n\n原始响应: {response}"
                )
        except Exception as ex:
            print(f"获取数据分析失败: {str(ex)}")
            
            # 处理整体错误
            return OpenAiResponseDto(
                queries=[],
                message=f"处理查询时出错: {str(ex)}"
            )
    
    async def get_streaming_response_async(self, query: str, tables: List[DataTable],
            on_chunk_received: callable, cancellation_token: Optional[Any] = None) -> str:
        """
        启动流式响应
        
        Args:
            query: 用户查询
            tables: 数据表列表
            on_chunk_received: 接收到数据块时的回调函数
            cancellation_token: 取消令牌
        
        Returns:
            完整的AI回复
        """
        try:
            # 第一步：预筛选可能相关的表
            selected_table_ids = await self.pre_select_tables_async(query, tables)
            selected_tables = [t for t in tables if t.id in selected_table_ids]
            
            # 第二步：使用筛选后的表构建详细提示词
            system_prompt = await self.prompt_template_service.get_content_by_key_async("DATAANALYSIS_DATA_ANALYSIS_PROMPT")
            
            # 加入表结构描述
            table_prompt = await self._build_data_analysis_table_prompt_async(query, selected_tables)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "system", "content": table_prompt}
            ]
            
            # 调用流式API
            return await self.ai_service.streaming_chat_completion_async(
                messages, on_chunk_received, cancellation_token
            )
        except Exception as ex:
            print(f"获取流式响应失败: {str(ex)}")
            raise
    
    async def _build_data_analysis_table_prompt_async(self, query: str, tables: List[DataTable]) -> str:
        """
        构建数据分析提示词
        
        Args:
            query: 用户查询
            tables: 数据表列表
        
        Returns:
            提示词
        """
        from app.modules.tools.dataanalysis.repositories.table_column_repository import TableColumnRepository
        
        # 导入其他必要的依赖
        # 假设我们可以获取TableColumnRepository的实例
        # 在实际应用中，这应该通过依赖注入来获取
        table_column_repo = None  # 应该通过某种方式获取
        
        prompt = "**数据库表结构**\n\n"
        
        # 添加表结构信息
        for table in tables:
            prompt += f"- `{table.table_name}`:\n"
            
            # 获取表的列信息
            # 注意：这里需要依赖注入TableColumnRepository，我们假设已经有了
            if table_column_repo:
                columns = await table_column_repo.get_table_columns_async(table.id)
                
                for column in columns:
                    data_type_desc = self._get_data_type_description(column.data_type)
                    prompt += f"  - `{column.english_name}` ({data_type_desc}) - {column.description or column.original_name}\n"
            
            prompt += "\n"
        
        # 添加用户查询
        prompt += "**用户需求**\n\n"
        prompt += f"- \"{query}\"\n"
        
        return prompt
    
    def _get_data_type_description(self, data_type: str) -> str:
        """
        获取数据类型描述
        
        Args:
            data_type: 数据类型
        
        Returns:
            数据类型描述
        """
        if not data_type:
            return "未知类型"
            
        data_type_lower = data_type.lower()
        
        if data_type_lower == "string":
            return "字符串"
        elif data_type_lower == "integer":
            return "整数"
        elif data_type_lower == "float":
            return "浮点数"
        elif data_type_lower == "date":
            return "日期"
        elif data_type_lower == "boolean":
            return "布尔值"
        else:
            return data_type
    
    def _replace_control_chars_with_space(self, json_str: str) -> str:
        """
        替换换行等特殊符号
        
        Args:
            json_str: JSON字符串
        
        Returns:
            处理后的字符串
        """
        if not json_str:
            return json_str
        
        # 替换常见的控制字符
        cleaned = json_str.replace('\r', ' ')  # CR (Carriage Return, 0x0D)
        cleaned = cleaned.replace('\n', ' ')   # LF (Line Feed, 0x0A)
        cleaned = cleaned.replace('\t', ' ')   # Tab
        cleaned = cleaned.replace('\b', ' ')   # Backspace
        cleaned = cleaned.replace('\f', ' ')   # Form feed
        
        return cleaned