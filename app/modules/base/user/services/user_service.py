# app/base/services/user_service.py
import random
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from ..dtos import (
    UserRegisterDto, UserLoginDto, UserInfoDto, LoginResultDto,
    SendVerifiCodeDto, VerifiCodeSceneType, UserUpdatePwdDto
)
from ..models import User
from ..repositories.user_repository import UserRepository
from app.core.auth.password_service import PasswordService
from app.core.auth.jwt_service import JwtService
from app.core.redis.service import RedisService
from app.core.exceptions import BusinessException, NotFoundException
from app.core.config.settings import Settings

import logging # 导入 logging
logger = logging.getLogger(__name__)

class UserService:
    """
    用户服务类，处理用户相关的业务逻辑。
    """
    def __init__(
        self,
        db: AsyncSession,
        user_repository: UserRepository,
        jwt_service: JwtService,
        redis_service: RedisService,
        settings: Settings # 注入配置
    ):
        self.db = db
        self.user_repository = user_repository
        self.jwt_service = jwt_service
        self.redis_service = redis_service
        self.settings = settings

    async def send_verifi_code(self, request_dto: SendVerifiCodeDto) -> bool:
        """
        通用场景发送验证码。

        Args:
            request_dto: 发送验证码请求 DTO。

        Returns:
            发送是否成功 (这里仅模拟，实际应调用短信网关)。

        Raises:
            BusinessException: 如果发送过于频繁。
        """
        cache_key = f"{request_dto.scene_type.value}:{request_dto.scene_key}"
        limit_key = f"Limit:{cache_key}"

        # 检查发送频率限制
        limit_count_str = await self.redis_service.get_async(limit_key)
        limit_count = int(limit_count_str) if limit_count_str else 0

        if limit_count > 5: # 一天不能超过 5 次
            raise BusinessException("验证码发送过于频繁，请稍后再试")

        # 增加频率计数 (原子操作)
        # 使用 INCR 并设置过期时间 (24 小时)
        await self.redis_service.set_string_increment_async(limit_key, 1, expiry_seconds=24 * 60 * 60)

        # 生成随机四位验证码
        verifi_code = f"{random.randint(0, 9)}{random.randint(0, 9)}{random.randint(0, 9)}{random.randint(0, 9)}"
        logger.debug(f"为场景 {cache_key} 生成的验证码: {verifi_code}") # 模拟发送，打印到控制台

        # --- 实际应用中应在此处调用短信网关接口 ---
        # sms_sent = await call_sms_gateway(request_dto.scene_key, verifi_code)
        # if not sms_sent:
        #     # 可以考虑回滚频率计数或进行补偿逻辑
        #     # await self.redis_service.set_string_increment_async(limit_key, -1) # 可能需要更复杂的逻辑
        #     logger.warning(f"调用短信网关失败: {cache_key}")
        #     return False
        # ------------------------------------------

        # 将验证码存入 Redis，5 分钟有效
        # C# 使用了 SetAsync<string>，这里也直接存字符串
        await self.redis_service.set_async(cache_key, verifi_code, expiry_seconds=5 * 60)

        return True

    async def register_async(self, register_dto: UserRegisterDto) -> UserInfoDto:
        """
        处理用户注册。

        Args:
            register_dto: 用户注册信息 DTO。

        Returns:
            注册成功后的用户信息 DTO。

        Raises:
            BusinessException: 如果手机号已存在、验证码不正确或创建失败。
        """
        # 检查手机号是否存在
        if await self.user_repository.exists_mobile_no(register_dto.mobile_no):
            raise BusinessException("该手机号已注册")

        # 验证验证码
        cache_key = f"{VerifiCodeSceneType.REGISTER.value}:{register_dto.mobile_no}"
        cached_code = await self.redis_service.get_async(cache_key) # get_async 返回 Optional[T]

        # if cached_code is None or register_dto.verifi_code != cached_code:
        #     raise BusinessException("验证码不正确或已过期")

        # 创建用户实体
        new_user = User(
            mobile_no=register_dto.mobile_no,
            name=register_dto.name,
            password=PasswordService.hash_password(register_dto.password) # 哈希密码
            # ID 和时间戳在 repository.create 中处理
        )

        # 保存用户 (事务处理)
        try:
            success = await self.user_repository.create(new_user)
            if not success:
                 # create 内部的 flush 可能失败，虽然概率小
                 raise BusinessException("注册失败 (存储错误)")

            await self.db.commit() # 提交事务

            # 注册成功后删除验证码
            await self.redis_service.key_delete_async(cache_key)

            # --- 调用 异步 任务发送欢迎邮件 ---


        except Exception as e:
            await self.db.rollback() # 发生任何异常都要回滚
            logger.error(f"注册过程中数据库操作失败: {e}") # logger
            # 可以根据异常类型判断是数据库约束错误还是其他错误
            # 例如，如果 commit 时报 unique constraint violation (理论上前面已检查)
            raise BusinessException(f"注册失败: {e}") from e

        # 返回用户信息
        # new_user 对象在 commit 后可能过期（如果 session expire_on_commit=True）
        # 但我们设置了 False，或者可以直接从 new_user.id 重新查询
        # 这里直接使用创建时填充好的 new_user 对象转换为 DTO
        # return new_user.to_user_info_dto() # 使用模型内的方法转换
        # 或者手动转换:
        return UserInfoDto(
            id=new_user.id,
            mobileNo=new_user.mobile_no, # DTO 使用别名
            name=new_user.name,
            createDate=new_user.create_date # DTO 使用别名
        )


    async def login_async(self, login_dto: UserLoginDto) -> LoginResultDto:
        """
        处理用户登录。

        Args:
            login_dto: 用户登录信息 DTO。

        Returns:
            登录成功后的结果，包含用户信息和令牌。

        Raises:
            NotFoundException: 如果用户不存在。
            BusinessException: 如果密码错误。
        """
        # 根据手机号查找用户
        user = await self.user_repository.get_by_mobile_no(login_dto.mobile_no)
        if user is None:
            raise NotFoundException(resource_type="用户", resource_id=login_dto.mobile_no)

        # 验证密码
        if not user.password or not PasswordService.verify_password(login_dto.password, user.password):
            raise BusinessException("用户名或密码错误") # 避免提示过于具体

        # 生成 JWT 令牌
        # 注意：C# 的 GenerateTokenAsync 同时会写入 Redis，Python 实现也应如此
        token, expire_time = await self.jwt_service.generate_token(user.id, user.mobile_no or "")

        # 计算 expire_in (秒)
        # C# 直接读取配置，这里我们用实际生成的 expire_time 计算
        expires_in = int((expire_time - datetime.now(timezone.utc)).total_seconds())
        if expires_in < 0 : expires_in = 0 # 避免负数

        # 返回登录结果
        return LoginResultDto(
            userInfo=user.to_user_info_dto(), # 使用模型转换方法
            accessToken=token,
            expiresIn=expires_in
        )

    async def update_pwd(self, user_id: int, request_dto: UserUpdatePwdDto) -> bool:
        """
        修改用户密码。

        Args:
            user_id: 当前登录用户的 ID。
            request_dto: 修改密码请求 DTO。

        Returns:
            如果修改成功返回 True。

        Raises:
            NotFoundException: 如果用户不存在。
            BusinessException: 如果验证码不正确或更新失败。
        """
        # 获取用户
        user = await self.user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundException(resource_type="用户", resource_id=user_id)

        # 验证验证码
        # C# 使用 userID 作为 key，这里保持一致
        cache_key = f"{VerifiCodeSceneType.UPDATE_PWD.value}:{user_id}"
        cached_code = await self.redis_service.get_async(cache_key)

        if cached_code is None or request_dto.verifi_code != cached_code:
            raise BusinessException("验证码不正确或已过期")

        # 更新密码
        user.password = PasswordService.hash_password(request_dto.password)
        # last_modify_date 会由 repository.update 或数据库的 onupdate 自动处理

        # 保存更改 (事务处理)
        try:
            success = await self.user_repository.update(user)
            if not success:
                # update 内部的 flush 可能失败
                raise BusinessException("密码修改失败 (存储错误)")
            await self.db.commit()

            # 修改成功后删除验证码
            await self.redis_service.key_delete_async(cache_key)

            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"修改密码过程中数据库操作失败: {e}") # logger
            raise BusinessException(f"密码修改失败: {e}") from e


    async def get_user_info_async(self, user_id: int) -> UserInfoDto:
        """
        获取指定用户 ID 的信息。

        Args:
            user_id: 用户 ID。

        Returns:
            用户信息 DTO。

        Raises:
            NotFoundException: 如果用户不存在。
        """
        print(f"获取用户信息: {user_id}")
        user = await self.user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundException(resource_type="用户", resource_id=user_id)

        return user.to_user_info_dto()

    async def logout_async(self, user_id: int) -> bool:
        """
        处理用户登出 (使当前令牌失效)。

        Args:
            user_id: 用户 ID。

        Returns:
            操作是否成功。
        """
        # 调用 JWT 服务撤销 Redis 中的令牌
        return await self.jwt_service.revoke_token(user_id)