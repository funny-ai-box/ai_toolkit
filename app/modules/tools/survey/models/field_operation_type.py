from enum import Enum

class FieldOperationType(str, Enum):
    """字段变更操作类型枚举"""
    ADD = "Add"     # 新增
    UPDATE = "Update"  # 更新
    DELETE = "Delete"  # 删除
