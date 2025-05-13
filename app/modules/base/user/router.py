# app/modules/base/user/router.py
from fastapi import APIRouter, Depends, Body, HTTPException, status, Request # 添加 Request
import logging # 添加 logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
# --- 导入修改后的依赖项 ---
from app.api.dependencies import (
    get_current_active_user_id,
    get_jwt_service_from_state, # 使用从 state 获取
    get_redis_service_from_state, # 使用从 state 获取
    RateLimiter
)
# --------------------------

from .dtos import (
    UserRegisterDto, UserLoginDto, UserInfoDto, LoginResultDto,
    SendVerifiCodeDto, UserUpdatePwdDto
)
from app.core.dtos import ApiResponse
from app.core.config.settings import settings

from typing import TYPE_CHECKING # 添加 TYPE_CHECKING

# --- 类型检查导入 ---
if TYPE_CHECKING:
    from app.modules.base.user.repositories.user_repository import UserRepository
    from app.core.auth.jwt_service import JwtService
    from app.core.redis.service import RedisService 
# --------------------
if TYPE_CHECKING:
    from .services.user_service import UserService

# 获取 logger
logger = logging.getLogger(__name__)

# 创建用户管理路由
router = APIRouter(
    prefix="/user",
    tags=["Base - User Management"]
)

# --- 辅助函数：获取 UserService 实例 (修改为使用 state 依赖) ---
def _get_user_service(
    db: AsyncSession = Depends(get_db),
    # 从全局依赖获取核心服务
    jwt_service: 'JwtService' = Depends(get_jwt_service_from_state),
    redis_service: 'RedisService' = Depends(get_redis_service_from_state),
) -> 'UserService':
    """内部依赖项：创建并返回 UserService 实例"""
    # 在函数内部导入，避免潜在问题
    from .repositories.user_repository import UserRepository # 相对导入
    from .services.user_service import UserService
    if TYPE_CHECKING: # 类型检查
        from app.core.auth.jwt_service import JwtService
        from app.core.redis.service import RedisService
        assert isinstance(jwt_service, JwtService)
        assert isinstance(redis_service, RedisService)

    # UserService 内部创建 UserRepository
    user_repo = UserRepository(db=db)
    return UserService(
        db=db,
        user_repository=user_repo, # 传递创建的 repo
        jwt_service=jwt_service,
        redis_service=redis_service,
        settings=settings
    )

# --- API 端点定义 ---

@router.post(
    "/register",
    response_model=ApiResponse[UserInfoDto], # 指定响应模型，包装在 ApiResponse 中
    summary="用户注册",
    description="新用户通过手机号和验证码进行注册。",
    status_code=status.HTTP_201_CREATED, # 注册成功返回 201
    # C# RateLimit(5, 60, RateLimitType.IP)
    dependencies=[Depends(RateLimiter(limit=5, period_seconds=60, limit_type="ip"))]
)
async def register(
    register_dto: UserRegisterDto = Body(...), # 从请求体获取数据
    user_service: 'UserService' = Depends(_get_user_service)
):
    """
    用户注册接口。

    - **mobileNo**: 手机号码 (必填)
    - **verifiCode**: 短信验证码 (必填)
    - **name**: 用户昵称 (必填, 2-50 字符)
    - **password**: 登录密码 (必填, 6-20 字符)
    """
    # 注意：全局异常处理器会处理 BusinessException
    user_info = await user_service.register_async(register_dto)
    return ApiResponse.success(data=user_info, message="注册成功", code=status.HTTP_201_CREATED)

@router.post(
    "/login",
    response_model=ApiResponse[LoginResultDto], # 响应包含用户信息和令牌
    summary="用户登录",
    description="用户使用手机号和密码进行登录。",
    # C# RateLimit(10, 60, RateLimitType.IP)
    dependencies=[Depends(RateLimiter(limit=10, period_seconds=60, limit_type="ip"))]
)
async def login(
    login_dto: UserLoginDto = Body(...),
    user_service: 'UserService' = Depends(_get_user_service)
):
    """
    用户登录接口。

    - **mobileNo**: 手机号码 (必填)
    - **password**: 登录密码 (必填)
    """
    login_result = await user_service.login_async(login_dto)
    return ApiResponse.success(data=login_result, message="登录成功")


@router.post(
    "/sendverificode",
    response_model=ApiResponse[None], # 成功时不返回特定数据
    summary="发送验证码",
    description="根据场景类型和场景 Key (手机号/用户ID) 发送短信验证码。",
    # C# RateLimit(10, 60, RateLimitType.IP)
    dependencies=[Depends(RateLimiter(limit=10, period_seconds=60, limit_type="ip"))]
)
async def send_verifi_code(
    request_dto: SendVerifiCodeDto = Body(...),
    user_service: 'UserService' = Depends(_get_user_service)
):
    """
    发送短信验证码接口。

    - **sceneKey**: 场景 Key，注册/登录时为手机号，修改密码时为用户 ID (必填)
    - **sceneType**: 场景类型 (Register, UpdatePwd) (必填)
    """
    success = await user_service.send_verifi_code(request_dto)
    if success:
        return ApiResponse.success(message="验证码发送成功")
    else:
        # 虽然服务层目前是模拟发送总返回 True，但保留失败分支
        # 服务层的 BusinessException 会被全局处理器捕获
        # 如果 send_verifi_code 返回 False，则表示非异常的失败
        return ApiResponse.fail(message="验证码发送失败", code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@router.post(
    "/updatepwd",
    response_model=ApiResponse[None],
    summary="修改密码 (需要登录)",
    description="登录用户使用验证码修改自己的登录密码。",
    # C# RateLimit(10, 60, RateLimitType.IP) - C# 代码中这个接口允许匿名但又获取了 UserID? 逻辑似乎矛盾
    # 这里改为需要用户登录才能修改密码，并按用户限流
    # 如果确实需要匿名修改（比如忘记密码流程），则需要调整认证和 sceneKey 逻辑
    dependencies=[
        Depends(RateLimiter(limit=10, period_seconds=60, limit_type="user")),
        Depends(get_current_active_user_id) # 确保用户已登录
    ]
)
async def update_password(
    request_dto: UserUpdatePwdDto = Body(...),
    user_service: 'UserService' = Depends(_get_user_service),
    current_user_id: int = Depends(get_current_active_user_id) # 再次注入以获取用户ID
):
    """
    修改当前登录用户的密码。

    - **verifiCode**: 短信验证码 (必填)
    - **password**: 新密码 (必填, 6-20 字符)

    *需要有效的登录令牌 (Authorization header)*
    """
    # 注意：发送验证码时，场景 Key 应为当前登录用户的 ID
    # 前端调用 /sendverificode 时应传入 sceneType=UpdatePwd, sceneKey=当前用户ID
    success = await user_service.update_pwd(current_user_id, request_dto)
    if success:
        return ApiResponse.success(message="密码修改成功")
    else:
        # 同样，保留失败分支
        return ApiResponse.fail(message="密码修改失败", code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@router.post(
    "/info",
    response_model=ApiResponse[UserInfoDto],
    summary="获取当前用户信息 (需要登录)",
    description="获取当前已登录用户的基本信息。",
    # C# RateLimit(100, 60, RateLimitType.User)
    dependencies=[
        Depends(RateLimiter(limit=100, period_seconds=60, limit_type="user")),
        Depends(get_current_active_user_id) # 确保用户已登录
    ]
)
async def get_user_info(
    user_service: 'UserService' = Depends(_get_user_service),
    current_user_id: int = Depends(get_current_active_user_id) # 注入验证后的用户ID
):
    """
    获取当前登录用户的信息。

    *需要有效的登录令牌 (Authorization header)*
    """
    user_info = await user_service.get_user_info_async(current_user_id)
    return ApiResponse.success(data=user_info)


@router.post(
    "/logout",
    response_model=ApiResponse[None],
    summary="退出登录 (需要登录)",
    description="使当前用户的访问令牌失效。",
    # C# RateLimit(30, 60, RateLimitType.User)
    dependencies=[
        Depends(RateLimiter(limit=30, period_seconds=60, limit_type="user")),
        Depends(get_current_active_user_id) # 确保用户已登录
    ]
)
async def logout(
    user_service: 'UserService' = Depends(_get_user_service),
    current_user_id: int = Depends(get_current_active_user_id) # 注入用户ID
):
    """
    退出当前登录用户的会话。

    *需要有效的登录令牌 (Authorization header)*
    """
    success = await user_service.logout_async(current_user_id)
    if success:
        return ApiResponse.success(message="退出登录成功")
    else:
        # 登出失败通常意味着令牌已经不在 Redis 中，但也算成功登出
        # 可以考虑始终返回成功，或者记录日志
        print(f"用户 {current_user_id} 登出时 Redis 操作可能未删除 key (或 key 本不存在)")
        return ApiResponse.success(message="退出登录成功")