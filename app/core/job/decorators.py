# app/core/job/decorators.py
import logging
from functools import wraps
from typing import Callable, Coroutine, Any, Optional
from fastapi import Depends, HTTPException, status

# 导入依赖的服务和模型
# from app.core.job.services import JobPersistenceService # 不需要直接导入服务类了
# from app.api.dependencies import get_job_persistence_service # 装饰器不再需要它
from app.core.dtos import ApiResponse
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.job.services import JobPersistenceService # 仅用于类型提示

logger = logging.getLogger(__name__)

TaskLogicFunction = Callable[..., Coroutine[Any, Any, None]]

def job_endpoint(default_can_retry: bool = True):
    """
    装饰器，用于封装处理持久化任务的 API 端点逻辑 (同步执行版本)。
    被装饰函数 *必须* 注入 JobPersistenceService。
    """
    def decorator(api_endpoint_func: Callable):
        @wraps(api_endpoint_func)
        async def wrapper(
            # wrapper 签名包含路径参数和通过 **kwargs 传递的依赖
            job_id: int,
            params_id: int, # 通用参数名
            # 不再包含 job_service = Depends(...)
            *args,
            **kwargs # 捕获所有注入到原始函数的依赖，*包括* job_service
        ):
            logger.info(f"任务端点收到同步执行请求: JobId={job_id}, ParamsId={params_id}")

            # --- 从 kwargs 中获取 JobPersistenceService 实例 ---
            # 被装饰的函数必须注入 job_service
            job_service: Optional['JobPersistenceService'] = kwargs.get('job_service')
            if job_service is None: # 严格检查 None
                # 尝试查找类型匹配的 (以防 key 不完全是 'job_service')
                for val in kwargs.values():
                     # 需要导入 JobPersistenceService 来进行 isinstance 检查
                     # 这又可能导致循环导入...
                     # 更好的方式是约定被装饰函数必须注入名为 'job_service' 的依赖
                     from app.core.job.services import JobPersistenceService # 仅用于检查
                     if isinstance(val, JobPersistenceService):
                          job_service = val
                          break

            if job_service is None: # 再次检查
                logger.error(f"Job Endpoint 装饰器错误：未能从依赖中获取 JobPersistenceService 实例 (JobId={job_id})。请确保 API 端点注入了名为 'job_service' 的依赖: job_service: JobPersistenceService = Depends(...)。")
                return ApiResponse.fail(message="任务执行依赖配置错误", code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            # --- 类型检查 (可选) ---
            from app.core.job.services import JobPersistenceService
            if not isinstance(job_service, JobPersistenceService):
                 logger.error(f"Job Endpoint 装饰器错误：获取到的 'job_service' 类型不正确 (Type: {type(job_service)})。")
                 return ApiResponse.fail(message="任务执行依赖类型错误", code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            # ------------------------

            # 1. 尝试获取锁 (现在 job_service 是实例)
            lock_acquired = await job_service.acquire_job_lock(job_id)

            if not lock_acquired:
                logger.warning(f"获取任务锁失败或任务已被处理: JobId={job_id}")
                return ApiResponse.fail(message="任务已被处理或状态不符", code=status.HTTP_409_CONFLICT)

            # 2. 直接执行业务逻辑并处理结果
            try:
                logger.debug(f"开始同步执行任务逻辑: JobId={job_id}")
                # --- 调用原始 API 端点函数 ---
                specific_params = {"job_id": job_id}
                if 'id' in api_endpoint_func.__annotations__:
                    specific_params['id'] = params_id
                else: specific_params['params_id'] = params_id

                # 从 kwargs 移除 job_service，避免传递给不需要它的原始函数
                # (如果原始函数也需要 job_service，则不移除)
                other_dependencies = {k: v for k, v in kwargs.items() if k != 'job_service'}

                await api_endpoint_func(
                    **specific_params,
                    # --- 传递过滤后的依赖 ---
                    **other_dependencies
                )
                # ---------------------------

                # 3. 成功，标记完成
                success_message = f"任务 {job_id} 成功完成"
                await job_service.complete_job(job_id, success_message)
                logger.info(f"同步任务成功完成: JobId={job_id}")
                return ApiResponse.success(message=success_message)

            except Exception as e:
                # 4. 失败，标记失败
                error_message = f"执行任务 {job_id} 时出错: {str(e)}"
                logger.error(f"同步任务失败: JobId={job_id} - {error_message}")
                await job_service.fail_job(job_id, error_message, can_retry=default_can_retry)
                return ApiResponse.fail(message=error_message, code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return wrapper
    return decorator