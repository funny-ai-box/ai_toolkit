# app/modules/dataanalysis/services/data_analysis_service.py
import logging
import json
import datetime
import os
from typing import List, Dict, Any, Optional, Tuple, Callable, Union
from app.core.exceptions import BusinessException,UnauthorizedException
from app.core.dtos import ApiResponse, PagedResultDto
from app.modules.tools.dataanalysis.models import (
    AnalysisSession,
    Conversation,
    SqlExecution,
    Visualization,
    DataTable,
    DynamicPage,
    PageComponent
)
from app.modules.tools.dataanalysis.dtos import (
    AnalysisSessionDto,
    SessionListItemDto,
    DataTableListItemDto,
    UserQueryDto,
    AiResponseDto,
    ConversationDto,
    SqlExecutionDto,
    VisualizationDto,
    TempDataDto,
    CreateDynamicPageDto,
    AddDynamicPageSqlDto,
    DynamicPageDto,
    PageComponentDto,
    DynamicPageListItemDto,
    GetSessionHistoryDto
)
from app.modules.tools.dataanalysis.repositories.analysis_session_repository import AnalysisSessionRepository
from app.modules.tools.dataanalysis.repositories.data_table_repository import DataTableRepository
from app.modules.tools.dataanalysis.repositories.temp_data_table_repository import TempDataTableRepository
from app.modules.tools.dataanalysis.repositories.table_column_repository import TableColumnRepository
from app.modules.tools.dataanalysis.repositories.conversation_repository import ConversationRepository
from app.modules.tools.dataanalysis.repositories.sql_execution_repository import SqlExecutionRepository
from app.modules.tools.dataanalysis.repositories.visualization_repository import VisualizationRepository
from app.modules.tools.dataanalysis.repositories.dynamic_page_repository import DynamicPageRepository
from app.modules.tools.dataanalysis.repositories.page_component_repository import PageComponentRepository
from app.modules.tools.dataanalysis.services.ai_analysis_service import AIAnalysisService
from app.modules.tools.dataanalysis.services.visualization_executor import VisualizationExecutor
from app.core.utils import json_utils

class DataAnalysisService:
    """数据分析服务实现"""
    
    def __init__(
        self,
        session_repository: AnalysisSessionRepository,
        data_table_repository: DataTableRepository,
        temp_data_table_repository: TempDataTableRepository,
        table_column_repository: TableColumnRepository,
        conversation_repository: ConversationRepository,
        sql_execution_repository: SqlExecutionRepository,
        visualization_repository: VisualizationRepository,
        dynamic_page_repository: DynamicPageRepository,
        page_component_repository: PageComponentRepository,
        ai_analysis_service: AIAnalysisService,
    
    ):
        """
        初始化数据分析服务
        
        Args:
            session_repository: 分析会话仓储
            data_table_repository: 数据表仓储
            temp_data_table_repository: 临时数据表仓储
            table_column_repository: 表列信息仓储
            conversation_repository: 对话仓储
            sql_execution_repository: SQL执行仓储
            visualization_repository: 可视化仓储
            dynamic_page_repository: 动态页面仓储
            page_component_repository: 页面组件仓储
            ai_analysis_service: AI分析服务

        """
        self.session_repository = session_repository
        self.data_table_repository = data_table_repository
        self.temp_data_table_repository = temp_data_table_repository
        self.table_column_repository = table_column_repository
        self.conversation_repository = conversation_repository
        self.sql_execution_repository = sql_execution_repository
        self.visualization_repository = visualization_repository
        self.dynamic_page_repository = dynamic_page_repository
        self.page_component_repository = page_component_repository
        self.ai_analysis_service = ai_analysis_service
  
    
    async def get_table_datas_async(self, user_id: int, file_id: int) -> TempDataDto:
        """
        获取表的数据
        
        Args:
            user_id: 用户ID
            file_id: 文件ID
        
        Returns:
            数据
        """
        # 获取数据表定义
        table_def = await self.data_table_repository.get_by_upload_file_id_async(file_id)
        if not table_def:
            raise BusinessException("文件的数据表不存在")
        
        if table_def.status != 1:
            raise BusinessException("文件的数据表不可用")
        
        # 检查权限
        if table_def.user_id != user_id:
            raise UnauthorizedException("无权访问此数据表")
        
        # 获取表数据
        result = await self.temp_data_table_repository.get_datas_by_table_name_async(table_def.table_name)
        
        # 获取表列信息
        table_columns = []
        if table_def:
            db_table_cols = await self.table_column_repository.get_table_columns_async(table_def.id)
            for col in db_table_cols:
                from app.modules.tools.dataanalysis.dtos import FileColumnDto
                table_columns.append(FileColumnDto(
                    id=col.id,
                    column_name=col.english_name,
                    original_name=col.original_name,
                    column_index=col.column_index,
                    data_type=col.data_type,
                    description=col.description,
                ))
        
        # 构建返回结果
        return TempDataDto(
            data_json=result[0],  # JSON字符串
            row_count=result[1],  # 行数
            table_name=table_def.table_name,
            display_name=table_def.display_name,
            total_row_count=table_def.row_count,
            execution_duration=result[2],  # 执行时间
            columns=table_columns,
        )
    
    async def create_session_async(self, user_id: int, session_name: str) -> AnalysisSessionDto:
        """
        创建分析会话
        
        Args:
            user_id: 用户ID
            session_name: 会话名称
        
        Returns:
            会话信息
        """
        # 创建会话
        session = AnalysisSession(
            user_id=user_id,
            session_name=session_name or f"分析会话 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            status=1  # 活跃
        )
        
        session = await self.session_repository.add_async(session)
        
        # 获取会话信息
        return await self.get_session_async(session.id, user_id)
    
    async def get_session_async(self, session_id: int, user_id: int) -> AnalysisSessionDto:
        """
        获取会话信息
        
        Args:
            session_id: 会话ID
            user_id: 用户ID
        
        Returns:
            会话信息
        """
        # 获取会话
        session = await self.session_repository.get_by_id_async(session_id)
        if not session:
            raise BusinessException("会话不存在")
        
        # 检查权限
        if session.user_id != user_id:
            raise UnauthorizedException("无权访问此会话")
        
        # 获取用户所有可用的数据表
        tables = await self.data_table_repository.get_user_tables_async(user_id)
        
        # 构建会话DTO
        result = AnalysisSessionDto(
            id=session.id,
            session_name=session.session_name,
            status=session.status,
            create_time=session.create_date,
            last_active_time=session.last_modify_date,
            available_tables=[]
        )
        
        # 添加表信息
        for table in tables:
            table_columns = await self.table_column_repository.get_table_columns_async(table.id)
            
            result.available_tables.append(DataTableListItemDto(
                id=table.id,
                upload_file_id=table.upload_file_id,
                table_name=table.table_name,
                display_name=table.display_name,
                row_count=table.row_count,
                storage_type=table.storage_type,
                status=table.status,
                column_count=len(table_columns),
                create_time=table.create_date
            ))
        
        return result
    
    async def get_user_sessions_async(self, user_id: int, page_index: int = 1, page_size: int = 20) -> PagedResultDto[SessionListItemDto]:
        """
        获取用户的会话列表
        
        Args:
            user_id: 用户ID
            page_index: 页码
            page_size: 每页大小
        
        Returns:
            会话列表
        """
        # 确保页码和每页数量有效
        if page_index < 1:
            page_index = 1
        if page_size < 1:
            page_size = 20
        
        # 获取用户的会话列表
        sessions = await self.session_repository.get_user_sessions_async(user_id)
        
        # 计算总记录数
        total_count = len(sessions)
        
        # 应用分页
        paged_sessions = sessions[(page_index - 1) * page_size:page_index * page_size]
        
        # 构建结果列表
        result = []
        
        for session in paged_sessions:
            result.append(SessionListItemDto(
                id=session.id,
                session_name=session.session_name,
                status=session.status,
                create_time=session.create_date,
                last_active_time=session.last_modify_date
            ))
        
        # 构建分页结果
        return PagedResultDto[SessionListItemDto](
            items=result,
            total_count=total_count,
            page_index=page_index,
            page_size=page_size,
            total_pages=(total_count + page_size - 1) // page_size  # 向上取整
        )
    
    async def close_session_async(self, session_id: int) -> bool:
        """
        关闭会话
        
        Args:
            session_id: 会话ID
        
        Returns:
            是否成功
        """
        session = await self.session_repository.get_by_id_async(session_id)
        if not session:
            raise BusinessException("会话不存在")
        
        # 更新会话状态
        session.status = 0  # 已关闭
        session.last_modify_date = datetime.datetime.now()
        
        await self.session_repository.update_async(session)
        
        return True
    
    async def refresh_conversation_data(self, sql_execution_id: int) -> SqlExecutionDto:
        """
        对对话中的图表，重新执行刷新数据的动作
        
        Args:
            sql_execution_id: 会话中执行SQL的ID
        
        Returns:
            SQL执行DTO
        """
        # 获取SQL执行记录
        sql_execution = await self.sql_execution_repository.get_by_id_async(sql_execution_id)
        if not sql_execution:
            raise BusinessException("会话图表不存在")
        
        # 执行SQL查询
        result, row_count, execution_time = await self.sql_execution_repository.execute_sql_query_async(
            sql_execution.sql_statement, sql_execution.storage_type
        )
        
        # 更新SQL执行状态
        sql_execution.execution_status = 1  # 成功
        sql_execution.row_count = row_count
        sql_execution.execution_time = execution_time
        sql_execution.data_json = result
        
        await self.sql_execution_repository.update_async(sql_execution)
        
        # 构建SQL执行DTO
        sql_execution_dto = SqlExecutionDto(
            id=sql_execution.id,
            sql_statement=sql_execution.sql_statement,
            execution_status=sql_execution.execution_status,
            execution_duration=sql_execution.execution_time,
            data_json=sql_execution.data_json,
            execution_time=sql_execution.create_date,
            row_count=sql_execution.row_count
        )
        
        # 获取可视化配置
        visualization = await self.visualization_repository.get_by_sql_execution_id_async(sql_execution.id)
        if visualization:
            sql_execution_dto.visualization = VisualizationDto(
                id=visualization.id,
                sql_execution_id=visualization.sql_execution_id,
                visualization_type=visualization.visualization_type,
                chart_config=visualization.chart_config,
                html_path=visualization.html_path,
                html_url=f"/api/dta/visualization/{visualization.id}"
            )
        
        return sql_execution_dto
    
    async def process_user_query_async(self, user_id: int, query_dto: UserQueryDto) -> AiResponseDto:
        """
        处理用户查询
        
        Args:
            user_id: 用户ID
            query_dto: 查询DTO
        
        Returns:
            AI响应
        """
        # 获取会话
        session = await self.session_repository.get_by_id_async(query_dto.session_id)
        if not session:
            raise BusinessException("会话不存在")
        
        # 检查权限
        if session.user_id != user_id:
            raise UnauthorizedException("无权访问此会话")
        
        # 创建对话记录
        conversation = Conversation(
            session_id=query_dto.session_id,
            user_id=user_id,
            user_query=query_dto.query
        )
        
        conversation = await self.conversation_repository.add_async(conversation)
        
        try:
            # 获取用户所有可用的数据表
            tables = await self.data_table_repository.get_user_tables_async(user_id, query_dto.file_id)
            if not tables:
                raise BusinessException("当前用户没有可用的数据表，请先上传数据")
            
            # 调用OpenAI获取SQL和可视化建议
            # OpenAI服务会自动进行两步查询：先预筛选相关表，再进行详细分析
            openai_response = await self.ai_analysis_service.get_data_analysis_async(query_dto.query or "", tables)
            
            # 处理OpenAI响应
            sql_executions = []
            
            if openai_response.queries and len(openai_response.queries) > 0:
                for query in openai_response.queries:
                    # 创建SQL执行记录
                    sql_execution = SqlExecution(
                        conversation_id=conversation.id,
                        sql_statement=query.sql,
                        execution_status=0 ,
                        storage_type=tables[0].storage_type if tables else "mysql",
                        execution_time=0,
                        row_count=0,
                    )
                    
                    sql_execution = await self.sql_execution_repository.add_async(sql_execution)
                    
                    try:

                        result, row_count, execution_time = await self.sql_execution_repository.execute_sql_query_async(
                            query.sql or "", sql_execution.storage_type or ""
                        )
                        
                        # 更新SQL执行状态
                        sql_execution.execution_status = 1  # 成功
                        sql_execution.row_count = row_count
                        sql_execution.execution_time = execution_time
                        sql_execution.data_json = result
                        
                        await self.sql_execution_repository.update_async(sql_execution)
                        
                        # 创建可视化配置
                        visualization = Visualization(
                            sql_execution_id=sql_execution.id,
                            visualization_type=query.type,
                            chart_config=(
                                json.dumps(query.table.__dict__) if query.type == "table" and query.table 
                                else json.dumps(query.echarts.__dict__) if query.echarts 
                                else None
                            )
                        )
                        
                        visualization = await self.visualization_repository.add_async(visualization)
                        
                        # 生成可视化HTML
                        html_path = await self.visualization_repository.generate_visualization_html_async(
                            visualization, result
                        )
                        visualization.html_path = html_path
                        
                        await self.visualization_repository.update_async(visualization)
                        
                        # 构建SQL执行DTO
                        sql_execution_dto = SqlExecutionDto(
                            id=sql_execution.id,
                            sql_statement=sql_execution.sql_statement,
                            execution_status=sql_execution.execution_status,
                            execution_duration=sql_execution.execution_time,
                            data_json=sql_execution.data_json,
                            execution_time=sql_execution.create_date,
                            row_count=sql_execution.row_count,
                            visualization=VisualizationDto(
                                id=visualization.id,
                                sql_execution_id=visualization.sql_execution_id,
                                visualization_type=visualization.visualization_type,
                                chart_config=visualization.chart_config,
                                html_path=visualization.html_path,
                                html_url=f"/api/dta/visualization/{visualization.id}"
                            )
                        )
                        
                        sql_executions.append(sql_execution_dto)
                    except Exception as ex:
                        print(f"执行SQL查询失败: {ex}")
                        
                        # 更新SQL执行状态
                        sql_execution.execution_status = 2  # 失败
                        sql_execution.error_message = str(ex)[:250] if ex else "未知错误"
                        
                        await self.sql_execution_repository.update_async(sql_execution)
                        
                        # 构建SQL执行DTO
                        sql_execution_dto = SqlExecutionDto(
                            id=sql_execution.id,
                            sql_statement=sql_execution.sql_statement,
                            execution_status=sql_execution.execution_status,
                            error_message=sql_execution.error_message,
                            execution_time=sql_execution.create_date
                        )
                        
                        sql_executions.append(sql_execution_dto)
            
            # 构建AI响应
            ai_response = openai_response.message
            if not ai_response:
                ai_response = "我已根据您的查询生成了以下分析结果："
            
            # 更新对话记录
            conversation.ai_response = ai_response
            await self.conversation_repository.update_async(conversation)
            
            # 更新会话最后修改时间
            session.last_modify_date = datetime.datetime.now()
            await self.session_repository.update_async(session)
            
            return AiResponseDto(
                conversation_id=conversation.id,
                response=ai_response,
                sql_executions=sql_executions
            )
        except Exception as ex:
            print(f"处理用户查询失败: {ex}")
            
            # 更新对话记录
            conversation.ai_response = f"对不起，处理查询时出错：{str(ex)}"
            await self.conversation_repository.update_async(conversation)
            
            # 更新会话最后修改时间
            session.last_modify_date = datetime.datetime.now()
            await self.session_repository.update_async(session)
            
            raise
    
    async def get_conversation_async(self, conversation_id: int) -> ConversationDto:
        """
        获取对话详情
        
        Args:
            conversation_id: 对话ID
        
        Returns:
            对话详情
        """
        # 获取对话记录
        conversation = await self.conversation_repository.get_by_id_async(conversation_id)
        if not conversation:
            raise BusinessException("对话不存在")
        
        # 获取SQL执行记录
        sql_executions = await self.sql_execution_repository.get_conversation_sql_executions_async(conversation_id)
        sql_execution_dtos = []
        
        for sql_execution in sql_executions:
            sql_execution_dto = SqlExecutionDto(
                id=sql_execution.id,
                sql_statement=sql_execution.sql_statement,
                execution_status=sql_execution.execution_status,
                error_message=sql_execution.error_message,
                execution_duration=sql_execution.execution_time,
                data_json=sql_execution.data_json,
                execution_time=sql_execution.create_date,
                row_count=sql_execution.row_count
            )
            
            # 获取可视化配置
            visualization = await self.visualization_repository.get_by_sql_execution_id_async(sql_execution.id)
            if visualization:
                sql_execution_dto.visualization = VisualizationDto(
                    id=visualization.id,
                    sql_execution_id=visualization.sql_execution_id,
                    visualization_type=visualization.visualization_type,
                    chart_config=visualization.chart_config,
                    html_path=visualization.html_path,
                    html_url=f"/api/dta/visualization/{visualization.id}"
                )
            
            sql_execution_dtos.append(sql_execution_dto)
        
        # 构建对话DTO
        return ConversationDto(
            id=conversation.id,
            session_id=conversation.session_id,
            user_query=conversation.user_query,
            ai_response=conversation.ai_response,
            create_time=conversation.create_date,
            sql_executions=sql_execution_dtos
        )
    
    async def process_user_query_stream_async(
        self, 
        user_id: int, 
        query_dto: UserQueryDto,
        on_chunk_received: Callable[[str], None],
        cancellation_token: Optional[Any] = None
    ) -> str:
        """
        流式处理用户查询
        
        Args:
            user_id: 用户ID
            query_dto: 查询DTO
            on_chunk_received: 接收到数据块时的回调函数
            cancellation_token: 取消令牌
        
        Returns:
            完整的AI回复
        """
        # 获取会话
        session = await self.session_repository.get_by_id_async(query_dto.session_id)
        if not session:
            raise BusinessException("会话不存在")
        
        # 检查权限
        if session.user_id != user_id:
            raise BusinessException("无权访问此会话")
        
        # 创建对话记录
        conversation = Conversation(
            session_id=query_dto.session_id,
            user_id=user_id,
            user_query=query_dto.query
        )
        
        conversation = await self.conversation_repository.add_async(conversation)
        
        # 获取用户所有可用的数据表
        tables = await self.data_table_repository.get_user_tables_async(user_id)
        if not tables:
            raise BusinessException("当前用户没有可用的数据表，请先上传数据")
        
        # 调用OpenAI流式API
        response_content = await self.ai_analysis_service.get_streaming_response_async(
            query_dto.query or "", 
            tables, 
            on_chunk_received, 
            cancellation_token
        )
        
        # 保存完整响应
        conversation.ai_response = response_content
        await self.conversation_repository.update_async(conversation)
        
        # 更新会话最后修改时间
        session.last_modify_date = datetime.datetime.now()
        await self.session_repository.update_async(session)
        
        return response_content
    
    async def get_session_history_async(
        self, 
        session_id: int, 
        page_index: int = 1, 
        page_size: int = 20
    ) -> PagedResultDto[ConversationDto]:
        """
        获取会话的对话历史
        
        Args:
            session_id: 会话ID
            page_index: 页码
            page_size: 每页大小
        
        Returns:
            对话历史
        """
        # 检查会话是否存在
        session = await self.session_repository.get_by_id_async(session_id)
        if not session:
            raise BusinessException("会话不存在")
        
        # 获取分页的对话记录
        conversations, total_count = await self.conversation_repository.get_paginated_session_conversations_async(
            session_id, page_index, page_size
        )
        
        # 构建结果列表
        result = []
        
        for conversation in conversations:
            sql_executions = await self.sql_execution_repository.get_conversation_sql_executions_async(conversation.id)
            sql_execution_dtos = []
            
            for sql_execution in sql_executions:
                sql_execution_dto = SqlExecutionDto(
                    id=sql_execution.id,
                    sql_statement=sql_execution.sql_statement,
                    data_json=sql_execution.data_json,
                    execution_status=sql_execution.execution_status,
                    error_message=sql_execution.error_message,
                    execution_time=sql_execution.create_date,
                    execution_duration=sql_execution.execution_time,
                    row_count=sql_execution.row_count
                )
                
                # 获取可视化配置
                visualization = await self.visualization_repository.get_by_sql_execution_id_async(sql_execution.id)
                if visualization:
                    sql_execution_dto.visualization = VisualizationDto(
                        id=visualization.id,
                        sql_execution_id=visualization.sql_execution_id,
                        visualization_type=visualization.visualization_type,
                        chart_config=visualization.chart_config,
                        html_path=visualization.html_path,
                        html_url=f"/api/dta/visualization/{visualization.id}"
                    )
                
                sql_execution_dtos.append(sql_execution_dto)
            
            result.append(ConversationDto(
                id=conversation.id,
                session_id=conversation.session_id,
                user_query=conversation.user_query,
                ai_response=conversation.ai_response,
                create_time=conversation.create_date,
                sql_executions=sql_execution_dtos
            ))
        
        # 构建分页结果
        return PagedResultDto[ConversationDto](
            items=result,
            total_count=total_count,
            page_index=page_index,
            page_size=page_size,
            total_pages=(total_count + page_size - 1) // page_size  # 向上取整
        )
    
    async def get_visualization_html_async(self, visualization_id: int) -> str:
        """
        获取可视化HTML内容
        
        Args:
            visualization_id: 可视化ID
        
        Returns:
            HTML内容
        """
        visualization = await self.visualization_repository.get_by_id_async(visualization_id)
        if not visualization:
            raise BusinessException("可视化不存在")
        
        if not visualization.html_path or not os.path.exists(visualization.html_path):
            raise BusinessException("可视化文件不存在")
        
        with open(visualization.html_path, "r", encoding="utf-8") as f:
            return f.read()
    
    async def create_dynamic_page_async(self, user_id: int, create_page_dto: CreateDynamicPageDto) -> DynamicPageDto:
        """
        创建动态页面
        
        Args:
            user_id: 用户ID
            create_page_dto: 创建页面DTO
        
        Returns:
            动态页面信息
        """
        # 创建动态页面
        dynamic_page = DynamicPage(
            user_id=user_id,
            page_name=create_page_dto.page_name,
            description=create_page_dto.description,
            is_public=1 if create_page_dto.is_public else 0,
            layout_config="{}"  # 默认空布局
        )
        
        dynamic_page = await self.dynamic_page_repository.add_async(dynamic_page)
        
        # 返回动态页面信息
        return DynamicPageDto(
            id=dynamic_page.id,
            page_name=dynamic_page.page_name,
            description=dynamic_page.description,
            layout_config=dynamic_page.layout_config,
            is_public=dynamic_page.is_public == 1,
            create_time=dynamic_page.create_date,
            last_modify_time=dynamic_page.last_modify_date,
            components=[]
        )
    
    async def dynamic_page_add_sql_async(self, add_sql_dto: AddDynamicPageSqlDto) -> int:
        """
        给动态页面增加SQL执行组件
        
        Args:
            add_sql_dto: 增加SQL的DTO
        
        Returns:
            添加的组件数量
        """
        if not add_sql_dto.sql_execution_ids:
            return 0
        
        # 处理SQL执行和可视化
        components = []
        
        position = 0
        
        for sql_execution_id in add_sql_dto.sql_execution_ids:
            # 获取SQL执行记录
            sql_execution = await self.sql_execution_repository.get_by_id_async(sql_execution_id)
            if not sql_execution:
                continue
            
            # 获取可视化配置
            visualization = await self.visualization_repository.get_by_sql_execution_id_async(sql_execution_id)
            if not visualization:
                continue
            
            # 创建组件
            component = PageComponent(
                page_id=add_sql_dto.id,
                component_type=visualization.visualization_type,
                component_name=f"组件 {position + 1}",
                component_config=visualization.chart_config,
                sql_template=sql_execution.sql_statement,
                sql_execution_id=sql_execution.id
            )
            
            component = await self.page_component_repository.add_async(component)
            components.append(component)
            
            position += 1
        
        return len(components)
    
    async def get_dynamic_page_async(self, page_id: int, user_id: int) -> DynamicPageDto:
        """
        获取动态页面信息
        
        Args:
            page_id: 页面ID
            user_id: 用户ID
        
        Returns:
            动态页面信息
        """
        # 获取动态页面
        page = await self.dynamic_page_repository.get_by_id_async(page_id)
        if not page:
            raise BusinessException("页面不存在")
        
        # 检查权限（公开页面或属于用户的页面）
        if page.is_public != 1 and page.user_id != user_id:
            raise UnauthorizedException("无权访问此页面")
        
        # 获取页面组件
        components = await self.page_component_repository.get_page_components_async(page_id)
        
        # 构建组件DTO列表
        component_dtos = []
        for component in components:
            component_dtos.append(PageComponentDto(
                id=component.id,
                page_id=component.page_id,
                component_type=component.component_type,
                component_name=component.component_name,
                component_config=component.component_config,
                sql_template=component.sql_template,
                sql_execution_id=component.sql_execution_id
            ))
        
        # 构建页面DTO
        return DynamicPageDto(
            id=page.id,
            page_name=page.page_name,
            description=page.description,
            layout_config=page.layout_config,
            is_public=page.is_public == 1,
            create_time=page.create_date,
            last_modify_time=page.last_modify_date,
            components=component_dtos
        )
    
    async def get_user_dynamic_pages_async(
        self, 
        user_id: int, 
        page_index: int = 1, 
        page_size: int = 20
    ) -> PagedResultDto[DynamicPageListItemDto]:
        """
        获取用户的动态页面列表
        
        Args:
            user_id: 用户ID
            page_index: 页码
            page_size: 每页大小
        
        Returns:
            动态页面列表
        """
        # 确保页码和每页数量有效
        if page_index < 1:
            page_index = 1
        if page_size < 1:
            page_size = 20
        
        # 获取用户的动态页面
        pages = await self.dynamic_page_repository.get_user_pages_async(user_id)
        
        # 计算总记录数
        total_count = len(pages)
        
        # 应用分页
        paged_pages = pages[(page_index - 1) * page_size:page_index * page_size]
        
        # 构建结果列表
        result = []
        
        for page in paged_pages:
            # 获取组件数量
            components = await self.page_component_repository.get_page_components_async(page.id)
            
            result.append(DynamicPageListItemDto(
                id=page.id,
                page_name=page.page_name,
                description=page.description,
                is_public=page.is_public == 1,
                component_count=len(components),
                create_time=page.create_date
            ))
        
        # 构建分页结果
        return PagedResultDto[DynamicPageListItemDto](
            items=result,
            total_count=total_count,
            page_index=page_index,
            page_size=page_size,
            total_pages=(total_count + page_size - 1) // page_size  # 向上取整
        )
    
    async def delete_dynamic_page_async(self, page_id: int, user_id: int) -> bool:
        """
        删除动态页面
        
        Args:
            page_id: 页面ID
            user_id: 用户ID
        
        Returns:
            是否成功
        """
        # 获取动态页面
        page = await self.dynamic_page_repository.get_by_id_async(page_id)
        if not page:
            raise BusinessException("页面不存在")
        
        # 检查权限
        if page.user_id != user_id:
            raise UnauthorizedException("无权删除此页面")
        
        # 删除页面及其组件
        return await self.dynamic_page_repository.delete_async(page_id)
