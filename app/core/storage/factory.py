# app/core/storage/factory.py
import logging
from functools import lru_cache
from typing import Optional, Union, TYPE_CHECKING # 添加 TYPE_CHECKING
from enum import Enum

from app.core.config.settings import settings
from app.core.storage.base import IStorageService
from app.core.storage.base import StorageProviderType # 从 core 导入

logger = logging.getLogger(__name__)


@lru_cache(maxsize=None)
def get_storage_service(provider_type_str: Optional[str] = None) -> Optional[IStorageService]:
    """
    获取指定类型的存储服务实例。
    使用 LRU 缓存来复用服务实例。
    将具体实现类的导入移到函数内部。
    """
    if provider_type_str is None:
        provider_type_str = settings.STORAGE_PROVIDER
        logger.debug(f"未指定存储提供者，使用配置值: {provider_type_str}")

    try:
        # ... (解析 provider_type 的逻辑保持不变) ...
        if provider_type_str.lower() == "none":
             logger.info("存储提供者配置为 'None'，不创建存储服务实例。")
             return None
        provider_type = StorageProviderType(provider_type_str)
    except ValueError:
        #provider_lower = provider_type_str.lower()
        provider_lower = "local"
        print(f"provider_lower: {provider_lower}")
        if provider_lower == "local": provider_type = StorageProviderType.LOCAL
        elif provider_lower == "aliyunoss": provider_type = StorageProviderType.ALIYUN_OSS
        elif provider_lower == "azureblob": provider_type = StorageProviderType.AZURE_BLOB
        elif provider_lower == "none":
             logger.info("存储提供者配置为 'None'，不创建存储服务实例。")
             return None
        else:
            logger.error(f"不支持的存储提供程序: {provider_type_str}")
            raise ValueError(f"不支持的存储提供程序: {provider_type_str}")

    logger.info(f"准备创建 '{provider_type.value}' 存储服务实例...")

    try:
        if provider_type == StorageProviderType.LOCAL:
            # --- 在函数内部导入 ---
            from app.core.storage.local_storage import LocalStorageService
            return LocalStorageService()
        elif provider_type == StorageProviderType.ALIYUN_OSS:
            # --- 在函数内部导入 ---
            from app.core.storage.aliyun_oss_storage import AliyunOssStorageService
            if not all([settings.ALIYUN_OSS_ACCESS_KEY_ID, settings.ALIYUN_OSS_ACCESS_KEY_SECRET, settings.ALIYUN_OSS_ENDPOINT, settings.ALIYUN_OSS_BUCKET_NAME]):
                logger.error("阿里云 OSS 配置不完整，无法创建服务实例。")
                raise ValueError("阿里云 OSS 配置不完整。")
            return AliyunOssStorageService()
        elif provider_type == StorageProviderType.AZURE_BLOB:
            # --- 在函数内部导入 ---
            from app.core.storage.azure_blob_storage import AzureBlobStorageService
            if not settings.AZURE_STORAGE_CONNECTION_STRING or not settings.AZURE_STORAGE_CONTAINER_NAME:
                 logger.error("Azure Blob Storage 配置不完整，无法创建服务实例。")
                 raise ValueError("Azure Blob Storage 配置不完整。")
            return AzureBlobStorageService()
        else:
            # 理论上不会执行
            raise ValueError(f"内部错误：无法处理的存储提供者类型 {provider_type.value}")
    except ImportError as e:
         # 捕获可能的导入错误
         logger.error(f"导入存储服务实现时出错 ({provider_type.value}): {e}")
         raise RuntimeError(f"无法导入存储服务 {provider_type.value}: {e}") from e
    except Exception as e:
         logger.error(f"创建存储服务 '{provider_type.value}' 实例时失败: {e}")
         raise RuntimeError(f"创建存储服务 '{provider_type.value}' 失败: {e}") from e


# --- FastAPI 依赖项 ---
# 为了让类型提示正常工作，我们仍然需要在 TYPE_CHECKING 块中导入
if TYPE_CHECKING:
    from app.core.storage.local_storage import LocalStorageService
    from app.core.storage.aliyun_oss_storage import AliyunOssStorageService
    from app.core.storage.azure_blob_storage import AzureBlobStorageService

def storage_service_dependency() -> Optional[IStorageService]:
    """FastAPI 依赖项，用于注入配置的存储服务实例。"""
    return get_storage_service()