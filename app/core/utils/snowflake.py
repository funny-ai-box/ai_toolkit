# app/core/utils/snowflake.py
import time
import threading
import logging
from app.core.snowflake import options, generator
# 配置日志
logger = logging.getLogger(__name__)

# --- 全局实例 ---
# 从配置中获取 Worker ID 和 Datacenter ID
from app.core.config.settings import settings

try:
    # 创建一个全局的 Snowflake ID 生成器实例
    options = options.IdGeneratorOptions(worker_id=settings.SNOWFLAKE_WORKER_ID, worker_id_bit_length=2, seq_bit_length=6)
    _id_generator = generator.DefaultIdGenerator()
    _id_generator.set_id_generator(options)
except ValueError as e:
    logger.error(f"初始化 Snowflake ID 生成器失败: {e}. 请检查 .env 文件中的 SNOWFLAKE_WORKER_ID 和 SNOWFLAKE_DATACENTER_ID 配置。")
    # 可以选择在这里抛出异常或设置 _id_generator 为 None，并在使用时检查
    _id_generator = None
except Exception as e:
     logger.error(f"初始化 Snowflake ID 生成器时发生未知错误: {e}")
     _id_generator = None

def generate_id() -> int:
    """全局函数，用于获取下一个 Snowflake ID"""
    if _id_generator is None:
        raise RuntimeError("Snowflake ID 生成器未成功初始化。请检查配置和日志。")
    return _id_generator.next_id()