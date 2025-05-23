from typing import List, Optional, Any, Annotated # <--- Import Annotated
import datetime
from pydantic import BaseModel, Field # <--- Field is already imported
# Remove conint and constr imports if they were explicit, though Field handles their functionality
# from pydantic import conint, constr # REMOVE THIS if present

from app.core.ai.dtos import ChatRoleType 
from app.modules.tools.datadesign.enums import DatabaseType, LanguageType, AssistantRoleType

# Common DTOs (equivalent to BaseIdRequestDto and BasePageRequestDto)
class BaseIdRequestDto(BaseModel):
    """基础ID请求DTO"""
    id: int = Field(..., description="ID")

class BasePageRequestDto(BaseModel):
    """基础分页请求DTO"""
    # OLD: page_index: conint(ge=1) = Field(1, description="页码，从1开始")
    # NEW:
    page_index: Annotated[int, Field(ge=1, default=1, description="页码，从1开始")]
    
    # OLD: page_size: conint(ge=1, le=100) = Field(20, description="每页大小，最大100")
    # NEW:
    page_size: Annotated[int, Field(ge=1, le=100, default=20, description="每页大小，最大100")]


# DesignTask DTOs
class CreateDesignTaskRequestDto(BaseModel):
    """创建设计任务请求DTO"""
    # OLD: task_name: constr(min_length=1, max_length=255) = Field(..., description="任务名称")
    # NEW:
    taskName: Annotated[str, Field(min_length=1, max_length=255, description="任务名称")]
    description: Optional[str] = Field(None, description="任务描述")

class UpdateDesignTaskRequestDto(BaseModel):
    """更新设计任务请求DTO"""
    id: int = Field(..., description="任务ID")
    # OLD: task_name: constr(min_length=1, max_length=255) = Field(..., description="任务名称")
    # NEW:
    task_name: Annotated[str, Field(min_length=1, max_length=255, description="任务名称")]
    description: Optional[str] = Field(None, description="任务描述")

class DesignTaskDetailDto(BaseModel):
    """设计任务详情DTO"""
    id: int = Field(..., description="任务ID")
    task_name: Optional[str] = Field(None, description="任务名称")
    description: Optional[str] = Field(None, description="任务描述")
    create_date: datetime.datetime = Field(..., description="创建时间")
    last_modify_date: datetime.datetime = Field(..., description="最后修改时间")

    class Config:
        from_attributes = True

class DesignTaskListItemDto(BaseModel):
    """设计任务列表项DTO"""
    id: int = Field(..., description="任务ID")
    task_name: Optional[str] = Field(None, description="任务名称")
    description: Optional[str] = Field(None, description="任务描述")
    table_count: int = Field(0, description="表数量")
    create_date: datetime.datetime = Field(..., description="创建时间")
    last_modify_date: datetime.datetime = Field(..., description="最后修改时间")

    class Config:
        from_attributes = True

class DesignTaskListRequestDto(BasePageRequestDto):
    """设计任务列表请求DTO"""
    pass

class PagedResultDto(BaseModel):
    """分页结果DTO模板"""
    items: List[Any] = Field(..., description="当前页数据项")
    total_count: int = Field(..., description="总记录数")
    page_index: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    total_pages: int = Field(..., description="总页数")

    @property
    def has_previous_page(self) -> bool:
        return self.page_index > 1

    @property
    def has_next_page(self) -> bool:
        return self.page_index < self.total_pages
        
class DesignTaskPagedResultDto(PagedResultDto):
    items: List[DesignTaskListItemDto]


# TableDesign DTOs (used for response)
class FieldDesignDetailDto(BaseModel):
    """字段设计详情DTO"""
    id: int = Field(..., description="字段ID")
    field_name: Optional[str] = Field(None, description="字段名")
    comment: Optional[str] = Field(None, description="字段注释")
    data_type: Optional[str] = Field(None, description="数据类型")
    length: Optional[int] = Field(None, description="长度")
    precision: Optional[int] = Field(None, description="精度")
    scale: Optional[int] = Field(None, description="小数位数")
    default_value: Optional[str] = Field(None, description="默认值")
    is_primary_key: bool = Field(False, description="是否主键")
    is_nullable: bool = Field(False, description="是否允许为空")
    is_auto_increment: bool = Field(False, description="是否自增")
    sort_order: int = Field(0, description="排序号")

    class Config:
        from_attributes = True

class IndexFieldDto(BaseModel):
    """索引字段DTO"""
    id: int = Field(..., description="索引字段ID")
    field_id: int = Field(..., description="字段ID")
    field_name: Optional[str] = Field(None, description="字段名")
    sort_direction: Optional[str] = Field(None, description="排序方向")
    sort_order: int = Field(0, description="排序号")

    class Config:
        from_attributes = True

class IndexDesignDetailDto(BaseModel):
    """索引设计详情DTO"""
    id: int = Field(..., description="索引ID")
    index_name: Optional[str] = Field(None, description="索引名称")
    index_type: Optional[str] = Field(None, description="索引类型")
    description: Optional[str] = Field(None, description="索引描述")
    fields: Optional[List[IndexFieldDto]] = Field(None, description="索引字段列表")

    class Config:
        from_attributes = True

class TableRelationDto(BaseModel):
    """表关系DTO"""
    id: int = Field(..., description="关系ID")
    parent_table_id: int = Field(..., description="父表ID")
    parent_table_name: Optional[str] = Field(None, description="父表名")
    child_table_id: int = Field(..., description="子表ID")
    child_table_name: Optional[str] = Field(None, description="子表名")
    relation_type: Optional[str] = Field(None, description="关系类型")
    description: Optional[str] = Field(None, description="关系描述")

    class Config:
        from_attributes = True

class TableDesignDetailDto(BaseModel):
    """表设计详情DTO"""
    id: int = Field(..., description="表ID")
    task_id: int = Field(..., description="任务ID")
    table_name: Optional[str] = Field(None, description="表名")
    comment: Optional[str] = Field(None, description="表注释")
    business_description: Optional[str] = Field(None, description="业务描述")
    business_group: Optional[str] = Field(None, description="业务分组")
    fields: Optional[List[FieldDesignDetailDto]] = Field(None, description="字段列表")
    parent_relations: Optional[List[TableRelationDto]] = Field(None, description="父表关系")
    child_relations: Optional[List[TableRelationDto]] = Field(None, description="子表关系")
    indexes: Optional[List[IndexDesignDetailDto]] = Field(None, description="索引列表")

    class Config:
        from_attributes = True

class TableDesignListItemDto(BaseModel):
    """表设计列表项DTO"""
    id: int = Field(..., description="表ID")
    table_name: Optional[str] = Field(None, description="表名")
    comment: Optional[str] = Field(None, description="表注释")
    business_group: Optional[str] = Field(None, description="业务分组")
    field_count: int = Field(0, description="字段数量")
    child_relations: Optional[List[TableRelationDto]] = Field(None, description="子表关系")

    class Config:
        from_attributes = True


# DesignChat DTOs
class DesignChatRequestDto(BaseModel):
    """聊天请求DTO"""
    task_id: int = Field(..., description="任务ID", alias="taskId")
    message: str = Field(..., description="用户消息")
    
    class Config:
        populate_by_name = True


class DesignChatMessageDto(BaseModel):
    """聊天消息DTO"""
    id: int = Field(..., description="消息ID")
    role: ChatRoleType = Field(..., description="角色(user/assistant)")
    assistant_role: Optional[AssistantRoleType] = Field(None, description="助手角色")
    content: Optional[str] = Field(None, description="内容")
    create_date: datetime.datetime = Field(..., description="创建时间")

    class Config:
        from_attributes = True


# DatabaseDesign DTOs (for JSON parsing from AI)
class FieldDesignJsonDto(BaseModel):
    """字段设计DTO（用于JSON解析）"""
    field_name: Optional[str] = Field(None, alias="fieldName")
    comment: Optional[str] = Field(None)
    data_type: Optional[str] = Field(None, alias="dataType")
    length: Optional[int] = Field(None)
    precision: Optional[int] = Field(None)
    scale: Optional[int] = Field(None)
    default_value: Optional[str] = Field(None, alias="defaultValue")
    is_primary_key: bool = Field(False, alias="isPrimaryKey")
    is_nullable: bool = Field(False, alias="isNullable")
    is_auto_increment: bool = Field(False, alias="isAutoIncrement")
    
    class Config:
        populate_by_name = True

class IndexFieldDetailJsonDto(BaseModel):
    """索引字段详情DTO（用于JSON解析）"""
    field_name: Optional[str] = Field(None, alias="fieldName")
    sort_direction: Optional[str] = Field(None, alias="sortDirection")

    class Config:
        populate_by_name = True

class IndexDesignJsonDto(BaseModel):
    """索引设计DTO（用于JSON解析）"""
    index_name: Optional[str] = Field(None, alias="indexName")
    index_type: Optional[str] = Field(None, alias="indexType")
    description: Optional[str] = Field(None)
    fields: Optional[List[IndexFieldDetailJsonDto]] = Field(None)

    class Config:
        populate_by_name = True

class TableDesignJsonDto(BaseModel):
    """表设计DTO（用于JSON解析）"""
    table_name: Optional[str] = Field(None, alias="tableName")
    comment: Optional[str] = Field(None)
    business_description: Optional[str] = Field(None, alias="businessDescription")
    business_group: Optional[str] = Field(None, alias="businessGroup")
    fields: Optional[List[FieldDesignJsonDto]] = Field(None)
    indexes: Optional[List[IndexDesignJsonDto]] = Field(None)

    class Config:
        populate_by_name = True

class TableRelationJsonDto(BaseModel): 
    """表关系DTO（用于JSON解析）"""
    parent_table_name: Optional[str] = Field(None, alias="parentTableName")
    child_table_name: Optional[str] = Field(None, alias="childTableName")
    relation_type: Optional[str] = Field(None, alias="relationType")
    description: Optional[str] = Field(None)

    class Config:
        populate_by_name = True

class DatabaseDesignJsonDto(BaseModel): 
    """数据库设计DTO（用于JSON解析）"""
    tables: Optional[List[TableDesignJsonDto]] = Field(None)
    relations: Optional[List[TableRelationJsonDto]] = Field(None)


class DesignChatReplyDto(BaseModel):
    """聊天回复DTO"""
    reply: Optional[str] = Field(None, description="回复内容")
    design: Optional[DatabaseDesignJsonDto] = Field(None, description="设计数据（如果存在）")

class DesignDialogResultDto(BaseModel):
    """设计对话结果DTO"""
    user_message: Optional[str] = Field(None, description="用户消息")
    business_analysis: Optional[str] = Field(None, description="业务分析")
    database_design: Optional[str] = Field(None, description="数据库设计")
    json_structure: Optional[str] = Field(None, description="JSON结构")
    database_design_dto: Optional[DatabaseDesignJsonDto] = Field(None, description="数据库设计DTO")


# CodeTemplate DTOs
class CreateCodeTemplateDto(BaseModel):
    """用户创建代码模板DTO"""
    # OLD: template_name: constr(min_length=1, max_length=100) = Field(..., description="模板名称", alias="templateName")
    # NEW:
    template_name: Annotated[str, Field(min_length=1, max_length=100, description="模板名称", alias="templateName")]
    language: LanguageType = Field(..., description="编程语言")
    database_type: DatabaseType = Field(..., description="数据库类型", alias="databaseType")

    class Config:
        populate_by_name = True

class SupportCodeLanguageDto(BaseModel):
    """支持的程序语言"""
    value: int
    code: Optional[str] = None

class SupportLanguageAndDbDto(BaseModel):
    """支持的程序语言和数据库"""
    databases: Optional[List[SupportCodeLanguageDto]] = None
    languages: Optional[List[SupportCodeLanguageDto]] = None

class CodeTemplateDto(BaseModel):
    """代码模板DTO"""
    id: int = Field(..., description="模板ID")
    user_id: int = Field(..., description="用户ID，0代表系统预置模板", alias="userId")
    template_name: Optional[str] = Field(None, description="模板名称", alias="templateName")
    language: LanguageType = Field(..., description="编程语言")
    database_type: DatabaseType = Field(..., description="数据库类型", alias="databaseType")
    prompt_content: Optional[str] = Field(None, description="自定义模板的提示词", alias="promptContent")
    is_system: bool = Field(..., description="是否系统模板")

    class Config:
        from_attributes = True
        populate_by_name = True


class CodeTemplateDetailDto(BaseModel):
    """代码模板详情DTO"""
    id: int = Field(..., description="模板详情ID")
    template_dtl_name: Optional[str] = Field(None, description="模板详情名称", alias="templateDtlName")
    template_content: Optional[str] = Field(None, description="模板内容", alias="templateContent")
    create_date: datetime.datetime = Field(..., description="创建时间", alias="createDate")
    last_modify_date: datetime.datetime = Field(..., description="最后修改时间", alias="lastModifyDate")
    
    class Config:
        from_attributes = True
        populate_by_name = True


class GenerateDDLRequestDto(BaseModel):
    """生成DDL请求DTO"""
    task_id: int = Field(..., description="任务ID", alias="taskId")
    table_id: Optional[int] = Field(None, description="表ID，不传则导出所有表", alias="tableId")
    database_type: DatabaseType = Field(DatabaseType.MYSQL, description="数据库类型", alias="databaseType")

    class Config:
        populate_by_name = True

class GenerateCodeRequestDto(BaseModel):
    """生成代码请求DTO"""
    table_id: int = Field(..., description="表ID", alias="tableId")
    template_id: int = Field(..., description="模板ID来生成代码", alias="templateId")

    class Config:
        populate_by_name = True

class GenerateDDLResultDto(BaseModel):
    """生成DDL结果DTO"""
    task_id: int = Field(..., description="任务ID", alias="taskId")
    table_id: Optional[int] = Field(None, description="表ID", alias="tableId")
    database_type: DatabaseType = Field(..., description="数据库类型", alias="databaseType")
    script: Optional[str] = Field(None, description="DDL脚本")

    class Config:
        populate_by_name = True

class CodeFileDto(BaseModel):
    """代码文件DTO"""
    name: Optional[str] = Field(None, description="代码名称")
    file_name: Optional[str] = Field(None, description="文件名", alias="fileName")
    content: Optional[str] = Field(None, description="文件内容")

    class Config:
        populate_by_name = True


class GenerateCodeResultDto(BaseModel):
    """生成代码结果DTO"""
    table_id: int = Field(..., description="表ID", alias="tableId")
    language: LanguageType = Field(..., description="编程语言")
    database_type: DatabaseType = Field(..., description="数据库类型", alias="databaseType")
    files: Optional[List[CodeFileDto]] = Field(None, description="生成的代码文件列表")

    class Config:
        populate_by_name = True

# CodeTemplateGenerator DTOs
class CodeTemplateGeneratorDto(BaseModel):
    """AI代码模板生成的Dto"""
    template_name: Optional[str] = Field(None, description="模板名称", alias="templateName")
    template_type: Optional[str] = Field(None, description="模板类型", alias="templateType")
    template_content: Optional[str] = Field(None, description="模板内容", alias="templateContent")
    
    class Config:
        populate_by_name = True

class GenerateCodeTemplateRequestDto(BaseModel):
    """用户发起代码模板生成的请求"""
    template_id: int = Field(..., description="模板编号", alias="templateId")
    # OLD: requirements: constr(min_length=1, max_length=1000) = Field(..., description="模板需求描述")
    # NEW:
    requirements: Annotated[str, Field(min_length=1, max_length=1000, description="模板需求描述")]


    class Config:
        populate_by_name = True

class GetExampleRequirementsRequestDto(BaseModel):
    """获取示例要求请求DTO"""
    language: LanguageType = Field(..., description="编程语言")
    database_type: DatabaseType = Field(..., description="数据库类型", alias="databaseType")

    class Config:
        populate_by_name = True

class TemplateExampleDto(BaseModel):
    """模板示例DTO"""
    language: LanguageType = Field(..., description="编程语言")
    database_type: DatabaseType = Field(..., description="数据库类型", alias="databaseType")
    example_requirements: Optional[str] = Field(None, description="示例需求", alias="exampleRequirements")

    class Config:
        populate_by_name = True

# ParseDocument (not used in controller, assuming internal or future use)
class ParseDocumentRequestDto(BaseModel):
    """文档解析请求DTO"""
    task_id: int = Field(..., description="任务ID", alias="taskId")
    content: Optional[str] = Field(None, description="文档内容")

    class Config:
        populate_by_name = True