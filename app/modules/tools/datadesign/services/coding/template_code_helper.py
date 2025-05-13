import re
from app.modules.tools.datadesign.enums import LanguageType

def get_data_type_for_language(data_type: str, language: LanguageType) -> str:
    """
    获取编程语言的数据类型

    Args:
        data_type (str): 通用数据类型 (小写)
        language (LanguageType): 编程语言

    Returns:
        str: 编程语言特定数据类型
    """
    dt_lower = data_type.lower() if data_type else ""

    if language == LanguageType.CSHARP:
        if dt_lower in ["int", "integer"]:
            return "int"
        if dt_lower in ["long", "bigint"]:
            return "long"
        if dt_lower == "decimal":
            return "decimal"
        if dt_lower == "float":
            return "float"
        if dt_lower == "double":
            return "double"
        if dt_lower in ["string", "varchar", "text", "longtext"]:
            return "string"
        if dt_lower in ["date", "datetime", "timestamp"]:
            return "DateTime"
        if dt_lower in ["bool", "boolean"]:
            return "bool"
        return "object"
    elif language == LanguageType.PYTHON:
        if dt_lower in ["int", "integer", "long", "bigint"]:
            return "int"
        if dt_lower in ["decimal", "float", "double"]:
            return "float" # Pydantic/SQLAlchemy use float for these generally
        if dt_lower in ["string", "varchar", "text", "longtext"]:
            return "str"
        if dt_lower in ["date", "datetime", "timestamp"]:
            return "datetime.datetime" # For type hints
        if dt_lower in ["bool", "boolean"]:
            return "bool"
        return "object" # Or 'Any' for type hints
    elif language == LanguageType.JAVA: # Added for completeness based on C# initializer
        if dt_lower in ["int", "integer"]:
            return "Integer" # Or int for primitive
        if dt_lower in ["long", "bigint"]:
            return "Long"
        if dt_lower == "decimal":
            return "java.math.BigDecimal"
        if dt_lower == "float":
            return "Float"
        if dt_lower == "double":
            return "Double"
        if dt_lower in ["string", "varchar", "text", "longtext"]:
            return "String"
        if dt_lower == "date":
            return "java.time.LocalDate" # Or java.sql.Date
        if dt_lower in ["datetime", "timestamp"]:
            return "java.time.LocalDateTime" # Or java.sql.Timestamp
        if dt_lower in ["bool", "boolean"]:
            return "Boolean" # Or boolean for primitive
        return "Object"
    return dt_lower


def to_pascal_case(input_str: str) -> str:
    """
    将下划线或混合命名的字符串转换为PascalCase

    Args:
        input_str (str): 输入字符串

    Returns:
        str: PascalCase字符串
    """
    if not input_str:
        return ""
    # Replace non-alphanumeric with underscore, then split by underscore
    s = re.sub(r'[^a-zA-Z0-9]+', '_', input_str)
    return "".join(word.capitalize() for word in s.split('_') if word)


def to_camel_case(input_str: str) -> str:
    """
    将下划线或混合命名的字符串转换为camelCase

    Args:
        input_str (str): 输入字符串

    Returns:
        str: camelCase字符串
    """
    pascal = to_pascal_case(input_str)
    if not pascal:
        return ""
    return pascal[0].lower() + pascal[1:]

def to_snake_case(input_str: str) -> str:
    """
    将PascalCase或camelCase字符串转换为snake_case.
    """
    if not input_str:
        return ""
    # Insert an underscore before any uppercase letter that is not at the beginning
    # and is preceded by a lowercase letter or followed by a lowercase letter.
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', input_str)
    # Insert an underscore before any uppercase letter that is followed by an uppercase letter then a lowercase letter.
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1)
    return s2.lower()