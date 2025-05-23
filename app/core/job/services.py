# app/core/job/services.py
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, delete, insert, func # 导入 func
from sqlalchemy.ext.asyncio import AsyncSession
import datetime
import json

from app.core.job.models import JobPersist, JobPersistLog, JobConfig, JobStatus, JobLogLevel, JobPersistHistory
from app.core.utils.snowflake import generate_id

logger = logging.getLogger(__name__)

class JobPersistenceService:
    """
    封装对任务持久化相关表的操作。
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job(
        self,
        task_type: str,
        params_id: Optional[int] = None,
        params_data: Optional[Dict[str, Any]] = None,
        scheduled_at: Optional[datetime.datetime] = None,
        max_retries: Optional[int] = None
    ) -> int:
        """
        创建一个新的持久化任务记录。
        """
        logger.debug(f"请求创建任务: Type={task_type}, ParamsId={params_id}, ParamsData={params_data}")

        job_config = await self._get_job_config(task_type)
        if job_config is None:
             logger.warning(f"任务类型 '{task_type}' 未在 pb_job_config 中找到，将使用默认重试次数 3。")
             final_max_retries = max_retries if max_retries is not None else 3
        else:
             final_max_retries = max_retries if max_retries is not None else job_config.default_max_retries

        now = datetime.datetime.now()
        job = JobPersist(
            task_type=task_type,
            params_id=params_id,
            params_data=json.dumps(params_data) if params_data else None,
            status=int(JobStatus.PENDING), # 使用枚举成员的整数值
            retry_count=0,
            max_retries=final_max_retries,
            scheduled_at=scheduled_at,
            create_date = now,
            last_modify_date = now,
        )

        try:
            self.db.add(job)
            await self.db.flush()
            await self.db.commit()
            logger.info(f"任务已创建: JobId={job.id}, Type={task_type}, ParamsId={params_id}")
            # 确保返回的是整数 ID
            return int(job.id) if job.id is not None else 0 # 添加 ID 非空检查
        except Exception as e:
            await self.db.rollback()
            logger.error(f"创建任务失败: Type={task_type} - {e}")
            raise

    async def acquire_job_lock(self, job_id: int) -> bool:
        """
        尝试获取任务锁 (将状态从 PENDING 更新为 PROCESSING)。
        """
        logger.debug(f"尝试获取任务锁: JobId={job_id}")
        now = datetime.datetime.now()
        
        stmt = (
            update(JobPersist)
            .where(JobPersist.id == job_id)
            .where(JobPersist.status ==int(JobStatus.PENDING)) # 使用枚举成员比较
            .values(
                status=JobStatus.PROCESSING.value, # 使用枚举成员赋值
                started_at=now,
                last_modify_date=now # 手动更新时间戳 (或者依赖 onupdate)
            )
        )
        try:
            result = await self.db.execute(stmt)
            if result.rowcount == 1:
                # 注意：日志记录的 job_id 仍然是整数 ID
                await self._log_job_event(job_id, JobLogLevel.INFO, "任务开始执行 (已获取锁)")
                await self.db.commit()
                logger.info(f"成功获取任务锁: JobId={job_id}")
                return True
            else:
                await self.db.rollback()
                logger.warning(f"获取任务锁失败 (任务不存在或状态不符): JobId={job_id}")
                return False
        except Exception as e:
            await self.db.rollback()
            logger.error(f"获取任务锁时数据库出错: JobId={job_id} - {e}")
            return False

    async def complete_job(self, job_id: int, message: str = "任务成功完成"):
        """
        标记任务为成功完成。
        """
        logger.debug(f"标记任务完成: JobId={job_id}")
        await self._update_job_status(job_id, JobStatus.COMPLETED, message, JobLogLevel.INFO)

    async def fail_job(self, job_id: int, error_message: str, can_retry: bool = True):
        """
        标记任务为失败，并根据重试次数决定最终状态或增加重试计数。
        """
        logger.debug(f"标记任务失败: JobId={job_id}, CanRetry={can_retry}")
        # 使用 get 获取对象，需要主键
        job = await self.db.get(JobPersist, job_id)
        if not job:
             logger.error(f"尝试标记失败状态，但任务不存在: JobId={job_id}")
             return

        should_retry = False
        if can_retry and job.retry_count < job.max_retries:
            should_retry = True
            new_status = JobStatus.PENDING
            new_retry_count = job.retry_count + 1
            retry_delay_seconds = 60 * (new_retry_count)
            new_scheduled_at = datetime.datetime.now() + datetime.timedelta(seconds=retry_delay_seconds)
            log_message = f"任务失败，将在 {retry_delay_seconds} 秒后重试 ({new_retry_count}/{job.max_retries})。错误: {error_message}"
            log_level = JobLogLevel.WARNING
        else:
            new_status = JobStatus.FAILED
            new_retry_count = job.retry_count
            new_scheduled_at = job.scheduled_at # 失败时不改变计划时间
            log_message = f"任务最终失败 (重试 {job.retry_count}/{job.max_retries})。错误: {error_message}"
            log_level = JobLogLevel.ERROR

        await self._update_job_status(
            job_id=job_id,
            status=new_status,
            message=error_message, # last_error
            log_level=log_level,
            log_message_override=log_message,
            retry_count_override=new_retry_count,
            scheduled_at_override=new_scheduled_at if should_retry else job.completed_at # 如果失败，完成时间是现在；如果重试，由下次执行设置
        )

    async def _update_job_status(
        self,
        job_id: int,
        status: JobStatus,
        message: Optional[str],
        log_level: JobLogLevel,
        log_message_override: Optional[str] = None,
        retry_count_override: Optional[int] = None,
        scheduled_at_override: Optional[datetime.datetime] = None
    ):
        """内部方法：更新任务状态并记录日志"""
        now = datetime.datetime.now()
        
        values_to_update: Dict[str, Any] = {
            "status": int(status), # 使用枚举成员的整数值
            "last_modify_date": now # 更新时间戳
        }
        if status == JobStatus.COMPLETED or status == JobStatus.FAILED:
            values_to_update["completed_at"] = now
        if message is not None:
            values_to_update["last_error"] = message
        if retry_count_override is not None:
            values_to_update["retry_count"] = retry_count_override
        if scheduled_at_override is not None:
            values_to_update["scheduled_at"] = scheduled_at_override
        # 当状态变回 PENDING 时，清除开始时间和完成时间
        if status == JobStatus.PENDING:
            values_to_update["started_at"] = None
            values_to_update["completed_at"] = None
            # scheduled_at 应该由 fail_job 设置，这里不再处理


        stmt = update(JobPersist).where(JobPersist.id == job_id).values(**values_to_update)
        try:
            await self.db.execute(stmt)
            log_msg = log_message_override if log_message_override else (message or f"状态更新为 {status.name}")
            await self._log_job_event(job_id, log_level, log_msg)
            await self.db.commit()
            logger.info(f"任务状态更新成功: JobId={job_id}, NewStatus={status.name}")
        except Exception as e:
            await self.db.rollback()
            logger.error(f"更新任务状态或记录日志失败: JobId={job_id} - {e}")

    async def _log_job_event(self, job_id: int, level: JobLogLevel, message: str):
        """记录任务日志到 pb_job_persist_log 表"""
        now = datetime.datetime.now()
        log_entry = JobPersistLog(
            job_id=job_id,
            level=level.value,
            message=message,
            timestamp = now,
        )
        self.db.add(log_entry)
        # 日志提交与状态更新在同一事务中

    async def find_pending_jobs(self, limit: int = 10) -> List[JobPersist]:
        """查找待处理的任务 (供调度器使用)"""
        now = datetime.datetime.now()
        stmt = (
            select(JobPersist)
            .where(JobPersist.status ==int(JobStatus.PENDING))
            .where( (JobPersist.scheduled_at == None) | (JobPersist.scheduled_at <= now) )
            .order_by(JobPersist.create_date.asc()) # 使用 create_date
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_job_config(self, task_type: str) -> Optional[JobConfig]:
        """获取任务配置 (供调度器使用)"""
        return await self._get_job_config(task_type)

    async def _get_job_config(self, task_type: str) -> Optional[JobConfig]:
         """内部方法获取任务配置"""
         stmt = select(JobConfig).where(JobConfig.task_type == task_type)
         result = await self.db.execute(stmt)
         return result.scalar_one_or_none()


    async def migrate_finished_jobs(self, older_than: datetime.datetime, batch_size: int = 500) -> int:
        """
        将指定时间之前已完成或失败的任务迁移到历史表，并从原表删除。

        Args:
            older_than: 只迁移在此时间之前完成或失败的任务。
            batch_size: 每次迁移处理的记录数。

        Returns:
            成功迁移的记录数。
        """
        logger.info(f"开始迁移 {older_than} 之前的已完成/失败任务...")
        migrated_count = 0
        try:
            # 1. 查找要迁移的任务 (分批处理)
            job_ids_stmt = (
                select(JobPersist.id)
                .where(
                    (JobPersist.status == JobStatus.COMPLETED) | (JobPersist.status == JobStatus.FAILED)
                )
                .where(JobPersist.last_modify_date < older_than) # 使用 last_modify_date 判断完成/失败时间
                .order_by(JobPersist.last_modify_date.asc()) # 按完成时间顺序迁移
                .limit(batch_size)
            )
            result = await self.db.execute(job_ids_stmt)
            job_ids_to_migrate = list(result.scalars().all())

            if not job_ids_to_migrate:
                logger.info("没有找到需要迁移到历史表的任务。")
                return 0

            logger.info(f"找到 {len(job_ids_to_migrate)} 个任务准备迁移...")

            # 2. 查询这些任务的完整数据
            jobs_to_migrate_stmt = select(JobPersist).where(JobPersist.id.in_(job_ids_to_migrate))
            job_result = await self.db.execute(jobs_to_migrate_stmt)
            jobs_data = list(job_result.scalars().all())

            if not jobs_data: # 双重检查
                 logger.warning("查询到的任务 ID 列表在再次查询时为空，可能已被删除。")
                 return 0

            # 3. 准备插入历史表的数据
            history_data = []
            now = datetime.datetime.now()
            for job in jobs_data:
                history_data.append({
                    "id": job.id, # 使用原 ID
                    "task_type": job.task_type,
                    "params_id": job.params_id,
                    "params_data": job.params_data,
                    "status": job.status,
                    "retry_count": job.retry_count,
                    "max_retries": job.max_retries,
                    "last_error": job.last_error,
                    "scheduled_at": job.scheduled_at,
                    "started_at": job.started_at,
                    "completed_at": job.completed_at,
                    "create_date": job.create_date, # 保留原创建时间
                    "last_modify_date": job.last_modify_date, # 保留原最后更新时间
                    "migrated_at": now # 记录迁移时间
                })

            # 4. 插入到历史表
            if history_data:
                # 使用 SQLAlchemy Core API 的 insert，性能更好
                insert_stmt = insert(JobPersistHistory).values(history_data)
                # 注意：如果存在主键冲突（理论上不应发生），可能需要添加 on_conflict_do_nothing 或 update
                await self.db.execute(insert_stmt)
                logger.info(f"成功将 {len(history_data)} 条记录插入到历史表。")

            # 5. 从原表删除已迁移的记录
            delete_stmt = delete(JobPersist).where(JobPersist.id.in_(job_ids_to_migrate))
            delete_result = await self.db.execute(delete_stmt)
            migrated_count = delete_result.rowcount
            logger.info(f"成功从原表删除 {migrated_count} 条已迁移的任务记录。")

            # 6. 提交事务
            await self.db.commit()
            return migrated_count

        except Exception as e:
            await self.db.rollback()
            logger.error(f"迁移任务到历史表时出错: {e}")
            raise # 重新抛出异常，让调度器知道任务失败

    async def delete_old_history_jobs(self, older_than: datetime.datetime, batch_size: int = 1000) -> int:
        """
        (可选) 删除指定时间之前迁移到历史表的记录及其日志。

        Args:
            older_than: 只删除在此时间之前迁移的记录。
            batch_size: 每次删除处理的记录数。

        Returns:
            成功删除的历史任务记录数。
        """
        logger.info(f"准备删除 {older_than} 之前迁移的历史任务...")
        deleted_count = 0
        try:
             # 1. 查找要删除的历史任务 ID (基于 MigratedAt)
            job_ids_stmt = select(JobPersistHistory.id).where(
                JobPersistHistory.migrated_at < older_than
            ).limit(batch_size)

            result = await self.db.execute(job_ids_stmt)
            job_ids_to_delete = list(result.scalars().all())

            if not job_ids_to_delete:
                logger.info("没有找到需要删除的旧历史任务。")
                return 0

            logger.info(f"找到 {len(job_ids_to_delete)} 个旧历史任务记录准备删除。")

            # 2. 删除关联的日志 (如果历史任务也需要保留日志的话，否则跳过这步)
            # delete_logs_stmt = delete(JobPersistLog).where(JobPersistLog.job_id.in_(job_ids_to_delete))
            # log_result = await self.db.execute(delete_logs_stmt)
            # logger.info(f"删除了 {log_result.rowcount} 条关联的历史任务日志。")

            # 3. 删除历史任务本身
            delete_jobs_stmt = delete(JobPersistHistory).where(JobPersistHistory.id.in_(job_ids_to_delete))
            job_result = await self.db.execute(delete_jobs_stmt)
            deleted_count = job_result.rowcount
            logger.info(f"删除了 {deleted_count} 条旧历史任务记录。")

            await self.db.commit()
            return deleted_count
        except Exception as e:
            await self.db.rollback()
            logger.error(f"删除旧历史任务时出错: {e}")
            raise