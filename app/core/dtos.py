# app/core/dtos.py
from typing import Generic, TypeVar, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator 
from math import ceil

# 定义泛型类型变量
T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    """
    通用的 API 响应模型。
    使用 Pydantic 的 GenericModel 来支持泛型数据类型。
    """
    code: int = Field(200, description="状态码，例如 200 表示成功")
    message: str = Field("操作成功", description="响应消息")
    data: Optional[T] = Field(None, description="响应数据主体")

    model_config = ConfigDict(
        populate_by_name=True, # 允许通过别名或字段名填充
        json_schema_extra={ # 为 Swagger UI 提供示例
            "example": {
                "code": 200,
                "message": "操作成功",
                "data": None  # 示例中 data 可以是任意类型或 null
            }
        }
    )

    @classmethod
    def success(cls, data: Optional[T] = None, message: str = "操作成功", code: int = 200) -> 'ApiResponse[T]':
        """创建表示成功的 ApiResponse 实例"""
        return cls(code=code, message=message, data=data)

    @classmethod
    def fail(cls, message: str, code: int = 400, data: Optional[T] = None) -> 'ApiResponse[T]':
        """创建表示失败的 ApiResponse 实例"""
        # 注意：失败时通常不返回 data，但允许传入以便特殊情况使用
        return cls(code=code, message=message, data=data)


class BasePageRequestDto(BaseModel):
    """
    通用的分页请求参数模型。
    字段名使用 alias 确保能接收 camelCase 的 JSON 输入。
    """
    page_index: int = Field(1, ge=1, description="页码，从 1 开始", alias="pageIndex")
    page_size: int = Field(20, ge=1, le=100, description="每页大小，范围 1-100", alias="pageSize") # 添加最大值限制

    model_config = ConfigDict(
        populate_by_name=True, # 允许通过别名或字段名填充
        json_schema_extra={
            "example": {
                "pageIndex": 1,
                "pageSize": 20
            }
        }
    )

class PagedResultDto(BaseModel, Generic[T]):
    """
    通用的分页结果响应模型 (Pydantic V2 版本)。
    计算字段通过 @model_validator 自动完成。
    """
    items: List[T] = Field(..., description="当前页的数据项列表") # 移除 alias，使用 alias_generator
    total_count: int = Field(..., description="总记录数")
    page_index: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页记录数")
    # --- 计算字段：移除 Field 定义，让 model_validator 赋值 ---
    total_pages: int = 0 # 提供默认值
    has_previous_page: bool = False
    has_next_page: bool = False
    # ---------------------------------------------------

    model_config = ConfigDict(
        populate_by_name=True,
        # 使用 alias_generator 将 Python snake_case 转为 JSON camelCase
        alias_generator=lambda field_name: ''.join([field_name.split('_')[0]] + [word.capitalize() for word in field_name.split('_')[1:]]) if '_' in field_name else field_name,
        json_schema_extra={
            "example": {
                "items": [],
                "totalCount": 0,
                "pageIndex": 1,
                "pageSize": 20,
                "totalPages": 0,
                "hasPreviousPage": False,
                "hasNextPage": False
            }
        }
    )

    # --- 使用 model_validator 计算分页详情 ---
    @model_validator(mode='after') # 在模型字段填充和基础验证后执行
    def calculate_pagination_details(self) -> 'PagedResultDto[T]':
        """根据 total_count, page_index, page_size 自动计算分页详情"""
        if self.page_size <= 0:
            page_size = 1 # 防止除零
        else:
            page_size = self.page_size

        if self.total_count > 0:
            self.total_pages = ceil(self.total_count / page_size)
        else:
            self.total_pages = 0 # 如果总数为 0，则总页数为 0

        self.has_previous_page = self.page_index > 1
        # 确保与 total_pages 比较
        self.has_next_page = self.page_index < self.total_pages

        return self # 必须返回 self
    # --------------------------------------------

    @classmethod
    def create(cls, items: List[T], total_count: int, page_request: BasePageRequestDto) -> 'PagedResultDto[T]':
        """
        便捷方法，用于根据数据和请求参数创建分页结果。
        现在只传递基础数据，计算由 @model_validator 完成。
        """
        # 只需传递必需的字段，计算字段会自动生成
        instance = cls(
            items=items,
            total_count=total_count,
            page_index=page_request.page_index,
            page_size=page_request.page_size,
            # total_pages, has_previous_page, has_next_page 会被 validator 计算
        )
        return instance

class BaseIdRequestDto(BaseModel):
    """通用的按 ID 请求 DTO"""
    id: int = Field(..., description="资源 ID") # C# 是 long, Python 中 int 可以表示任意大小整数

    model_config = ConfigDict(json_schema_extra={"example": {"id": 123}})

class BaseIdResponseDto(BaseModel):
    """通用的只返回 ID 的响应 DTO"""
    id: int = Field(..., description="资源 ID")

    model_config = ConfigDict(json_schema_extra={"example": {"id": 123}})

# 文档所属应用类型枚举 (对应 C# DocumentAppType)
from enum import Enum, IntEnum

class DocumentAppType(IntEnum):
    """文档所属源枚举"""
    PKB = 1                   # 个人知识库
    SOCIAL_CONTENT = 2        # 社交内容
    CUSTOMER_SERVICE = 3      # 智能客服
    PODCAST = 4               # 播客
    INTERVIEW = 5             # AI面试官