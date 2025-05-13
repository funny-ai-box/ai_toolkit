"""
文件服务实现
"""
import os
import logging
from typing import Tuple, Optional
from fastapi import UploadFile

from app.core.storage.base import IStorageService, StorageProviderType
from app.core.config.settings import settings

logger = logging.getLogger(__name__)

class FileService:
    """文件服务实现类"""
    
    def __init__(self, storage_service: IStorageService):
        """
        初始化文件服务
        
        Args:
            storage_service: 存储服务
        """
        self.storage_service = storage_service
        
        # 从配置中获取文件根路径
        self.root_path = settings.get_or_default("VideoMixer.StoragePath", "uploads/videomixer")
        
        # 确保根目录存在
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path, exist_ok=True)
    
    async def upload_file_async(self, file: UploadFile, directory: str) -> str:
        """
        上传文件
        
        Args:
            file: 上传的文件
            directory: 存储目录
            
        Returns:
            本地文件路径
        """
        try:
            logger.info(f"开始上传文件: {file.filename}, 大小: {file.size} 字节")
            
            # 确保目录存在
            full_dir_path = os.path.join(self.root_path, directory)
            if not os.path.exists(full_dir_path):
                os.makedirs(full_dir_path, exist_ok=True)
            
            # 生成唯一文件名
            import uuid
            file_extension = os.path.splitext(file.filename)[1] if file.filename else ""
            file_name = f"{uuid.uuid4()}{file_extension}"
            file_path = os.path.join(full_dir_path, file_name)
            
            # 保存文件
            with open(file_path, "wb") as f:
                # 每次读取8KB
                chunk_size = 8192
                content = await file.read(chunk_size)
                while content:
                    f.write(content)
                    content = await file.read(chunk_size)
            
            # 重置文件指针位置
            await file.seek(0)
            
            logger.info(f"文件上传成功: {file_path}")
            return file_path.replace("\\", "/")
        
        except Exception as e:
            logger.error(f"文件上传失败: {str(e)}", exc_info=True)
            raise
    
    async def upload_stream_async(self, file_stream, file_name: str, directory: str) -> str:
        """
        上传文件流
        
        Args:
            file_stream: 文件流
            file_name: 文件名
            directory: 存储目录
            
        Returns:
            本地文件路径
        """
        try:
            logger.info(f"开始上传文件流: {file_name}")
            
            # 确保目录存在
            full_dir_path = os.path.join(self.root_path, directory)
            if not os.path.exists(full_dir_path):
                os.makedirs(full_dir_path, exist_ok=True)
            
            # 生成唯一文件名
            import uuid
            file_extension = os.path.splitext(file_name)[1]
            new_file_name = f"{uuid.uuid4()}{file_extension}"
            file_path = os.path.join(full_dir_path, new_file_name)
            
            # 保存文件
            with open(file_path, "wb") as f:
                f.write(await file_stream.read())
            
            logger.info(f"文件流上传成功: {file_path}")
            return file_path.replace("\\", "/")
        
        except Exception as e:
            logger.error(f"文件流上传失败: {str(e)}", exc_info=True)
            raise
    
    async def upload_to_cdn_async(self, file_path: str, object_key: str) -> str:
        """
        上传到CDN
        
        Args:
            file_path: 本地文件路径
            object_key: 对象键
            
        Returns:
            CDN URL
        """
        try:
            logger.info(f"开始上传文件到CDN: {file_path}, 对象键: {object_key}")
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"要上传的文件不存在: {file_path}")
            
            # 获取文件的MIME类型
            content_type = self._get_content_type(file_path)
            
            # 读取文件内容
            with open(file_path, "rb") as f:
                file_content = f.read()
            
            # 上传到存储服务
            from io import BytesIO
            file_stream = BytesIO(file_content)
            
            cdn_url = await self.storage_service.upload_async(file_stream, object_key, content_type)
            
            logger.info(f"文件上传到CDN成功: {cdn_url}")
            return cdn_url
        
        except Exception as e:
            logger.error(f"上传文件到CDN失败: {str(e)}", exc_info=True)
            raise
    
    def _get_content_type(self, file_path: str) -> str:
        """
        获取文件的MIME类型
        
        Args:
            file_path: 文件路径
            
        Returns:
            MIME类型
        """
        extension = os.path.splitext(file_path)[1].lower()
        return {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".avi": "video/x-msvideo",
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".txt": "text/plain",
            ".json": "application/json",
        }.get(extension, "application/octet-stream")


class FileValidationService:
    """文件验证服务"""
    
    def __init__(self):
        """初始化文件验证服务"""
        # 从配置中获取支持的文件格式和大小限制
        self.supported_video_formats = settings.get_or_default(
            "VideoMixer.SupportedVideoFormats", 
            [".mp4", ".mov", ".avi", ".mkv", ".wmv"]
        )
        
        self.supported_audio_formats = settings.get_or_default(
            "VideoMixer.SupportedAudioFormats", 
            [".mp3", ".wav", ".m4a", ".aac"]
        )
        
        self.max_video_size = settings.get_or_default("VideoMixer.MaxVideoSize", 2147483648)  # 默认2GB
    
    def validate_video_file(self, file: UploadFile) -> Tuple[bool, str]:
        """
        验证视频文件
        
        Args:
            file: 上传的文件
            
        Returns:
            验证结果元组 (是否有效, 错误信息)
        """
        try:
            # 检查文件是否为空
            if file is None or file.size == 0:
                return False, "未提供视频文件或文件为空"
            
            # 检查文件大小
            if file.size > self.max_video_size:
                return False, f"视频文件大小超过限制，最大允许{self.max_video_size // (1024 * 1024)}MB"
            
            # 检查文件扩展名
            if file.filename:
                file_extension = os.path.splitext(file.filename)[1].lower()
                if not file_extension or file_extension not in self.supported_video_formats:
                    supported_formats = ", ".join(self.supported_video_formats)
                    return False, f"不支持的视频文件格式，支持的格式有：{supported_formats}"
            else:
                return False, "文件名无效"
            
            return True, ""
        
        except Exception as e:
            logger.error(f"验证视频文件时发生错误: {str(e)}", exc_info=True)
            return False, "验证文件时发生错误"
    
    def validate_audio_file(self, file: UploadFile) -> Tuple[bool, str]:
        """
        验证音频文件
        
        Args:
            file: 上传的文件
            
        Returns:
            验证结果元组 (是否有效, 错误信息)
        """
        try:
            # 检查文件是否为空
            if file is None or file.size == 0:
                return False, "未提供音频文件或文件为空"
            
            # 检查文件扩展名
            if file.filename:
                file_extension = os.path.splitext(file.filename)[1].lower()
                if not file_extension or file_extension not in self.supported_audio_formats:
                    supported_formats = ", ".join(self.supported_audio_formats)
                    return False, f"不支持的音频文件格式，支持的格式有：{supported_formats}"
            else:
                return False, "文件名无效"
            
            return True, ""
        
        except Exception as e:
            logger.error(f"验证音频文件时发生错误: {str(e)}", exc_info=True)
            return False, "验证文件时发生错误"