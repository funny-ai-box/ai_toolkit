# app/modules/dataanalysis/models.py
import datetime
from sqlalchemy import BigInteger, String, DateTime, Text, func, Integer, Float, Boolean, ForeignKey, LargeBinary, SmallInteger
from sqlalchemy.orm import mapped_column, Mapped, relationship
from typing import Optional, List

from app.core.database.session import Base



class UploadFile(Base):
    """文件上传记录实体"""
    __tablename__ = "dta_upload_file"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    original_file_name: Mapped[str] = mapped_column(String(255), name="OriginalFileName", comment="原始文件名")
    file_path: Mapped[str] = mapped_column(String(500), name="FilePath", comment="文件存储路径")
    file_size: Mapped[int] = mapped_column(BigInteger, name="FileSize", comment="文件大小(字节)")
    file_type: Mapped[str] = mapped_column(String(50), name="FileType", comment="文件类型(csv/excel等)")
    status: Mapped[int] = mapped_column(SmallInteger, name="Status", comment="状态：0-初始，1-解析中，2-解析成功，3-解析失败")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="LastModifyDate", comment="最后修改时间")

class DataTable(Base):
    """数据表记录实体"""
    __tablename__ = "dta_data_table"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    upload_file_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UploadFileId", comment="关联的上传文件ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    table_name: Mapped[str] = mapped_column(String(100), name="TableName", comment="临时表名")
    display_name: Mapped[str] = mapped_column(String(255), name="DisplayName", comment="显示名称（用户可理解的名称）")
    row_count: Mapped[int] = mapped_column(Integer, name="RowCount", comment="数据行数")
    storage_type: Mapped[str] = mapped_column(String(20), name="StorageType", comment="存储类型（mysql/doris）")
    status: Mapped[int] = mapped_column(SmallInteger, name="Status", comment="状态：0-创建中，1-可用，2-异常")
    expiry_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True, name="ExpiryDate", comment="过期时间")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="LastModifyDate", comment="最后修改时间")

class TableColumn(Base):
    """数据表列信息实体"""
    __tablename__ = "dta_table_column"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    table_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="TableId", comment="关联的数据表ID")
    original_name: Mapped[str] = mapped_column(String(255), name="OriginalName", comment="原始列名（文件中的列名）")
    english_name: Mapped[str] = mapped_column(String(100), name="EnglishName", comment="英文列名（表中的列名）")
    description: Mapped[str] = mapped_column(String(500), name="Description", comment="列描述")
    data_type: Mapped[str] = mapped_column(String(50), name="DataType", comment="数据类型（string, integer, float, date等）")
    column_index: Mapped[int] = mapped_column(Integer, name="ColumnIndex", comment="列顺序")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="LastModifyDate", comment="最后修改时间")

class ImportLog(Base):
    """数据导入日志实体"""
    __tablename__ = "dta_import_log"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    upload_file_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UploadFileId", comment="关联的上传文件ID")
    table_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="TableId", comment="关联的数据表ID")
    total_rows: Mapped[int] = mapped_column(Integer, name="TotalRows", comment="总行数")
    success_rows: Mapped[int] = mapped_column(Integer, name="SuccessRows", comment="成功导入行数")
    failed_rows: Mapped[int] = mapped_column(Integer, name="FailedRows", comment="失败行数")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="ErrorMessage", comment="错误信息")
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime, name="StartTime", comment="开始时间")
    end_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True, name="EndTime", comment="结束时间")
    status: Mapped[int] = mapped_column(SmallInteger, name="Status", comment="状态：0-进行中，1-成功，2-失败")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="LastModifyDate", comment="最后修改时间")

class AnalysisSession(Base):
    """分析会话实体"""
    __tablename__ = "dta_analysis_session"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    session_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, name="SessionName", comment="会话名称")
    status: Mapped[int] = mapped_column(SmallInteger, name="Status", comment="状态：0-已关闭，1-活跃")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="LastModifyDate", comment="最后修改时间")

class Conversation(Base):
    """对话记录实体"""
    __tablename__ = "dta_conversation"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    session_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="SessionId", comment="会话ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    user_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="UserQuery", comment="用户查询内容")
    ai_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="AiResponse", comment="AI响应内容")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="LastModifyDate", comment="最后修改时间")

class SqlExecution(Base):
    """SQL执行记录实体"""
    __tablename__ = "dta_sql_execution"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="ConversationId", comment="对话ID")
    sql_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="SqlStatement", comment="SQL语句")
    data_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="DataJson", comment="执行SQL后获取到的JSON")
    execution_status: Mapped[int] = mapped_column(SmallInteger, name="ExecutionStatus", comment="执行状态：0-执行中，1-成功，2-失败")
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, name="ErrorMessage", comment="错误信息")
    storage_type: Mapped[str] = mapped_column(String(20), name="StorageType", comment="存储类型（mysql/doris）")
    execution_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, name="ExecutionTime", comment="执行时间(毫秒)")
    row_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, name="RowCount", comment="结果行数")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="LastModifyDate", comment="最后修改时间")

class Visualization(Base):
    """可视化配置实体"""
    __tablename__ = "dta_visualization"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    sql_execution_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="SqlExecutionId", comment="SQL执行ID")
    visualization_type: Mapped[str] = mapped_column(String(50), name="VisualizationType", comment="可视化类型(line, bar, pie, scatter, table)")
    chart_config: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="ChartConfig", comment="可视化图表配置JSON")
    html_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, name="HtmlPath", comment="生成的HTML文件路径")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="LastModifyDate", comment="最后修改时间")

class DynamicPage(Base):
    """动态页面实体"""
    __tablename__ = "dta_dynamic_page"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="UserId", comment="用户ID")
    page_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, name="PageName", comment="页面名称")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="Description", comment="页面描述")
    layout_config: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="LayoutConfig", comment="页面布局配置JSON")
    is_public: Mapped[int] = mapped_column(SmallInteger, name="IsPublic", comment="是否公开：0-私有，1-公开")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="LastModifyDate", comment="最后修改时间")

class PageComponent(Base):
    """动态页面组件实体"""
    __tablename__ = "dta_page_component"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    page_id: Mapped[int] = mapped_column(BigInteger, nullable=False, name="PageId", comment="动态页面ID")
    component_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, name="ComponentType", comment="组件类型(filter, chart, table)")
    component_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, name="ComponentName", comment="组件名称")
    component_config: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="ComponentConfig", comment="组件配置JSON")
    sql_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True, name="SqlTemplate", comment="SQL模板")
    sql_execution_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, name="SqlExecutionId", comment="关联的原始SQL执行ID")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="CreateDate", comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, name="LastModifyDate", comment="最后修改时间")