# app/core/exceptions.py

class BusinessException(Exception):
    """业务逻辑异常基类"""
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)

class NotSupportedException(BusinessException):
    """NotSupport的异常"""
    def __init__(self, message: str = "NotSupported"):
        super().__init__(message, code=405)

class NotFoundException(BusinessException):
    """资源未找到异常"""
    def __init__(self, resource_type: str = "资源", resource_id: any = None):
        message = f"未找到指定的 {resource_type}"
        if resource_id is not None:
            message += f" (ID: {resource_id})"
        super().__init__(message, code=404)

class ValidationException(BusinessException):
    """数据验证异常"""
    def __init__(self, message: str):
        super().__init__(message, code=400)

class UnauthorizedException(BusinessException):
    """未授权异常 (通常指需要登录但未登录)"""
    def __init__(self, message: str = "未授权访问，请先登录"):
        super().__init__(message, code=401)

class ForbiddenException(BusinessException):
    """禁止访问异常 (通常指已登录但无权限)"""
    def __init__(self, message: str = "您没有权限执行此操作"):
        super().__init__(message, code=403)

# 可以根据需要添加更多特定业务异常