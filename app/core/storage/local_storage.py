# app/core/storage/local_storage.py
import os
import shutil
import io
import logging
from pathlib import Path

from app.core.config.settings import settings
from app.core.storage.base import IStorageService
from app.core.exceptions import BusinessException

logger = logging.getLogger(__name__)

class LocalStorageService(IStorageService):
    """
    将文件存储在本地文件系统的服务实现。
    """
    def __init__(self):
        self.base_path = Path(settings.LOCAL_STORAGE_PATH)
        self.base_url = settings.LOCAL_STORAGE_BASE_URL

        # 确保基础存储目录存在
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"本地存储目录 '{self.base_path}' 已确保存在。")
        except OSError as e:
            logger.error(f"创建本地存储目录 '{self.base_path}' 失败: {e}", exc_info=True)
            raise RuntimeError(f"无法创建本地存储目录: {e}") from e

        if not self.base_url:
             logger.warning("本地存储的 BASE_URL 未配置，get_url 将返回相对路径或不完整 URL。")


    async def upload_async(
        self,
        file_stream: io.BytesIO | io.BufferedReader | bytes,
        file_key: str,
        content_type: str # content_type 在本地存储中通常不直接使用，但保留接口一致性
    ) -> str:
        """异步上传文件到本地存储"""
        # 构建完整的文件路径，并进行安全检查防止路径遍历
        # 使用 Path.joinpath 避免手动处理斜杠
        # 清理 file_key，移除可能的前导斜杠和 '../'
        safe_file_key = file_key.lstrip('/').lstrip('\\')
        # 简单的路径遍历防护
        if ".." in safe_file_key:
             logger.error(f"检测到潜在的路径遍历尝试: {file_key}")
             raise BusinessException("无效的文件路径", code=400)

        target_path = self.base_path.joinpath(safe_file_key)

        try:
            # 确保目标文件的父目录存在
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # 异步写入文件
            # 使用 aiofiles 库可以实现真正的异步文件 IO，但这里为了简单，
            # 使用同步 IO 包装在 asyncio.to_thread 中（如果性能是瓶颈再考虑 aiofiles）
            # 或者直接使用同步写入，因为本地 IO 通常很快
            logger.info(f"正在上传文件到本地: {target_path}")

            # 将流写入文件
            if isinstance(file_stream, bytes):
                # 如果是字节对象，直接写入
                with open(target_path, "wb") as f:
                    f.write(file_stream)
            elif hasattr(file_stream, 'read'):
                 # 如果是流对象
                 # 确保流指针在开始位置
                 if hasattr(file_stream, 'seek') and file_stream.seekable():
                     file_stream.seek(0)

                 with open(target_path, "wb") as f:
                     shutil.copyfileobj(file_stream, f) # 使用 shutil 高效复制流
                 logger.info(f"文件成功写入: {target_path}")

            else:
                 logger.error(f"不支持的文件流类型: {type(file_stream)}")
                 raise BusinessException("无效的文件流类型", code=400)

            # 返回文件的可访问 URL
            return self.get_url(safe_file_key) # 使用清理过的 key

        except OSError as e:
            logger.error(f"写入本地文件 '{target_path}' 时发生 OS 错误: {e}", exc_info=True)
            raise BusinessException(f"上传文件失败 (IO Error): {e}", code=500) from e
        except Exception as e:
            logger.error(f"上传文件到本地时发生未知错误: {e}", exc_info=True)
            # 尝试删除可能已创建的不完整文件
            if target_path.exists():
                try:
                    target_path.unlink()
                except OSError:
                    logger.warning(f"删除不完整上传文件 '{target_path}' 失败。")
            raise BusinessException(f"上传文件失败: {str(e)}", code=500) from e

    def get_url(self, file_key: str) -> str:
        """获取本地存储文件的 URL"""
        # 确保 file_key 中的路径分隔符是 URL 友好的 '/'
        url_safe_key = file_key.replace('\\', '/')

        if self.base_url:
            # 确保 base_url 和 key 之间只有一个斜杠
            return f"{self.base_url.rstrip('/')}/{url_safe_key.lstrip('/')}"
        else:
            # 如果 base_url 未配置，返回相对路径或文件 URI (可能无法直接访问)
            logger.warning(f"本地存储 base_url 未配置，为 key '{file_key}' 返回相对路径。")
            return f"/{url_safe_key.lstrip('/')}" # 返回一个相对路径

    async def delete_async(self, file_key: str) -> bool:
        """异步删除本地存储的文件"""
        safe_file_key = file_key.lstrip('/').lstrip('\\')
        if ".." in safe_file_key:
            logger.error(f"尝试删除非法路径: {file_key}")
            return False # 防止删除上级目录文件

        target_path = self.base_path.joinpath(safe_file_key)

        try:
            if target_path.is_file():
                # 同样，可以使用 asyncio.to_thread 执行同步删除，或直接同步执行
                target_path.unlink()
                logger.info(f"本地文件已删除: {target_path}")
                return True
            else:
                logger.warning(f"尝试删除的文件不存在或不是文件: {target_path}")
                return False # 文件不存在也算删除“成功”？根据需求定，这里返回 False
        except OSError as e:
            logger.error(f"删除本地文件 '{target_path}' 时发生 OS 错误: {e}", exc_info=True)
            return False # 删除失败
        except Exception as e:
            logger.error(f"删除本地文件时发生未知错误: {e}", exc_info=True)
            return False