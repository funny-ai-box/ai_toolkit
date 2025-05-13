# app/api/middleware/exception_handlers.py
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.core.dtos import ApiResponse
from app.core.exceptions import BusinessException, UnauthorizedException, ForbiddenException, NotFoundException, ValidationException

async def business_exception_handler(request: Request, exc: BusinessException):
    """处理自定义的业务异常"""
    # 对于特定类型的业务异常，可以记录不同级别的日志
    # if isinstance(exc, NotFoundException):
    #     # log info
    # elif isinstance(exc, ValidationException):
    #     # log info/warning
    # else:
    #     # log warning/error
    print(f"业务异常捕获: {exc.message}, Code: {exc.code}") # 简单打印，实际应用中应使用 logger
    response = ApiResponse.fail(message=exc.message, code=exc.code)
    return JSONResponse(
        status_code=exc.code, # HTTP 状态码与业务码保持一致
        content=response.model_dump(exclude_none=True) # 序列化 Pydantic 模型
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理 FastAPI 的请求体验证错误 (RequestValidationError)"""
    # 从 Pydantic 错误中提取更友好的信息
    error_messages = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error['loc'] if loc != 'body') # 获取字段路径
        msg = error['msg']
        error_messages.append(f"字段 '{field}': {msg}")

    error_string = "; ".join(error_messages)
    print(f"请求体验证错误: {error_string}") # 简单打印
    response = ApiResponse.fail(message=f"请求参数验证失败: {error_string}", code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response.model_dump(exclude_none=True)
    )

async def general_exception_handler(request: Request, exc: Exception):
    """处理未被捕获的通用异常"""
    # !! 重要: 在生产环境中，不应将详细的错误信息暴露给客户端
    # 这里仅为示例，实际应用中应记录详细错误日志，并返回通用错误信息
    print(f"未处理的服务器内部错误: {exc}") # 简单打印
    # log.error("Unhandled exception", exc_info=exc) # 使用日志记录
    response = ApiResponse.fail(message="服务器内部错误，请稍后重试", code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response.model_dump(exclude_none=True)
    )

# 在 main.py 中注册这些处理器
def register_exception_handlers(app):
    app.add_exception_handler(BusinessException, business_exception_handler)
    # 也可以为 BusinessException 的子类单独注册处理器，如果需要不同处理逻辑
    # app.add_exception_handler(NotFoundException, specific_not_found_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler) # 最后注册通用异常处理器