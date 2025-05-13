# app/modules/base/knowledge/services/graph_service.py
import logging
from typing import Tuple, List, Dict, Any # 添加 Dict, Any
import json # 导入 json

from app.core.config.settings import settings
from app.core.ai.chat.base import IChatAIService
from app.core.ai.dtos import InputMessage, ChatRoleType
from app.modules.base.prompts.services import PromptTemplateService # 导入 Service
from app.core.utils.json_utils import safe_deserialize, safe_serialize
from app.core.exceptions import BusinessException, NotFoundException

logger = logging.getLogger(__name__)

class KnowledgeGraphService:
    """知识图谱服务，负责调用 AI 生成图谱信息"""
    def __init__(
        self,
        prompt_service: PromptTemplateService, # 注入 Prompt Service
        ai_service: IChatAIService,
        # logger: logging.Logger, # 可以注入 logger
    ):
        self.prompt_service = prompt_service
        self.ai_service = ai_service
        self.logger = logger # 使用全局 logger 或注入的 logger

    async def generate_knowledge_graph_async(self, content: str) -> Tuple[str, str, str]:
        """
        调用 AI 模型生成内容的摘要、关键词和思维导图。

        Args:
            content: 需要处理的文档内容。

        Returns:
            一个元组，包含 (摘要文本, 关键词 JSON 字符串, 思维导图 JSON 字符串)。

        Raises:
            BusinessException: 如果 AI 调用或结果解析失败。
            NotFoundException: 如果找不到所需的提示词模板。
        """
        if not content:
            self.logger.warning("尝试为内容为空的文档生成知识图谱。")
            return "", "[]", "{}"

        try:
            # 获取提示词模板内容
            try:
                system_prompt = await self.prompt_service.get_content_by_key_async("PKB_GRAPH_GENERATE_PROMPT")
            except NotFoundException:
                 self.logger.error("未找到知识图谱生成所需的提示词模板: PKB_GRAPH_GENERATE_PROMPT")
                 raise BusinessException("知识图谱服务配置不完整 (缺少提示词)")

            # 构建发送给 AI 的消息
            messages = [
                InputMessage.from_text(ChatRoleType.SYSTEM, system_prompt),
                InputMessage.from_text(ChatRoleType.USER, f"请根据以下文档内容生成摘要、关键词和思维导图:\n\n---\n{content}\n---"),
            ]
            self.logger.info(f"准备调用 AI 生成知识图谱，内容长度: {len(content)}")

            # 调用 AI 服务
            ai_result_text = await self.ai_service.chat_completion_async(messages)
            self.logger.debug(f"AI 返回的知识图谱原始结果: {ai_result_text[:500]}...") # 记录部分原始结果

            # 解析 AI 返回的 JSON 结果
            summary = ""
            keywords_list: List[str] = []
            mind_map_dict: Dict[str, Any] = {}

            try:
                # 假设 AI 返回的是一个包含 summary, keywords, mindMap 键的 JSON 对象字符串
                result_obj = safe_deserialize(ai_result_text)
                if isinstance(result_obj, dict):
                    summary = result_obj.get("summary", "").strip()
                    # 确保 keywords 是列表
                    raw_keywords = result_obj.get("keywords")
                    if isinstance(raw_keywords, list):
                         keywords_list = [str(kw).strip() for kw in raw_keywords if str(kw).strip()]
                    elif isinstance(raw_keywords, str): # 如果 AI 返回逗号分隔的字符串
                         keywords_list = [kw.strip() for kw in raw_keywords.split(',') if kw.strip()]

                    # 确保 mind_map 是字典
                    raw_mind_map = result_obj.get("mindMap")
                    if isinstance(raw_mind_map, dict):
                        mind_map_dict = raw_mind_map
                    else:
                         self.logger.warning("AI 返回的 mindMap 不是有效的字典结构。")

                else:
                     self.logger.error(f"AI 返回的知识图谱结果不是有效的 JSON 对象: {ai_result_text[:200]}...")
                     summary = "[AI结果格式错误]"

            except Exception as parse_ex:
                self.logger.error(f"解析 AI 返回的知识图谱 JSON 失败: {parse_ex}. Raw result: {ai_result_text[:200]}...", exc_info=True)
                summary = "[AI结果解析失败]"

            # 将 keywords 和 mindMap 序列化回 JSON 字符串用于存储
            keywords_json = safe_serialize(keywords_list)
            mind_map_json = safe_serialize(mind_map_dict)

            self.logger.info(f"知识图谱生成成功。摘要长度: {len(summary)}, 关键词数量: {len(keywords_list)}")
            return summary, keywords_json, mind_map_json

        except BusinessException as be: # 捕获并重新抛出已知的业务异常
             self.logger.error(f"生成知识图谱时发生业务异常: {be.message}")
             raise
        except Exception as ex:
            self.logger.error(f"生成知识图谱时发生未知错误: {ex}", exc_info=True)
            raise BusinessException("生成知识图谱时发生内部错误") from ex