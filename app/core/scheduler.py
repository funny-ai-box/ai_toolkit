# app/core/scheduler.py
import logging
import asyncio
import httpx # 用于异步调用 API
from typing import Optional, List, Dict, Any, Union
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.base import JobLookupError
from datetime import datetime, timedelta, timezone

# 导入依赖
from app.core.database.session import AsyncSessionFactory # 需要创建独立的 session
from app.core.job.services import JobPersistenceService
from app.core.job.models import JobPersist, JobConfig, JobStatus, JobLogLevel
from app.core.config.settings import settings
import json # 用于解析 params_data

logger = logging.getLogger(__name__)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
# 全局调度器实例
scheduler = AsyncIOScheduler(timezone="Asia/Shanghai") # 使用配置的时区

# --- 定时任务函数 ---

async def migrate_jobs_to_history_job():
    """定时任务：将完成/失败的任务迁移到历史表"""
    logger.info("APScheduler: 开始执行迁移任务到历史表...")
    session = None
    try:
        async with AsyncSessionFactory() as session: # 创建新 session
            job_service = JobPersistenceService(session)
            # 迁移 7 天前完成/失败的任务
            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
            migrated_count = await job_service.migrate_finished_jobs(older_than=seven_days_ago, batch_size=500)
            logger.info(f"APScheduler: 任务迁移完成，共迁移 {migrated_count} 条记录。")
    except Exception as e:
        logger.error(f"APScheduler: 迁移任务到历史表时出错: {e}", exc_info=True)
    finally:
         if session: await session.close() # 确保关闭

async def cleanup_old_history_job():
    """(可选) 定时任务：清理过旧的历史任务记录"""
    logger.info("APScheduler: 开始执行清理旧历史任务...")
    session = None
    try:
        async with AsyncSessionFactory() as session:
            job_service = JobPersistenceService(session)
            # 清理 90 天前迁移的历史记录
            ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
            deleted_count = await job_service.delete_old_history_jobs(older_than=ninety_days_ago, batch_size=1000)
            logger.info(f"APScheduler: 旧历史任务清理完成，共删除 {deleted_count} 条记录。")
    except Exception as e:
        logger.error(f"APScheduler: 清理旧历史任务时出错: {e}", exc_info=True)
    finally:
         if session: await session.close()


async def dispatch_pending_jobs_job():
    """定时任务：扫描待处理任务并调用 API，处理 API 调用层面的失败和重试"""
    logger.debug("APScheduler: 开始扫描并调度待处理任务...")
    session = None
    job_service: Optional[JobPersistenceService] = None
    pending_jobs: List[JobPersist] = []
    job_configs: Dict[str, JobConfig] = {}

    try:
        # 1. 获取待处理任务和配置 (保持不变)
        async with AsyncSessionFactory() as session:
            job_service = JobPersistenceService(session)
            pending_jobs = await job_service.find_pending_jobs(limit=settings.SCHEDULER_FETCH_LIMIT)
            if not pending_jobs:
                 logger.debug("APScheduler: 没有待处理的任务。")
                 return

            logger.info(f"APScheduler: 发现 {len(pending_jobs)} 个待处理任务，准备调度...")
            task_types = {job.task_type for job in pending_jobs}
            for task_type in task_types:
                 config = await job_service.get_job_config(task_type)
                 if config: job_configs[task_type] = config
                 else: logger.warning(f"APScheduler: 任务类型 '{task_type}' 未找到配置。")
    except Exception as e:
         logger.error(f"APScheduler: 查询待处理任务或配置时出错: {e}", exc_info=True)
         if session: await session.close()
         return
    finally:
        if session: await session.close()

    # 2. 异步调用 API
    if pending_jobs:
        async with httpx.AsyncClient(timeout=settings.SCHEDULER_API_TIMEOUT) as client:
            tasks = []
            valid_jobs = [] # 只包含有配置的任务
            for job in pending_jobs:
                config = job_configs.get(job.task_type)
                if config:
                    tasks.append(call_job_api(client, job, config))
                    valid_jobs.append(job) # 记录对应的 job
                else:
                    logger.warning(f"APScheduler: 跳过任务 JobId={job.id}，类型 '{job.task_type}' 缺少配置。")
                    # 将缺少配置的任务直接标记为失败，不再重试
                    async with AsyncSessionFactory() as fail_session:
                         fail_job_service = JobPersistenceService(fail_session)
                         await fail_job_service.fail_job(job.id, "任务类型配置缺失", can_retry=False)

            if tasks:
                 logger.info(f"APScheduler: 准备并发调用 {len(tasks)} 个任务 API...")
                 # --- 处理 gather 的结果 ---
                 results = await asyncio.gather(*tasks, return_exceptions=True)

                 for i, result in enumerate(results):
                      job = valid_jobs[i] # 获取对应的原始 job 对象

                      if isinstance(result, httpx.Response) and result.status_code < 400:
                           # API 调用成功 (HTTP 2xx 或 3xx)
                           logger.info(f"APScheduler: 成功调用任务 API (JobId={job.id})，状态码: {result.status_code}")
                           # 任务的最终成功/失败由 API 端内部的 complete_job/fail_job 处理
                      else:
                           # --- API 调用失败或返回错误状态码 ---
                           error_message = "API 调用失败: "
                           if isinstance(result, httpx.Response): # API 返回 >= 400
                                error_message += f"HTTP {result.status_code}"
                                try:
                                     error_data = result.json()
                                     error_message += f" - {error_data.get('message', result.text[:100])}"
                                except Exception:
                                     error_message += f" - {result.text[:100]}"
                           elif isinstance(result, Exception): # 网络错误, 超时等
                                error_message += str(result)
                           else: # 未知错误
                                error_message += f"未知返回类型 {type(result)}"

                           logger.error(f"APScheduler: 调用任务 API (JobId={job.id}) 失败: {error_message}")

                           # --- 在调度器端调用 fail_job 来处理重试 ---
                           async with AsyncSessionFactory() as fail_session:
                                fail_job_service = JobPersistenceService(fail_session)
                                # 注意：这里的 can_retry 应该为 True，让 fail_job 根据次数判断
                                await fail_job_service.fail_job(job.id, error_message, can_retry=True)
                           # -------------------------------------------


async def call_job_api(client: httpx.AsyncClient, job: JobPersist, config: JobConfig) -> Union[httpx.Response, Exception]:
    """
    异步调用单个任务的 API。
    成功返回 httpx.Response 对象，失败返回 Exception 对象。
    """
    api_path_template = config.api_path
    http_method = config.http_method.upper()
    full_api_url = "" # 初始化

    try:
        # 构建 API URL
        try:
            # 优先使用 params_id 填充 {id} 或 {params_id}
            # 提供 job_id 用于填充 {job_id}
            api_url = api_path_template.format(
                id=job.params_id,
                params_id=job.params_id,
                job_id=job.id
            )
        except KeyError as e:
            raise ValueError(f"API 路径模板 '{api_path_template}' 缺少占位符: {e}") from e

        # 构建请求体
        request_data = None
        if http_method in ["POST", "PUT", "PATCH"] and job.params_data:
            try: request_data = json.loads(job.params_data)
            except json.JSONDecodeError: logger.warning(f"无法解析 JobId={job.id} 的 ParamsData")

        full_api_url = f"{settings.API_BASE_URL}{api_url}"
        logger.debug(f"调用 API: {http_method} {full_api_url}, JobId={job.id}, Data={request_data}")

        # 发起请求
        response = await client.request(
            method=http_method,
            url=full_api_url,
            json=request_data
            # headers={"X-Internal-Auth": settings.INTERNAL_AUTH_TOKEN} # 如果需要
        )

        # 直接返回响应，让调用者检查状态码
        return response

    except (httpx.TimeoutException, httpx.RequestError, ValueError, Exception) as e:
         # 捕获所有可能的异常，包括 URL 构建错误、请求错误、超时等
         error_type = type(e).__name__
         logger.error(f"调用 API ({http_method} {full_api_url or api_path_template}) 出错 (JobId={job.id}): {error_type} - {e}")
         # 不再向上抛出，而是返回异常对象
         return e


# --- 调度器启动和关闭函数 (添加任务) ---
def start_scheduler():
    try:
        # 任务迁移
        scheduler.add_job(
            migrate_jobs_to_history_job,
            trigger=IntervalTrigger(minutes=settings.JOB_MIGRATION_INTERVAL_MINUTES), # 从 settings 读取
            id="migrate_jobs_job", replace_existing=True, max_instances=1
        )
        # 清理历史 (可选)
        # scheduler.add_job(
        #     cleanup_old_history_job,
        #     trigger=IntervalTrigger(hours=settings.JOB_HISTORY_CLEANUP_INTERVAL_HOURS), # 从 settings 读取
        #     id="cleanup_history_job", replace_existing=True, max_instances=1
        # )
        # 任务调度
        scheduler.add_job(
            dispatch_pending_jobs_job,
            trigger=IntervalTrigger(seconds=settings.SCHEDULER_INTERVAL_SECONDS),
            id="dispatch_jobs_job", replace_existing=True, max_instances=1
        )

        if not scheduler.running: scheduler.start()
        logger.info("APScheduler 已启动，并添加了任务调度和维护作业。")
    except Exception as e:
        logger.error(f"启动 APScheduler 或添加作业时出错: {e}", exc_info=True)


def stop_scheduler():
    """关闭 APScheduler"""
    if scheduler.running:
        try:
            # 等待当前正在运行的任务完成（设置超时）
            scheduler.shutdown(wait=True)
            logger.info("APScheduler 已关闭。")
        except Exception as e:
            logger.error(f"关闭 APScheduler 时出错: {e}", exc_info=True)