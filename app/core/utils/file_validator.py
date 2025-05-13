# app/core/utils/file_validator.py
import logging
from typing import List, Tuple
from fastapi import UploadFile
from pathlib import Path

logger = logging.getLogger(__name__)

def validate_document_file(file: UploadFile, allowed_extensions: List[str], max_size_mb: int = 10) -> Tuple[bool, str]:
    """
    验证上传的文档文件是否有效。

    Args:
        file: FastAPI 的 UploadFile 对象。
        allowed_extensions: 允许的文件扩展名列表 (例如 [".pdf", ".docx"])。
                              会自动转为小写。
        max_size_mb: 允许的最大文件大小 (MB)。
    Returns:
        一个元组 (is_valid, error_message)。
        如果有效，is_valid=True, error_message=""。
        如果无效，is_valid=False, error_message=错误信息。
    """
    if not file or file.size is None:
        return False, "文件不能为空"

    # 1. 检查文件大小
    if file.size == 0:
         return False, "文件不能为空"
    max_size_bytes = max_size_mb * 1024 * 1024
    if file.size > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        logger.warning(f"文件大小超限: {file.filename}, size={file.size} bytes, max={max_mb}MB")
        return False, f"文件大小不能超过 {max_mb}MB"

    # 2. 检查文件名和扩展名
    if not file.filename:
        return False, "缺少文件名"
    file_extension = Path(file.filename).suffix.lower()
    if not file_extension:
         # 尝试从 content_type 推断 (不太可靠)
         # content_type = file.content_type
         # ... 推断逻辑 ...
         logger.warning(f"文件缺少扩展名: {file.filename}")
         # 可以选择允许或拒绝无扩展名文件
         # return False, "文件缺少扩展名"
         pass # 暂时允许无扩展名？或者根据 content_type 判断
    t_allowed_extensions = [ext.lower() for ext in allowed_extensions]
    if file_extension not in t_allowed_extensions:
        logger.warning(f"不支持的文件扩展名: {file.filename}, ext='{file_extension}'")
        allowed_str = ", ".join(t_allowed_extensions)
        return False, f"不支持的文件格式。请上传以下格式的文件: {allowed_str}"

    # 3. 其他检查 (可选)
    # 例如，检查文件名是否包含非法字符等

    logger.debug(f"文件验证通过: {file.filename}")
    return True, ""