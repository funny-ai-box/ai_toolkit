# app/api/dependencies.py
import time
import logging
import httpx
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import JWTError
from pydantic import ValidationError
from typing import Optional, Any, TYPE_CHECKING # <--- 导入 TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db
from app.core.config.settings import settings
from app.core.auth.jwt_service import TokenPayload # TokenPayload 还是需要的
from app.core.exceptions import UnauthorizedException, ForbiddenException, NotFoundException


# --- 类型检查时导入 (避免运行时循环导入) ---
if TYPE_CHECKING:
    from httpx import AsyncClient
    from app.core.redis.service import RedisService
    from app.core.auth.jwt_service import JwtService
    from app.core.ai.vector.base import IMilvusService, IUserDocsMilvusService
    from app.core.ai.chat.base import IChatAIService
    from app.core.storage.base import IStorageService
    from app.modules.base.user.repositories.user_repository import UserRepository    
    from app.modules.base.prompts.repositories import PromptTemplateRepository
    from app.modules.base.prompts.services import PromptTemplateService
    from app.core.job.services import JobPersistenceService
# -----------------------------------------

# --- 获取 logger ---
logger = logging.getLogger(__name__)

# --- OAuth2 Scheme (保持不变) ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user/login")

# --- 从 app.state 获取服务的依赖项 ---

def get_redis_service_from_state(request: Request) -> 'RedisService':
    """依赖项：从 app.state 获取 RedisService 实例"""
    redis_service = getattr(request.app.state, 'redis_service', None)
    if redis_service is None:
        logger.error("依赖项错误：RedisService 未在 app.state 中找到。")
        raise RuntimeError("Redis 服务未初始化。")
    # 可选的类型检查 (只在 TYPE_CHECKING 为 True 时有效)
    if TYPE_CHECKING:
        from app.core.redis.service import RedisService
        assert isinstance(redis_service, RedisService)
    return redis_service

def get_jwt_service_from_state(request: Request) -> 'JwtService':
    """依赖项：从 app.state 获取 JwtService 实例"""
    jwt_service = getattr(request.app.state, 'jwt_service', None)
    if jwt_service is None:
        logger.error("依赖项错误：JwtService 未在 app.state 中找到。")
        raise RuntimeError("JWT 服务未初始化。")
    if TYPE_CHECKING:
        from app.core.auth.jwt_service import JwtService
        assert isinstance(jwt_service, JwtService)
    return jwt_service

def get_milvus_service_from_state(request: Request) -> 'IMilvusService': # 使用协议
    """依赖项：从 app.state 获取 MilvusService 实例"""
    milvus_service = getattr(request.app.state, 'milvus_service', None)
    if milvus_service is None:
        logger.error("依赖项错误：MilvusService 未在 app.state 中找到。")
        raise RuntimeError("Milvus 服务未初始化。")
    if TYPE_CHECKING:
        from app.core.ai.vector.base import IMilvusService
        # 注意：协议检查用 issubclass 或 Protocol.__isinstancecheck__，但这里用类型提示足够
        # assert isinstance(milvus_service, IMilvusService) # Protocol 不能直接用 isinstance
    return milvus_service


def get_user_docs_milvus_service_from_state(request: Request) -> 'IUserDocsMilvusService': # 使用协议
    """依赖项：从 app.state 获取 UserDocsMilvusService 实例"""
    user_docs_milvus_service = getattr(request.app.state, 'user_docs_milvus_service', None)
    if user_docs_milvus_service is None:
        logger.error("依赖项错误：UserDocsMilvusService 未在 app.state 中找到。")
        raise RuntimeError("User Docs Milvus 服务未初始化。")
    return user_docs_milvus_service

# 获取共享 HTTP 客户端的依赖（包含代理能力）
def get_http_client_from_state(request: Request) -> Optional[httpx.AsyncClient]:
    """依赖项：从 app.state 获取共享的 httpx.AsyncClient 实例"""
    http_client = getattr(request.app.state, 'http_client', None)
    # 不需要报错，允许返回 None，让服务自己处理
    # if http_client is None:
    #     logger.error("依赖项错误：共享 HTTP 客户端未在 app.state 中找到。")
    #     raise RuntimeError("共享 HTTP 客户端不可用。")
    if TYPE_CHECKING:
         if http_client is not None: assert isinstance(http_client, httpx.AsyncClient)
    return http_client

def get_chatai_service_from_state(request: Request) -> 'IChatAIService': # 使用协议
    """依赖项：从 app.state 获取 AIService 实例"""
    ai_service = getattr(request.app.state, 'ai_services', None)
    if ai_service is None:
        logger.error("依赖项错误：AIService 未在 app.state 中找到或初始化失败。")
        raise RuntimeError("AI 服务不可用。")
    return ai_service

def get_storage_service_from_state(request: Request) -> Optional['IStorageService']: # 使用协议, 可选
    """依赖项：从 app.state 获取配置的 StorageService 实例 (可能为 None)"""
    storage_service = getattr(request.app.state, 'storage_service', None)
    return storage_service

def get_speech_service_from_state(request: Request) -> Optional[Any]: # Change type hint
    """依赖项：从 app.state 获取 speech_service 实例 (可能为 None)"""
    speech_service = getattr(request.app.state, 'speech_service', None)
    return speech_service

# # --- 仓库依赖项  ---
# def get_user_repository(db: AsyncSession = Depends(get_db)) -> 'UserRepository': # 使用字符串
#     """依赖项：获取 UserRepository 实例"""
#     from app.modules.base.user.repositories.user_repository import UserRepository # 在函数内部导入，避免全局循环
#     return UserRepository(db=db)

# --- 添加 Job Persistence Service 依赖项工厂 ---
def get_job_persistence_service(db: AsyncSession = Depends(get_db)) -> 'JobPersistenceService':
    """依赖项：获取 JobPersistenceService 实例"""
    # 在函数内部导入，避免潜在的启动循环依赖
    from app.core.job.services import JobPersistenceService
    # JobPersistenceService 只需要数据库会话
    return JobPersistenceService(db=db)


# --- 添加 Prompts 模块的依赖项工厂 ---

def get_prompt_template_repository(db: AsyncSession = Depends(get_db)) -> 'PromptTemplateRepository':
    """依赖项：获取 PromptTemplateRepository 实例"""
    # 在函数内部导入以避免启动时的循环依赖问题
    from app.modules.base.prompts.repositories import PromptTemplateRepository
    return PromptTemplateRepository(db=db)

def get_prompt_template_service(
    db: AsyncSession = Depends(get_db), # Service 可能也需要 db 操作或传递给 Repo
    repo: 'PromptTemplateRepository' = Depends(get_prompt_template_repository),
    redis_service: 'RedisService' = Depends(get_redis_service_from_state) # 使用从 state 获取的 redis
) -> 'PromptTemplateService':
    """依赖项：获取 PromptTemplateService 实例"""
    # 在函数内部导入
    from app.modules.base.prompts.services import PromptTemplateService
    # 类型检查
    if TYPE_CHECKING:
        from app.modules.base.prompts.repositories import PromptTemplateRepository
        from app.core.redis.service import RedisService
        assert isinstance(repo, PromptTemplateRepository)
        assert isinstance(redis_service, RedisService)

    return PromptTemplateService(db=db, repository=repo, redis_service=redis_service)

# -------------------------------------

# --- 认证/授权依赖项 (现在可以进行类型检查了) ---
async def get_current_active_user_id(
    token: str = Depends(oauth2_scheme),
    redis_service: 'RedisService' = Depends(get_redis_service_from_state),
    jwt_service: 'JwtService' = Depends(get_jwt_service_from_state)
) -> int:
    """
    依赖项：验证令牌（签名、过期时间、Redis存在性、一致性）并返回用户ID。
    """
    # 类型检查（可选，但推荐）
    if TYPE_CHECKING:
        from app.core.redis.service import RedisService
        from app.core.auth.jwt_service import JwtService
        assert isinstance(redis_service, RedisService)
        assert isinstance(jwt_service, JwtService)
    print(f"获取当前用户 ID: {token=}, {redis_service=}, {jwt_service=}") # 调试输出

    credentials_exception = UnauthorizedException(
        message="无法验证凭据或令牌无效",
    )
    payload = jwt_service.validate_token(token)
    if payload is None or payload.sub is None:
        raise credentials_exception

    redis_key = f"user:token:{payload.sub}"
    stored_token = await redis_service.get_async(redis_key)
    if stored_token is None or stored_token != token:
        logger.warning(f"用户 {payload.sub} 的令牌验证失败 (Redis 不存在或不匹配)。")
        raise UnauthorizedException(message="登录已失效或已在别处登录")

    try:
        user_id = int(payload.sub)
        logger.debug(f"用户 {user_id} 令牌验证通过。")
        return user_id
    except ValueError:
        raise credentials_exception

# --- 可选用户 ID 依赖项 (现在可以进行类型检查了) ---
async def get_optional_user_id_from_token(
    request: Request,
    redis_service: 'RedisService' = Depends(get_redis_service_from_state),
    jwt_service: 'JwtService' = Depends(get_jwt_service_from_state)
) -> Optional[int]:
    """
    尝试从请求头中获取并验证令牌，如果有效则返回用户 ID，否则返回 None。
    不抛出异常。
    """
    if TYPE_CHECKING:
        from app.core.redis.service import RedisService
        from app.core.auth.jwt_service import JwtService
        assert isinstance(redis_service, RedisService)
        assert isinstance(jwt_service, JwtService)

    auth_header = request.headers.get("Authorization")
    token: Optional[str] = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

    if not token: return None

    payload = jwt_service.validate_token(token)
    if payload is None or payload.sub is None: return None

    redis_key = f"user:token:{payload.sub}"
    stored_token = await redis_service.get_async(redis_key)
    if stored_token is None or stored_token != token: return None

    try:
        return int(payload.sub)
    except ValueError:
        return None


# --- 限流器依赖项 (RateLimiterV2) (现在可以进行类型检查了) ---
class RateLimiterV2:
    def __init__(self, limit: int, period_seconds: int, limit_type: str = "ip"):
        self.limit = limit
        self.period_seconds = period_seconds
        self.limit_type = limit_type.lower()

    async def __call__(
        self,
        request: Request,
        redis_service: 'RedisService' = Depends(get_redis_service_from_state),
        optional_user_id: Optional[int] = Depends(get_optional_user_id_from_token)
    ):
        if TYPE_CHECKING:
             from app.core.redis.service import RedisService
             assert isinstance(redis_service, RedisService)
        # ... (内部逻辑不变) ...
        identifier = ""
        path = request.url.path.lower()
        rate_limit_key_prefix = f"ratelimit:{path}"
        client_host = request.client.host if request.client else "unknown_ip"

        if self.limit_type == "user" and optional_user_id is not None:
            identifier = f"user:{optional_user_id}"
            rate_limit_key_prefix += f":user:{optional_user_id}"
        elif self.limit_type == "ip":
            identifier = f"ip:{client_host}"
            rate_limit_key_prefix += f":ip:{client_host}"
        elif self.limit_type == "global":
            identifier = "global"
            rate_limit_key_prefix += ":global"
        else: # 默认或 fallback 按 IP
            identifier = f"ip:{client_host}"
            rate_limit_key_prefix += f":ip:{client_host}"

        allowed = await redis_service.rate_limit_async(
            key_prefix=rate_limit_key_prefix,
            limit=self.limit,
            period_seconds=self.period_seconds
        )

        if not allowed:
            logger.warning(f"速率限制触发: Identifier='{identifier}', Limit={self.limit}/{self.period_seconds}s, Path='{path}'")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试。",
                headers={"Retry-After": str(max(1, self.period_seconds // 2))},
            )

# 使用 RateLimiterV2 作为依赖
RateLimiter = RateLimiterV2
