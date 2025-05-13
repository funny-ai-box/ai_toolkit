# app/core/redis/service.py
import json
from typing import Optional, TypeVar, Any
from redis import asyncio as aioredis # 使用 redis-py 的异步客户端
import time

from app.core.config.settings import settings
from app.core.utils.json_utils import safe_serialize, safe_deserialize # 需要实现 json_utils

# 定义泛型类型变量
T = TypeVar('T')

class RedisService:
    """
    提供 Redis 操作的异步服务类。
    """
    _pool: aioredis.Redis = None

    @classmethod
    async def initialize(cls):
        """初始化 Redis 连接池"""
        if cls._pool is None:
            try:
                print("正在初始化 Redis 连接池...")
                print(f"Redis 连接字符串: {settings.REDIS_URL}")
                print("Redis 连接池初始化中...")
                print(settings.REDIS_URL)
                cls._pool = aioredis.from_url(
                    "redis://localhost:6379/0",
                    password=123456,
                    encoding="utf-8",
                    decode_responses=True # 自动将 bytes 解码为 str
                )
                await cls._pool.ping() # 测试连接
                print("Redis 连接池初始化成功。")
            except Exception as e:
                print(f"Redis 连接失败: {e}")
                # 根据需要决定是否抛出异常或允许应用在无 Redis 的情况下启动（降级模式）
                # raise ConnectionError(f"无法连接到 Redis: {e}") from e
                cls._pool = None # 标记为未初始化

    @classmethod
    async def close(cls):
        """关闭 Redis 连接池"""
        if cls._pool:
            await cls._pool.close()
            print("Redis 连接池已关闭。")
            cls._pool = None

    def _get_client(self) -> aioredis.Redis:
        """获取 Redis 客户端实例"""
        if self._pool is None:
            raise ConnectionError("Redis 服务未初始化或连接失败。")
        return self._pool

    async def get_async(self, key: str) -> Optional[T]:
        """
        异步从 Redis 获取指定 key 的值，并反序列化为指定类型 T。

        Args:
            key: Redis 键。

        Returns:
            反序列化后的对象，如果 key 不存在或反序列化失败则返回 None。
        """
        try:
            client = self._get_client()
            value_str = await client.get(key)
            if value_str:
                # 假设 safe_deserialize 可以处理 JSON 反序列化
                return safe_deserialize(value_str) # 使用安全的 JSON 反序列化
            return None
        except Exception as e:
            print(f"从 Redis 获取 key '{key}' 时出错: {e}") # 使用 logger 记录错误
            return None

    async def set_async(self, key: str, value: T, expiry_seconds: Optional[int] = None) -> bool:
        """
        异步将对象序列化后存入 Redis。

        Args:
            key: Redis 键。
            value: 要存储的对象。
            expiry_seconds: 过期时间（秒），如果为 None 则永不过期。

        Returns:
            操作是否成功。
        """
        try:
            client = self._get_client()
            # 假设 safe_serialize 可以将任意对象转为 JSON 字符串
            value_str = safe_serialize(value) # 使用安全的 JSON 序列化
            if expiry_seconds is not None and expiry_seconds > 0:
                return await client.setex(key, expiry_seconds, value_str)
            else:
                return await client.set(key, value_str)
        except Exception as e:
            print(f"向 Redis 设置 key '{key}' 时出错: {e}") # 使用 logger 记录错误
            return False

    async def set_string_increment_async(self, key: str, value: int = 1, expiry_seconds: Optional[int] = None) -> Optional[int]:
        """
        异步对 Redis 中的字符串执行增量操作 (原子性)。
        如果 key 不存在，会先设置为 0 再执行增量。

        Args:
            key: Redis 键。
            value: 要增加的值 (默认为 1)。
            expiry_seconds: 过期时间（秒）。如果设置，会在增量操作后设置过期时间。

        Returns:
            增量操作后的值，如果操作失败则返回 None。
        """
        try:
            client = self._get_client()
            # 使用 INCRBY 原子地增加值
            new_value = await client.incrby(key, value)
            if expiry_seconds is not None and expiry_seconds > 0:
                # 只有在成功增量后才设置过期时间
                await client.expire(key, expiry_seconds)
            return new_value
        except Exception as e:
            print(f"对 Redis key '{key}' 执行增量操作时出错: {e}") # 使用 logger 记录错误
            return None

    async def key_exists_async(self, key: str) -> bool:
        """
        异步检查指定的 key 是否存在于 Redis 中。

        Args:
            key: Redis 键。

        Returns:
            如果 key 存在返回 True，否则返回 False。
        """
        try:
            client = self._get_client()
            return await client.exists(key) > 0
        except Exception as e:
            print(f"检查 Redis key '{key}' 是否存在时出错: {e}") # 使用 logger 记录错误
            return False

    async def key_delete_async(self, key: str) -> bool:
        """
        异步删除 Redis 中的指定 key。

        Args:
            key: Redis 键。

        Returns:
            如果成功删除了 key 返回 True，否则返回 False。
        """
        try:
            client = self._get_client()
            # DEL 命令返回成功删除的 key 的数量
            deleted_count = await client.delete(key)
            return deleted_count > 0
        except Exception as e:
            print(f"删除 Redis key '{key}' 时出错: {e}") # 使用 logger 记录错误
            return False

    async def rate_limit_async(self, key_prefix: str, limit: int, period_seconds: int) -> bool:
        """
        使用 Redis Sorted Set 实现简单的滑动窗口速率限制 (异步)。

        Args:
            key_prefix: 用于生成 Redis key 的前缀 (例如 "ratelimit:user:123:path")。
            limit: 时间窗口内的最大允许请求数。
            period_seconds: 时间窗口的长度（秒）。

        Returns:
            如果请求被允许返回 True，如果超出限制返回 False。
        """
        try:
            client = self._get_client()
            now_ns = time.time_ns() # 使用纳秒时间戳以获得更高精度
            cutoff_ns = now_ns - (period_seconds * 1_000_000_000)
            redis_key = f"{key_prefix}:{period_seconds}" # Key 包含时间窗口，方便管理

            # 使用 Lua 脚本保证原子性
            # 脚本逻辑:
            # 1. 移除时间窗口之外的旧记录 (zremrangebyscore)
            # 2. 获取当前窗口内的记录数 (zcard)
            # 3. 如果记录数小于限制:
            #    a. 添加当前时间戳记录 (zadd)
            #    b. 设置/刷新 key 的过期时间 (expire)
            #    c. 返回 1 (允许)
            # 4. 否则返回 0 (拒绝)
            lua_script = """
            local key = KEYS[1]
            local cutoff = ARGV[1]
            local limit = tonumber(ARGV[2])
            local now = ARGV[3]
            local period = tonumber(ARGV[4])

            -- 移除过期成员
            redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)

            -- 获取当前数量
            local current_count = redis.call('ZCARD', key)

            if current_count < limit then
                -- 添加当前请求记录，分数和成员都使用纳秒时间戳
                redis.call('ZADD', key, now, now)
                -- 设置过期时间，比时间窗口稍长一点，确保旧 key 能自动清理
                redis.call('EXPIRE', key, period + 5)
                return 1
            else
                return 0
            end
            """
            # 参数: key, cutoff_score, limit, current_timestamp, period_seconds
            args = [cutoff_ns, limit, now_ns, period_seconds]
            result = await client.eval(lua_script, 1, redis_key, *args)

            return result == 1

        except Exception as e:
            print(f"执行速率限制检查 key '{key_prefix}' 时出错: {e}") # 使用 logger 记录错误
            # 在 Redis 出错时，选择放行还是拒绝？这里选择放行，避免 Redis 问题导致服务完全不可用
            return True