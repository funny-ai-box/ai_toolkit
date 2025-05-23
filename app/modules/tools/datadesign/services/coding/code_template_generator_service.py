import json
import logging
from typing import List, Callable, Optional, AsyncGenerator
from app.core.ai.chat.base import IChatAIService, InputMessage # Assuming InputMessage & ChatRoleType in base
from app.core.ai.dtos import ChatRoleType
from app.core.exceptions import BusinessException
from app.modules.tools.datadesign.enums import LanguageType, DatabaseType
from app.modules.tools.datadesign.dtos import CodeTemplateGeneratorDto # Local DTO
from app.modules.tools.datadesign.entities import CodeTemplateDtl # Local Entity

class CodeTemplateGeneratorService:
    """AI生成代码模板的服务"""

    def __init__(self, logger: logging.Logger, ai_service: IChatAIService):
        """
        构造函数

        Args:
            logger (logging.Logger): 日志服务
            ai_service (IChatAIService): AI聊天服务
        """
        self._logger = logger
        self._ai_service = ai_service

    def _get_system_prompt(self, language: LanguageType, database_type: DatabaseType) -> str:
        """获取系统提示词"""
        return f"""你是一个专业的代码模板生成专家。你的任务是为{language.name}语言和{database_type.name}数据库创建一组代码模板，用于生成数据库实体、数据访问层和业务逻辑层的代码。

这些模板将用于从数据库表设计生成代码。模板应当遵循mustache模板语法，使用双大括号表示变量，例如 {{{{tableName}}}}。

你需要支持以下变量：
- tableName: 表名
- tableComment: 表注释
- pascalTableName: 表名的Pascal命名风格 (如user_profile变成UserProfile)
- camelTableName: 表名的Camel命名风格 (如user_profile变成userProfile)
- snake_table_name: 表名的蛇形命名风格 (如UserProfile变成user_profile)
- fields: 字段列表，支持以下属性
  - name: 字段名
  - pascalName: 字段名的Pascal命名风格
  - camelName: 字段名的Camel命名风格
  - comment: 字段注释
  - dataType: 数据类型
  - codeDataType: 代码中使用的数据类型
  - length: 长度 (对于字符串类型)
  - precision: 精度 (对于小数类型)
  - scale: 小数位数 (对于小数类型)
  - isPrimaryKey: 是否为主键
  - isAutoIncrement: 是否自增
  - isNullable: 是否允许为空
  - defaultValue: 默认值
- primaryKey: 主键字段，具有与fields中相同的属性
- indexes: 索引列表，支持以下属性
  - indexName: 索引名称
  - indexType: 索引类型 (如NORMAL、UNIQUE等)
  - fields: 字段列表
    - fieldName: 字段名
    - sortDirection: 排序方向 (ASC或DESC)

你需要为{language.name}语言和{database_type.name}数据库创建以下模板：
1. 实体模板：用于定义数据库实体类
2. 数据访问层模板：用于定义数据访问方法
3. DTO模板：用于定义数据传输对象
4. 业务逻辑层模板：用于定义业务逻辑服务

请以JSON数组格式返回这些模板，每个模板包含以下属性：
1. templateName: 模板名称，使用mustache语法以支持动态文件名
2. templateType: 模板类型，如Entity、Repository、DTO、Service等
3. templateContent: 模板内容，使用mustache语法

请确保你的响应是有效的JSON格式，不要使用 ```json 或 ``` 标记，不要增加双斜杠的备注，会导致解析失败。

示例JSON结构如下：
[
  {{
    "templateName": "{{{{pascalTableName}}}}.py",
    "templateType": "Model",
    "templateContent": "# 这里是模板内容\\nimport something\\n\\n# 更多内容..."
  }},
  {{
    "templateName": "I{{{{pascalTableName}}}}Repository.java",
    "templateType": "Repository Interface",
    "templateContent": "// 这里是模板内容\\nimport java.util.*;\\n\\n// 更多内容..."
  }}
]"""

    async def generate_templates_async(
        self,
        template_id: int,
        language: LanguageType,
        database_type: DatabaseType,
        user_requirements: str,
        on_chunk_received: Optional[Callable[[str], None]] = None
    ) -> List[CodeTemplateDtl]:
        """
        生成代码模板

        Args:
            template_id (int): 模板ID
            language (LanguageType): 编程语言
            database_type (DatabaseType): 数据库类型
            user_requirements (str): 用户的模板规范需求
            on_chunk_received (Optional[Callable[[str], None]]): 接收到数据块时的回调函数

        Returns:
            List[CodeTemplateDtl]: 生成的模板明细列表
        """
        try:
            system_prompt = self._get_system_prompt(language, database_type)
            messages = [
                InputMessage(role=ChatRoleType.SYSTEM, content=system_prompt),
                InputMessage(role=ChatRoleType.USER, content=user_requirements)
            ]

            full_response = ""
            if on_chunk_received:
                async for chunk in self._ai_service.streaming_chat_completion_async(messages):
                    full_response += chunk
                    on_chunk_received(chunk)
            else:
                full_response = await self._ai_service.chat_completion_async(messages)
            
            self._logger.info(f"AI response for template generation: {full_response}")

            try:
                parsed_templates = json.loads(full_response)
            except json.JSONDecodeError as e:
                self._logger.error(f"AI响应JSON解析失败: {e}. Response: {full_response}")
                raise BusinessException("AI响应JSON解析失败，请检查AI输出或提示词。")

            if not isinstance(parsed_templates, list) or not parsed_templates:
                self._logger.warning(f"未能从AI响应中提取有效的模板列表. Response: {full_response}")
                raise BusinessException("未能从AI响应中提取有效的模板列表")

            template_dtls: List[CodeTemplateDtl] = []
            for t_data in parsed_templates:
                if not isinstance(t_data, dict):
                    self._logger.warning(f"模板数据项不是字典格式: {t_data}")
                    continue
                
                # Use Pydantic model for validation and parsing
                try:
                    gen_dto = CodeTemplateGeneratorDto.model_validate(t_data)
                except Exception as e: # Catches Pydantic validation errors
                    self._logger.warning(f"模板数据项验证失败: {e}, data: {t_data}")
                    continue

                template_dtls.append(
                    CodeTemplateDtl(
                        template_id=template_id,
                        file_name=gen_dto.template_name,
                        template_dtl_name=gen_dto.template_type,
                        template_content=gen_dto.template_content,
                    )
                )
            
            if not template_dtls:
                 raise BusinessException("AI成功响应，但未能解析出任何有效的模板详情。")

            return template_dtls

        except BusinessException:
            raise
        except Exception as ex:
            self._logger.error(f"生成代码模板失败: {ex}")
            raise BusinessException(f"生成代码模板时发生内部错误: {str(ex)}")