# app/core/storage/aliyun_oss_storage.py
import oss2 # 阿里云 OSS SDK
import io
import logging
from typing import Union

from app.core.config.settings import settings
from app.core.storage.base import IStorageService
from app.core.exceptions import BusinessException

logger = logging.getLogger(__name__)

class AliyunOssStorageService(IStorageService):
    """使用阿里云 OSS 的存储服务实现"""

    def __init__(self):
        self.access_key_id = settings.ALIYUN_OSS_ACCESS_KEY_ID
        self.access_key_secret = settings.ALIYUN_OSS_ACCESS_KEY_SECRET
        self.endpoint = settings.ALIYUN_OSS_ENDPOINT
        self.bucket_name = settings.ALIYUN_OSS_BUCKET_NAME
        self.cdn_domain = settings.ALIYUN_OSS_CDN_DOMAIN
        self.url_expiration = settings.ALIYUN_OSS_URL_EXPIRATION

        # 检查配置完整性
        if not all([self.access_key_id, self.access_key_secret, self.endpoint, self.bucket_name]):
            raise ValueError("阿里云 OSS 配置不完整 (需要 ACCESS_KEY_ID, ACCESS_KEY_SECRET, ENDPOINT, BUCKET_NAME)。")

        try:
            # 初始化 OSS Auth 和 Bucket 对象
            self.auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            # Bucket 对象是非线程安全的，但在无状态服务中每次请求创建一个新的通常没问题
            # 如果需要考虑性能，可以研究 Auth 或 Service 的复用
            self.bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name)
            logger.info(f"阿里云 OSS 服务已初始化。Endpoint: {self.endpoint}, Bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"初始化阿里云 OSS 服务失败: {e}")
            raise RuntimeError(f"初始化阿里云 OSS 服务失败: {e}") from e

    async def upload_async(
        self,
        file_stream: Union[io.BytesIO, io.BufferedReader, bytes],
        file_key: str,
        content_type: str
    ) -> str:
        """异步上传文件到阿里云 OSS"""
        # oss2 SDK 的 put_object 是同步阻塞的
        # 为了在异步环境中使用，需要使用 asyncio.to_thread
        # 或者直接调用同步方法，如果上传时间不长且不阻塞关键路径

        # 准备 Headers
        headers = {'Content-Type': content_type}
        # 可以添加其他 Header，例如 Cache-Control, Content-Disposition 等
        # headers['Cache-Control'] = 'max-age=3600' # 缓存1小时
        # headers['Content-Disposition'] = f'inline; filename="{os.path.basename(file_key)}"'

        # 确保 file_key 不以 '/' 开头
        clean_file_key = file_key.lstrip('/')

        logger.info(f"准备上传文件到 OSS: bucket='{self.bucket_name}', key='{clean_file_key}', content_type='{content_type}'")

        try:
            # --- 使用同步方法 (简单，适用于非 CPU 密集型 IO) ---
            # 确保流指针在开始位置
            if hasattr(file_stream, 'seek') and hasattr(file_stream, 'readable') and file_stream.readable() and file_stream.seekable():
                file_stream.seek(0)

            # put_object 支持直接传入 bytes 或 file-like object
            result = self.bucket.put_object(clean_file_key, file_stream, headers=headers)

            if result.status == 200:
                logger.info(f"文件成功上传到 OSS: etag='{result.etag}', key='{clean_file_key}'")
                return self.get_url(clean_file_key)
            else:
                logger.error(f"上传文件到 OSS 失败: status={result.status}, request_id={result.request_id}")
                # 尝试读取错误响应体 (如果存在)
                error_body = result.resp.read().decode('utf-8') if hasattr(result, 'resp') else "N/A"
                logger.error(f"OSS 错误响应: {error_body}")
                raise BusinessException(f"上传文件到云存储失败 (HTTP Status: {result.status})", code=500)

            # --- 使用 asyncio.to_thread (如果需要避免阻塞事件循环) ---
            # async def upload_sync():
            #     if hasattr(file_stream, 'seek') and file_stream.seekable():
            #         file_stream.seek(0)
            #     return self.bucket.put_object(clean_file_key, file_stream, headers=headers)
            #
            # result = await asyncio.to_thread(upload_sync)
            # ... (后续处理同上) ...

        except oss2.exceptions.OssError as e:
            logger.error(f"上传文件到 OSS 时发生错误: status={e.status}, code={e.code}, message={e.message}, request_id={e.request_id}")
            raise BusinessException(f"上传文件到云存储失败: {e.message}", code=e.status) from e
        except Exception as e:
            logger.error(f"上传文件到 OSS 时发生未知错误: {e}")
            raise BusinessException(f"上传文件失败: {str(e)}", code=500) from e

    def get_url(self, file_key: str) -> str:
        """获取 OSS 文件的访问 URL"""
        clean_file_key = file_key.lstrip('/')
        if self.cdn_domain:
            # 使用 CDN 域名
            # 确保 CDN 域名不包含协议头和尾部斜杠
            clean_cdn_domain = self.cdn_domain.replace("https://", "").replace("http://", "").rstrip('/')
            return f"https://{clean_cdn_domain}/{clean_file_key}"
        else:
            # 生成带签名的临时访问 URL
            try:
                # expires 参数是秒
                signed_url = self.bucket.sign_url('GET', clean_file_key, self.url_expiration)
                return signed_url
            except Exception as e:
                logger.error(f"生成 OSS 文件签名 URL 失败 for key '{clean_file_key}': {e}")
                # 返回一个无签名的 URL 作为备用，但这可能无法访问私有 Bucket
                # 需要确认 Bucket 的读写权限设置
                endpoint_no_proto = self.endpoint.replace("https://", "").replace("http://", "")
                return f"https://{self.bucket_name}.{endpoint_no_proto}/{clean_file_key}"


    async def delete_async(self, file_key: str) -> bool:
        """异步删除 OSS 上的文件"""
        # delete_object 也是同步的，如果需要异步包装，使用 asyncio.to_thread
        clean_file_key = file_key.lstrip('/')
        logger.info(f"准备从 OSS 删除文件: bucket='{self.bucket_name}', key='{clean_file_key}'")
        try:
            # --- 使用同步方法 ---
            result = self.bucket.delete_object(clean_file_key)
            if result.status == 204: # 删除成功返回 204 No Content
                 logger.info(f"成功从 OSS 删除文件: key='{clean_file_key}'")
                 return True
            else:
                 logger.warning(f"从 OSS 删除文件可能未成功: status={result.status}, request_id={result.request_id}")
                 # 根据状态码决定是否算成功，2xx 都算成功？
                 return 200 <= result.status < 300

            # --- 使用 asyncio.to_thread ---
            # async def delete_sync():
            #     return self.bucket.delete_object(clean_file_key)
            # result = await asyncio.to_thread(delete_sync)
            # ... (后续处理同上) ...

        except oss2.exceptions.NoSuchKey:
            logger.warning(f"尝试从 OSS 删除文件，但文件不存在: key='{clean_file_key}'")
            return True # 文件不存在，视为删除成功
        except oss2.exceptions.OssError as e:
            logger.error(f"从 OSS 删除文件时发生错误: status={e.status}, code={e.code}, message={e.message}, request_id={e.request_id}")
            return False
        except Exception as e:
            logger.error(f"从 OSS 删除文件时发生未知错误: {e}")
            return False