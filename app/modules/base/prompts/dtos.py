# app/modules/base/prompts/dtos.py
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional

# --- 请求 DTOs ---

class PromptTemplateAddRequestDto(BaseModel):
    """添加提示词模板请求 DTO"""
    template_key: str = Field(..., max_length=50, description="模板唯一 Key", alias="templateKey")
    template_desc: str = Field(..., max_length=250, description="模板描述", alias="templateDesc")
    template_content: str = Field(..., max_length=10000, description="模板内容", alias="templateContent")

    model_config = ConfigDict(
        populate_by_name=True, # 允许别名填充
        json_schema_extra={
            "example": {
                "templateKey": "EXAMPLE_PROMPT",
                "templateDesc": "一个示例提示词模板",
                "templateContent": "这是提示词的内容，可以使用 {variable} 占位符。"
            }
        }
    )

    # 可以在这里添加对 template_key 格式的验证，例如不允许空格等
    @field_validator('template_key')
    def validate_template_key(cls, v):
        if not v or ' ' in v:
            raise ValueError('模板 Key 不能为空且不能包含空格')
        # 可以添加更多验证规则，比如只允许大写字母、数字和下划线
        # if not re.match(r'^[A-Z0-9_]+$', v):
        #     raise ValueError('模板 Key 只能包含大写字母、数字和下划线')
        return v

class PromptTemplateUpdateRequestDto(PromptTemplateAddRequestDto):
    """更新提示词模板请求 DTO"""
    id: int = Field(..., description="要更新的模板 ID") # C# 是 long, Python int 即可

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "id": 123,
                "templateKey": "EXAMPLE_PROMPT_UPDATED",
                "templateDesc": "更新后的示例提示词模板",
                "templateContent": "这是更新后的提示词内容，可以使用 {variable} 占位符。"
            }
        }
    )


# --- 响应 DTOs ---

class PromptTemplateResponseDto(BaseModel):
    """提示词模板响应 DTO"""
    id: int = Field(..., description="模板 ID")
    template_key: str = Field(..., description="模板 Key", alias="templateKey")
    template_desc: str = Field(..., description="模板描述", alias="templateDesc")
    template_content: str = Field(..., description="模板内容", alias="templateContent")

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda field_name: field_name.replace('_', ' ').title().replace(' ', ''), # 自动转 camelCase
        json_schema_extra={
            "example": {
                "id": 123,
                "templateKey": "EXAMPLE_PROMPT",
                "templateDesc": "一个示例提示词模板",
                "templateContent": "这是提示词的内容..."
            }
        }
    )