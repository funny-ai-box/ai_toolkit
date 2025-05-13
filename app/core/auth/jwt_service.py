# app/core/auth/jwt_service.py
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from app.core.config.settings import Settings
from app.core.redis.service import RedisService # 假设 RedisService 可用
from app.core.utils.snowflake import generate_id

class TokenPayload(BaseModel):
    """JWT 令牌载荷模型"""
    sub: str = Field(..., description="令牌主题 (用户 ID)")
    exp: Optional[int] = Field(None, description="过期时间戳")
    iat: Optional[int] = Field(None, description="签发时间戳")
    jti: Optional[str] = Field(None, description="JWT ID (唯一标识符)")
    # --- 自定义声明 ---
    mobile: Optional[str] = Field(None, description="用户手机号 (可选)")
    # 可以添加其他需要的声明，例如用户角色等
    # roles: List[str] = []

class JwtService:
    """
    提供 JWT 生成、验证和撤销功能的服务类。
    """
    def __init__(self, settings: Settings, redis_service: RedisService):
        self.settings = settings
        self.redis_service = redis_service
        self.SECRET_KEY = settings.SECRET_KEY
        self.ALGORITHM = settings.JWT_ALGORITHM
        self.ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

    async def generate_token(self, user_id: int, mobile_no: str) -> Tuple[str, datetime]:
        """
        生成访问令牌并将其存储到 Redis。

        Args:
            user_id: 用户 ID。
            mobile_no: 用户手机号。

        Returns:
            一个元组，包含生成的令牌字符串和令牌的过期时间 (datetime 对象)。
        """
        now = datetime.now(timezone.utc)
        expire_delta = timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        expire_at = now + expire_delta
        jwt_id = str(generate_id()) # 使用雪花 ID 作为 JTI，确保唯一性

        # 构建令牌载荷
        to_encode = TokenPayload(
            sub=str(user_id),
            exp=int(expire_at.timestamp()), # JWT 标准使用 Unix 时间戳 (秒)
            iat=int(now.timestamp()),
            jti=jwt_id,
            mobile=mobile_no
        ).model_dump(exclude_none=True) # 移除 None 值

        # 编码令牌
        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)

        # 将令牌存储到 Redis，过期时间与 JWT 令牌过期时间一致
        # 注意：Redis 过期时间是秒
        redis_key = f"user:token:{user_id}"
        success = await self.redis_service.set_async(
            redis_key,
            encoded_jwt,
            expiry_seconds=int(expire_delta.total_seconds())
        )
        if not success:
            # 记录日志或抛出异常，表示 Redis 存储失败
            print(f"警告: 存储用户 {user_id} 的令牌到 Redis 失败。")
            # raise CacheError("无法存储令牌到 Redis")

        return encoded_jwt, expire_at

    def validate_token(self, token: str) -> Optional[TokenPayload]:
        """
        验证JWT令牌并增强错误处理
        """
        # 先不验证签名解码，用于调试
        try:
            # 正确方式：即使不验证签名也需要提供key参数
            unverified_payload = jwt.decode(
                token,
                self.SECRET_KEY,  # 需要提供key
                options={"verify_signature": False}  # 不验证签名
            )
            print(f"令牌未验证载荷: {unverified_payload}")
            print(f"使用的SECRET_KEY: {self.SECRET_KEY}... 算法: {self.ALGORITHM}")
        except Exception as e:
            print(f"令牌格式错误，无法解码: {e}")
            return None
            
        # 验证令牌
        try:
            payload_dict = jwt.decode(
                token,
                self.SECRET_KEY,
                algorithms=[self.ALGORITHM],
                options={"verify_aud": False}
            )
            print(f"验证成功，载荷: {payload_dict}")
            token_data = TokenPayload(**payload_dict)
            return token_data
        except jwt.ExpiredSignatureError:
            print("令牌已过期")
            return None
        except jwt.JWTClaimsError as e:
            print(f"令牌声明错误: {e}")
            return None
        except JWTError as e:
            print(f"令牌验证失败: {e}")
            # 添加更多诊断信息
            print(f"使用的SECRET_KEY长度: {len(self.SECRET_KEY)}, 算法: {self.ALGORITHM}")
            return None
        except Exception as e:
            print(f"令牌解码或验证时发生未知错误: {e}")
            return None

    async def revoke_token(self, user_id: int) -> bool:
        """
        通过从 Redis 中删除令牌来撤销用户的当前令牌。

        Args:
            user_id: 用户 ID。

        Returns:
            如果成功删除返回 True，否则返回 False。
        """
        redis_key = f"user:token:{user_id}"
        return await self.redis_service.key_delete_async(redis_key)