# app/core/storage/base.py
from typing import Protocol, runtime_checkable, Union # 确保导入 Union
from abc import abstractmethod
import io # 确保导入 io
from enum import Enum

# 定义支持的存储提供者类型枚举
class StorageProviderType(str, Enum):
    LOCAL = "Local"
    ALIYUN_OSS = "AliyunOSS"
    AZURE_BLOB = "AzureBlob"
    NONE = "None"

@runtime_checkable # 允许运行时检查一个类是否实现了这个协议
class IStorageService(Protocol):
    """
    对象存储服务的接口协议。

    定义了所有存储服务实现（如本地存储、阿里云 OSS、Azure Blob）
    必须提供的方法签名。
    """

    @abstractmethod # 标记为抽象方法，实现类必须覆盖它
    async def upload_async(
        self,
        file_stream: Union[io.BytesIO, io.BufferedReader, bytes], # 接受多种流类型或字节对象
        file_key: str,
        content_type: str
    ) -> str:
        """
        异步上传文件到存储服务。

        Args:
            file_stream: 包含文件内容的字节流或字节对象。
                         注意：如果传入的是流对象，调用者应确保流在使用后被正确关闭。
                         实现者应注意流可能需要被重置（seek(0)）如果之前被读取过。
            file_key: 文件在存储服务中的唯一标识符 (通常是相对路径 + 文件名)。
                      实现类应处理路径分隔符和潜在的安全问题（如路径遍历）。
            content_type: 文件的 MIME 类型 (例如 'image/jpeg', 'application/pdf')。

        Returns:
            上传成功后文件的可访问 URL。

        Raises:
            BusinessException: 如果上传过程中发生可预见的业务错误（如配置错误、权限问题）。
            Exception: 如果发生其他意外错误。
        """
        ... # Protocol 中的抽象方法体就是 ...

    @abstractmethod
    def get_url(self, file_key: str) -> str:
        """
        获取已上传文件的可访问 URL。

        这个方法通常是同步的，因为它主要是基于配置（如基础 URL、CDN 域名）
        和文件 key 来构造 URL 字符串，不涉及实际的 I/O 操作。

        Args:
            file_key: 文件在存储服务中的唯一标识符。实现类应处理 key 的规范化。

        Returns:
            文件的可访问 URL。如果无法生成有效 URL（例如配置缺失），
            可以返回一个占位符、相对路径或根据约定抛出异常。
        """
        ...

    @abstractmethod
    async def delete_async(self, file_key: str) -> bool:
        """
        异步从存储服务删除文件。

        Args:
            file_key: 文件在存储服务中的唯一标识符。实现类应处理 key 的规范化和安全。

        Returns:
            布尔值，指示删除操作是否成功。
            对于某些服务，即使文件原本不存在，删除操作也可能返回成功。
            具体的成功定义取决于实现类的逻辑。

        Raises:
            BusinessException: 如果删除过程中发生可预见的业务错误。
            Exception: 如果发生其他意外错误。
        """
        ...