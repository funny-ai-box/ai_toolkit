import enum

class DatabaseType(enum.IntEnum):
    """数据库类型"""
    MYSQL = 1
    SQLSERVER = 2
    ORACLE = 3

class LanguageType(enum.IntEnum):
    """语言类型"""
    PYTHON = 1
    JAVA = 2
    CSHARP = 3

class AssistantRoleType(enum.IntEnum):
    """助手角色"""
    BUSINESS_ANALYST = 1  # 业务分析角色
    DATABASE_ARCHITECT = 2  # 数据架构角色
    DATABASE_OPERATOR = 3  # 数据运维角色