# app/core/logging_config.py
import logging
import sys
import json
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timezone

from app.core.config.settings import settings

# --- 自定义 JSON 日志格式化器 ---
# 输出 JSON 格式的日志，方便机器解析和收集
class JsonFormatter(logging.Formatter):
    # 移除构造函数中的 datefmt 参数，因为我们将手动格式化
    # def __init__(self, *, datefmt=None, ...):
    #     super().__init__(...)

    def format(self, record: logging.LogRecord) -> str:
        # --- 手动格式化时间戳为 ISO 8601 格式 (包含毫秒和时区) ---
        # record.created 是时间戳 (秒)
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc) # 假设 record.created 是 UTC 时间戳
        # 如果需要本地时区，可以使用: dt = datetime.fromtimestamp(record.created).astimezone()
        # 格式化为: YYYY-MM-DDTHH:MM:SS.ffffff+HH:MM
        # .isoformat() 默认包含微秒，我们需要手动添加时区 Z 表示 UTC
        # timestamp_str = dt.isoformat(timespec='milliseconds') + 'Z'
        # 或者，如果想使用本地时区偏移：
        timestamp_str = dt.astimezone().isoformat(timespec='milliseconds') # 转换为本地时区并格式化

        log_entry = {
            "timestamp": timestamp_str, # <--- 使用手动格式化的时间戳
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "environment": settings.ENVIRONMENT,
            "pathname": record.pathname,
            "lineno": record.lineno,
            "funcName": record.funcName,
            "exception": self.formatException(record.exc_info) if record.exc_info else None,
            **(record.__dict__.get("extra_data", {})),
        }
        log_entry = {k: v for k, v in log_entry.items() if v is not None}
        return json.dumps(log_entry, ensure_ascii=False)

# --- 日志配置函数 ---
def setup_logging():
    """配置应用程序的日志记录"""
    log_level_str = settings.LOG_LEVEL.upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # --- 创建格式化器 ---
    console_formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)",
        datefmt="%Y-%m-%d %H:%M:%S" # 控制台格式可以简单点
    )
    # 文件格式化器 (JSON) - 不再需要 datefmt
    json_formatter = JsonFormatter() # <--- 不再传递 datefmt

    # --- 创建处理器 ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(log_level)

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        filename=log_dir / "app.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding='utf-8',
        delay=True
    )
    file_handler.setFormatter(json_formatter) # <--- 设置 JsonFormatter
    file_handler.setLevel(log_level)

    # --- 配置根 Logger ---
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # --- 清理和添加处理器 ---
    # 检查并避免重复添加处理器
    handler_types = {type(h) for h in root_logger.handlers}
    if console_handler.__class__ not in handler_types:
        root_logger.addHandler(console_handler)
    if file_handler.__class__ not in handler_types:
        root_logger.addHandler(file_handler)

    # --- 配置特定库的日志级别 (保持不变) ---
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO if settings.DATABASE_ECHO else logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)
    logging.getLogger("oss2").setLevel(logging.WARNING)
    logging.getLogger("azure.core.pipeline.policies").setLevel(logging.WARNING)
    logging.getLogger("azure.storage.blob").setLevel(logging.WARNING)
    logging.getLogger("pymilvus").setLevel(logging.INFO)

    logger = logging.getLogger(__name__) # 获取 logger 用于此模块内部日志
    logger.info(f"日志系统配置完成。根日志级别: {log_level_str}")
    logger.info(f"控制台日志级别: {logging.getLevelName(console_handler.level)}")
    logger.info(f"文件日志级别: {logging.getLevelName(file_handler.level)}, 文件路径: {file_handler.baseFilename}")

# 在模块加载时获取一个 logger 实例，用于配置过程中的日志输出
# logger = logging.getLogger(__name__) # 这行可以移到 setup_logging 内部或之后