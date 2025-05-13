# app/base/repositories/user_repository.py
import datetime
from typing import Optional
from sqlalchemy import select, update, exists, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User
from app.core.utils.snowflake import generate_id # 导入雪花 ID 生成函数

class UserRepository:
    """
    用户数据仓库类，负责与用户相关的数据库操作。
    """
    def __init__(self, db: AsyncSession):
        """
        初始化仓库。

        Args:
            db: SQLAlchemy 的异步数据库会话。
        """
        self.db = db

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """
        根据用户 ID 获取用户实体。

        Args:
            user_id: 用户 ID。

        Returns:
            用户实体对象，如果未找到则返回 None。
        """
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() # 返回单个对象或 None

    async def get_by_mobile_no(self, mobile_no: str) -> Optional[User]:
        """
        根据手机号获取用户实体。

        Args:
            mobile_no: 手机号。

        Returns:
            用户实体对象，如果未找到则返回 None。
        """
        # 确保查询时比较的是正确的列名 'MobileNo'
        stmt = select(User).where(User.mobile_no == mobile_no)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def exists_mobile_no(self, mobile_no: str) -> bool:
        """
        检查指定手机号是否已存在。

        Args:
            mobile_no: 手机号。

        Returns:
            如果存在返回 True，否则返回 False。
        """
        # 使用 exists() 子查询更高效
        stmt = select(exists().where(User.mobile_no == mobile_no))
        result = await self.db.execute(stmt)
        return result.scalar() or False # scalar() 返回 True/False 或 None

    async def create(self, user: User) -> bool:
        """
        创建新用户。自动生成雪花 ID 并设置创建/修改时间。

        Args:
            user: 待创建的用户实体对象 (ID 和时间字段会被覆盖)。

        Returns:
            如果创建成功返回 True，否则返回 False (虽然 add 通常不直接报错，commit 时才报)。
        """
        try:
            # 生成雪花 ID
            user.id = generate_id()
            # C# 代码在仓库层设置时间，这里也保持一致
            # (虽然模型定义了 server_default，但显式设置可以确保时间准确性)
            now = datetime.datetime.now() # 或者使用数据库的 func.now() - 取决于需求
            user.create_date = now
            user.last_modify_date = now

            self.db.add(user) # 添加到会话
            await self.db.flush() # 将更改刷新到数据库，以便获取可能的错误或 ID (虽然这里是手动生成)
            # 注意：commit 操作应该在服务层完成，以控制事务边界
            # await self.db.commit()
            return True
        except Exception as e:
            # 实际错误通常在 commit 时抛出，这里 flush 失败的可能性较小
            # 但以防万一，进行捕获和记录
            print(f"创建用户时出错 (flush阶段): {e}") # 使用 logger
            # await self.db.rollback() # 回滚应该在服务层处理
            return False

    async def update(self, user: User) -> bool:
        """
        更新用户信息。自动更新 last_modify_date。

        Args:
            user: 包含更新后信息的用户实体对象。

        Returns:
            如果更新成功返回 True，否则返回 False。
        """
        # 检查用户是否在当前会话中 (如果是通过 ID 查出来的，就在)
        # 如果不是，需要先从数据库获取或合并
        if user not in self.db:
            # 尝试合并游离对象到会话中
            # 如果 ID 相同但对象不同，merge 会用传入对象的值更新数据库记录
             try:
                 # 注意：merge 在 2.0 中不直接返回实例，需要在之后重新查询或依赖现有实例
                 await self.db.merge(user)
             except Exception as e:
                  print(f"合并用户对象失败: {e}") # logger
                  return False
        else:
             # 如果对象已在会话中，SQLAlchemy 会自动跟踪更改
             pass

        # 显式更新修改时间 (即使模型有 onupdate，显式设置更明确)
        # 注意：模型中的 onupdate=func.now() 会在 SQL层面生效
        # 如果业务逻辑需要在 Python 代码中确定时间点，则在此处设置
        # user.last_modify_date = datetime.datetime.now()

        try:
            await self.db.flush() # 刷新更改
            # await self.db.commit() # 提交应在服务层
            return True
        except Exception as e:
            print(f"更新用户时出错 (flush阶段): {e}") # 使用 logger
            # await self.db.rollback() # 回滚应在服务层
            return False

    # C# 中的 Updateable(user).ExecuteCommandAsync() 类似于以下方式：
    # (但通常我们直接修改附加到 session 的对象实例)
    async def update_partial(self, user_id: int, data: dict) -> bool:
        """
        部分更新用户信息 (示例，如果需要)。
        Args:
            user_id: 用户 ID。
            data: 包含要更新字段的字典。
        Returns:
            是否成功。
        """
        try:
            # 确保包含 last_modify_date 的更新
            # data['last_modify_date'] = datetime.datetime.now() # 或者使用 func.now()
            data['LastModifyDate'] = func.now() # 使用数据库函数确保时间一致性

            stmt = update(User).where(User.id == user_id).values(**data)
            result = await self.db.execute(stmt)
            # await self.db.commit() # 提交应在服务层
            # rowcount 在某些 DBAPI 驱动下可能不可靠，但通常 > 0 表示有更新
            return result.rowcount > 0
        except Exception as e:
            print(f"部分更新用户 (ID: {user_id}) 时出错: {e}") # 使用 logger
            # await self.db.rollback() # 回滚应在服务层
            return False