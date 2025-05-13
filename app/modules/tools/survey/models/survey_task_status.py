from enum import Enum

class SurveyTaskStatus(int, Enum):
    """问卷任务状态枚举"""
    DRAFT = 0       # 草稿
    PUBLISHED = 1   # 已发布
    CLOSED = 2      # 已关闭

    @staticmethod
    def get_status_name(status: int) -> str:
        """
        获取状态名称
        
        Args:
            status: 状态值
            
        Returns:
            状态名称
        """
        status_map = {
            SurveyTaskStatus.DRAFT: "草稿",
            SurveyTaskStatus.PUBLISHED: "已发布",
            SurveyTaskStatus.CLOSED: "已关闭"
        }
        return status_map.get(status, "未知状态")
