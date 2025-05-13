# app/core/storage/azure_blob_storage.py
import io
import logging
from typing import Union
from azure.storage.blob.aio import BlobServiceClient, BlobClient, ContainerClient # 使用异步客户端
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError

from app.core.config.settings import settings
from app.core.storage.base import IStorageService
from app.core.exceptions import BusinessException

logger = logging.getLogger(__name__)

class AzureBlobStorageService(IStorageService):
    """使用 Azure Blob Storage 的存储服务实现"""

    def __init__(self):
        self.connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
        self.container_name = settings.AZURE_STORAGE_CONTAINER_NAME
        self.cdn_domain = settings.AZURE_STORAGE_CDN_DOMAIN

        if not self.connection_string:
            raise ValueError("Azure Storage 连接字符串 (AZURE_STORAGE_CONNECTION_STRING) 未配置。")
        if not self.container_name:
            raise ValueError("Azure Storage 容器名称 (AZURE_STORAGE_CONTAINER_NAME) 未配置。")

        try:
            # 创建异步 BlobServiceClient
            # from_connection_string 会处理连接字符串的解析
            self.blob_service_client: BlobServiceClient = BlobServiceClient.from_connection_string(
                self.connection_string
            )
            logger.info("Azure Blob Service Client 已初始化。")
            # 注意：我们不在 init 中创建 ContainerClient，因为它是异步操作
            # self._container_client: Optional[ContainerClient] = None # 推迟初始化
        except Exception as e:
            logger.error(f"初始化 Azure Blob Service Client 失败: {e}", exc_info=True)
            raise RuntimeError(f"初始化 Azure Blob Service Client 失败: {e}") from e

    async def _get_container_client(self) -> ContainerClient:
        """获取并可能创建容器客户端 (异步)"""
        # 如果需要缓存 client 实例，可以在这里添加逻辑
        # if self._container_client is None:
        #     client = self.blob_service_client.get_container_client(self.container_name)
        #     try:
        #         # 尝试创建容器，如果它不存在的话
        #         # public_access='blob' 允许匿名读取 Blob
        #         await client.create_container(public_access='blob')
        #         logger.info(f"Azure Blob 容器 '{self.container_name}' 已创建或已存在。")
        #     except HttpResponseError as e:
        #         # 如果错误是容器已存在 (Conflict)，则忽略
        #         if e.status_code == 409:
        #             logger.info(f"Azure Blob 容器 '{self.container_name}' 已存在。")
        #         else:
        #             logger.error(f"创建 Azure Blob 容器 '{self.container_name}' 失败: {e}", exc_info=True)
        #             raise BusinessException(f"无法访问存储容器: {e.message}", code=500) from e
        #     except Exception as e:
        #         logger.error(f"处理 Azure Blob 容器 '{self.container_name}' 时出错: {e}", exc_info=True)
        #         raise BusinessException(f"无法访问存储容器: {str(e)}", code=500) from e
        #     self._container_client = client
        # return self._container_client

        # 简单版本：每次获取都创建 client 实例，让 SDK 处理缓存（如果有）
        # 并且不在每次获取时都尝试创建容器，假设容器已存在或由其他流程创建
        return self.blob_service_client.get_container_client(self.container_name)


    async def upload_async(
        self,
        file_stream: Union[io.BytesIO, io.BufferedReader, bytes],
        file_key: str,
        content_type: str
    ) -> str:
        """异步上传文件到 Azure Blob Storage"""
        container_client = await self._get_container_client()
        # Blob 名称通常就是 file_key
        blob_client: BlobClient = container_client.get_blob_client(file_key)

        logger.info(f"准备上传文件到 Azure Blob: container='{self.container_name}', blob='{file_key}', content_type='{content_type}'")

        try:
             # 确保流指针在开始位置
            if hasattr(file_stream, 'seek') and hasattr(file_stream, 'readable') and file_stream.readable() and file_stream.seekable():
                file_stream.seek(0)

            # 使用异步 upload_blob 方法
            # overwrite=True 表示如果 Blob 已存在则覆盖
            # content_settings 用于设置 ContentType 等 HTTP Headers
            await blob_client.upload_blob(
                file_stream,
                overwrite=True,
                content_settings={'content_type': content_type}
                # 可以添加其他设置，如 metadata
                # metadata={'uploaded_by': 'my_app'}
            )
            logger.info(f"文件成功上传到 Azure Blob: {blob_client.url}")
            # 返回可访问 URL
            return self.get_url(file_key)

        except HttpResponseError as e:
            logger.error(f"上传文件到 Azure Blob 时发生 HTTP 错误: status={e.status_code}, message={e.message}", exc_info=True)
            raise BusinessException(f"上传文件到云存储失败: {e.message}", code=e.status_code) from e
        except Exception as e:
            logger.error(f"上传文件到 Azure Blob 时发生未知错误: {e}", exc_info=True)
            raise BusinessException(f"上传文件失败: {str(e)}", code=500) from e


    def get_url(self, file_key: str) -> str:
        """获取 Azure Blob 文件的访问 URL"""
        if self.cdn_domain:
            # 使用 CDN 域名
            clean_cdn_domain = self.cdn_domain.replace("https://", "").replace("http://", "").rstrip('/')
            # Azure CDN URL 通常是 https://<endpoint-name>.azureedge.net/<container-name>/<blob-name>
            # 但如果 CDN 配置了源路径，可能不需要 container_name
            # 假设 CDN 直接映射到 blob 根路径
            return f"https://{clean_cdn_domain}/{file_key.lstrip('/')}"
        else:
            # 返回 Blob 的直接 URL
            # 需要 BlobServiceClient 来构造 URL，或者直接从 BlobClient 获取
            # 这里简单地手动构造（可能不完全准确，取决于存储账户设置）
            # account_name = self.blob_service_client.account_name
            # return f"https://{account_name}.blob.core.windows.net/{self.container_name}/{file_key.lstrip('/')}"
            # 更可靠的方式是从 BlobClient 获取
            container_client = self.blob_service_client.get_container_client(self.container_name)
            blob_client = container_client.get_blob_client(file_key)
            return blob_client.url


    async def delete_async(self, file_key: str) -> bool:
        """异步删除 Azure Blob Storage 上的文件"""
        container_client = await self._get_container_client()
        blob_client: BlobClient = container_client.get_blob_client(file_key)

        logger.info(f"准备从 Azure Blob 删除文件: container='{self.container_name}', blob='{file_key}'")
        try:
            # 使用异步 delete_blob
            # delete_snapshots="include" 表示同时删除快照 (如果需要)
            await blob_client.delete_blob(delete_snapshots="include")
            logger.info(f"成功从 Azure Blob 删除文件: {file_key}")
            return True
        except ResourceNotFoundError:
            logger.warning(f"尝试从 Azure Blob 删除文件，但文件不存在: {file_key}")
            return True # 文件不存在，视为删除成功
        except HttpResponseError as e:
            logger.error(f"从 Azure Blob 删除文件时发生 HTTP 错误: status={e.status_code}, message={e.message}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"从 Azure Blob 删除文件时发生未知错误: {e}", exc_info=True)
            return False