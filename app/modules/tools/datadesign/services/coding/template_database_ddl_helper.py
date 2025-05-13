from typing import Optional
from app.modules.tools.datadesign.enums import DatabaseType
from app.core.exceptions import BusinessException # Assuming this exists

def get_data_type_for_database(
    data_type: Optional[str], 
    database_type: DatabaseType, 
    length: Optional[int], 
    precision: Optional[int], 
    scale: Optional[int]
) -> str:
    """
    获取指定数据库的数据类型

    Args:
        data_type (str): 通用数据类型 (小写)
        database_type (DatabaseType): 数据库类型
        length (Optional[int]): 长度
        precision (Optional[int]): 精度
        scale (Optional[int]): 小数位数

    Returns:
        str: 数据库特定数据类型
    """
    dt_lower = data_type.lower() if data_type else ""

    if database_type == DatabaseType.MYSQL:
        if dt_lower in ["int", "integer"]:
            return "INT"
        if dt_lower in ["long", "bigint"]:
            return "BIGINT"
        if dt_lower == "decimal":
            return f"DECIMAL({precision or 10},{scale or 2})"
        if dt_lower == "float":
            return "FLOAT"
        if dt_lower == "double":
            return "DOUBLE"
        if dt_lower in ["string", "varchar"]:
            return f"VARCHAR({length or 255})"
        if dt_lower == "text":
            return "TEXT"
        if dt_lower == "longtext":
            return "LONGTEXT"
        if dt_lower == "date":
            return "DATE"
        if dt_lower == "datetime":
            return "DATETIME"
        if dt_lower == "timestamp":
            return "TIMESTAMP"
        if dt_lower in ["bool", "boolean"]:
            return "TINYINT(1)"
        return dt_lower.upper() if dt_lower else "VARCHAR(255)" # Fallback for unknown
    
    elif database_type == DatabaseType.SQLSERVER:
        if dt_lower in ["int", "integer"]:
            return "INT"
        if dt_lower in ["long", "bigint"]:
            return "BIGINT"
        if dt_lower == "decimal":
            return f"DECIMAL({precision or 10},{scale or 2})"
        if dt_lower == "float":
            return "FLOAT" # SQL Server FLOAT is double precision by default (FLOAT(53))
        if dt_lower == "double":
            return "FLOAT(53)"
        if dt_lower in ["string", "varchar"]:
            return f"NVARCHAR({length or 255})"
        if dt_lower in ["text", "longtext"]:
            return "NVARCHAR(MAX)"
        if dt_lower == "date":
            return "DATE"
        if dt_lower == "datetime":
            return "DATETIME2"
        if dt_lower == "timestamp": # SQL Server TIMESTAMP is rowversion, not for time
            return "DATETIME2"
        if dt_lower in ["bool", "boolean"]:
            return "BIT"
        return dt_lower.upper() if dt_lower else "NVARCHAR(255)"

    elif database_type == DatabaseType.ORACLE:
        if dt_lower in ["int", "integer"]:
            return "NUMBER(10)"
        if dt_lower in ["long", "bigint"]:
            return "NUMBER(19)"
        if dt_lower == "decimal":
            return f"NUMBER({precision or 10},{scale or 2})"
        if dt_lower == "float":
            return "FLOAT" # Oracle FLOAT is an alias for NUMBER
        if dt_lower == "double":
            return "FLOAT(126)" # Or NUMBER for more precision control
        if dt_lower in ["string", "varchar"]:
            # Max length for VARCHAR2 is 4000 bytes. Consider CLOB for larger.
            actual_length = length or 255
            if actual_length > 4000: # Oracle specific limit for VARCHAR2 in bytes
                return "CLOB" 
            return f"VARCHAR2({actual_length})"
        if dt_lower in ["text", "longtext"]:
            return "CLOB"
        if dt_lower == "date":
            return "DATE" # Oracle DATE includes time component
        if dt_lower == "datetime":
            return "TIMESTAMP"
        if dt_lower == "timestamp":
            return "TIMESTAMP"
        if dt_lower in ["bool", "boolean"]:
            return "NUMBER(1)" # Typically 0 for false, 1 for true
        return dt_lower.upper() if dt_lower else "VARCHAR2(255)"

    return dt_lower.upper() if dt_lower else "VARCHAR(255)" # Generic fallback

def get_ddl_template(database_type: DatabaseType) -> str:
    """
    获取DDL模板

    Args:
        database_type (DatabaseType): 数据库类型

    Returns:
        str: DDL模板字符串
    """
    if database_type == DatabaseType.MYSQL:
        return """-- MySQL DDL Script
-- Generated at {{now}}

{{#tables}}
-- Table: {{name}}
-- Comment: {{comment}}
CREATE TABLE `{{name}}` (
{{#fields}}
    `{{name}}` {{dataType}}{{#isPrimaryKey}} PRIMARY KEY{{/isPrimaryKey}}{{#isAutoIncrement}} AUTO_INCREMENT{{/isAutoIncrement}}{{^isNullable}} NOT NULL{{/isNullable}}{{#isNullable}} NULL{{/isNullable}}{{#defaultValue}} DEFAULT {{{defaultValue}}}{{/defaultValue}} COMMENT '{{comment}}'{{^last}},{{/last}}
{{/fields}}
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='{{comment}}';

{{#indexes}}
{{#type}}
-- Index: {{name}}
CREATE {{type}} INDEX `{{name}}` ON `{{tablename}}` ({{{fields}}});
{{/type}}
{{/indexes}}

{{/tables}}"""

    elif database_type == DatabaseType.SQLSERVER:
        return """-- SQL Server DDL Script
-- Generated at {{now}}

{{#tables}}
-- Table: {{name}}
-- Comment: {{comment}}
CREATE TABLE [{{name}}] (
{{#fields}}
    [{{name}}] {{dataType}}{{^isNullable}} NOT NULL{{/isNullable}}{{#isNullable}} NULL{{/isNullable}}{{#defaultValue}} DEFAULT {{{defaultValue}}}{{/defaultValue}}{{#isPrimaryKey}} PRIMARY KEY{{#isAutoIncrement}} IDENTITY(1,1){{/isAutoIncrement}}{{/isPrimaryKey}}{{^last}},{{/last}}
{{/fields}}
);

-- Add table comment
EXEC sp_addextendedproperty 'MS_Description', N'{{comment}}', 'SCHEMA', 'dbo', 'TABLE', N'{{name}}', NULL, NULL;

{{#fields}}
-- Add column comment for {{name}} in table {{tablename}}
EXEC sp_addextendedproperty 'MS_Description', N'{{comment}}', 'SCHEMA', 'dbo', 'TABLE', N'{{tablename}}', 'COLUMN', N'{{name}}';
{{/fields}}

{{#indexes}}
{{#type}}
-- Index: {{name}}
CREATE {{type}} INDEX [{{name}}] ON [{{tablename}}] ({{{fields}}});
{{/type}}
{{/indexes}}

{{/tables}}"""

    elif database_type == DatabaseType.ORACLE:
        return """-- Oracle DDL Script
-- Generated at {{now}}

{{#tables}}
-- Table: {{name}}
-- Comment: {{comment}}
CREATE TABLE {{name}} (
{{#fields}}
    {{name}} {{dataType}}{{^isNullable}} NOT NULL{{/isNullable}}{{#isNullable}} NULL{{/isNullable}}{{#defaultValue}} DEFAULT {{{defaultValue}}}{{/defaultValue}}{{^last}},{{/last}}
{{/fields}}
);

-- Add primary key for {{name}}
{{#primaryKey}}
ALTER TABLE {{tablename}} ADD CONSTRAINT PK_{{tablename}} PRIMARY KEY ({{name}});
{{/primaryKey}}

-- Add table comment for {{name}}
COMMENT ON TABLE {{name}} IS '{{comment}}';

{{#fields}}
-- Add column comment for {{name}} in table {{tablename}}
COMMENT ON COLUMN {{tablename}}.{{name}} IS '{{comment}}';
{{/fields}}

{{#indexes}}
{{#type}}
-- Index: {{name}}
CREATE {{type}} INDEX {{name}} ON {{tablename}} ({{{fields}}});
{{/type}}
{{/indexes}}

{{/tables}}"""
    else:
        raise BusinessException(f"不支持的数据库类型: {database_type}")