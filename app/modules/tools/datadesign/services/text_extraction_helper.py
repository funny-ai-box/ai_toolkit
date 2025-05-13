import re
import logging

class AIResultTextExtractionHelper:
    """AI返回文本提取辅助类"""

    @staticmethod
    def extract_complete_business_analysis(content: str, logger: logging.Logger) -> str:
        """
        提取完整业务分析内容

        Args:
            content (str): AI生成的内容
            logger (logging.Logger): 日志记录器

        Returns:
            str: 完整业务分析内容，如果提取失败则返回原内容
        """
        try:
            match = re.search(r"===COMPLETE_BUSINESS_ANALYSIS_BEGIN===(.*?)===COMPLETE_BUSINESS_ANALYSIS_END===", content, re.DOTALL)
            if match:
                return match.group(1).strip()
            else:
                logger.warning("没有找到业务分析的格式标记，将使用完整内容")
                return content
        except Exception as e:
            logger.error(f"提取完整业务分析内容时发生错误: {e}")
            return content

    @staticmethod
    def extract_complete_database_design(content: str, logger: logging.Logger) -> str:
        """
        提取完整数据库设计内容

        Args:
            content (str): AI生成的内容
            logger (logging.Logger): 日志记录器

        Returns:
            str: 完整数据库设计内容，如果提取失败则返回原内容
        """
        try:
            match = re.search(r"===COMPLETE_DATABASE_DESIGN_BEGIN===(.*?)===COMPLETE_DATABASE_DESIGN_END===", content, re.DOTALL)
            if match:
                return match.group(1).strip()
            else:
                logger.warning("没有找到数据库设计的格式标记，将使用完整内容")
                return content
        except Exception as e:
            logger.error(f"提取完整数据库设计内容时发生错误: {e}")
            return content