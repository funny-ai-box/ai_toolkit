# app/modules/tools/podcast/services/ai_script_service.py
import logging
import json
import re
from typing import List, Optional
import httpx

from app.core.ai.chat.base import IChatAIService, InputMessage
# Import the factory FUNCTION directly
from app.core.ai.chat.factory import get_chat_ai_service
from app.core.ai.dtos import ChatRoleType
from app.core.config.settings import Settings
from app.modules.base.prompts.services import PromptTemplateService
from app.core.exceptions import BusinessException
from app.modules.tools.podcast.dtos import PodcastDetailDto, TtsVoiceDefinitionDto, PodcastScriptRawItemDto
from app.modules.tools.podcast.models import VoiceGenderType

logger = logging.getLogger(__name__)

class AIScriptService:
    """AI播客脚本生成服务"""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient, # HTTP client for the factory function
        prompt_template_service: PromptTemplateService,
    ):
        self.settings = settings
        self.prompt_template_service = prompt_template_service
        
        # Use the imported factory function get_chat_ai_service
        # The provider_type_str is read from podcast-specific settings
        self.ai_service: IChatAIService = get_chat_ai_service(
            provider_type_str=settings.podcast.chat_ai_provider_type,
            shared_http_client=http_client
        )
        if not self.ai_service: # Should not happen if factory raises error on failure
            raise RuntimeError(f"Failed to initialize Chat AI service for provider: {settings.podcast.chat_ai_provider_type}")


    def _contains_ssml_tags(self, text: Optional[str]) -> bool:
         if not text:
             return False
         ssml_tag_pattern = r"<(?:speak|prosody|emphasis|break|mstts:express-as|p|s|say-as|sub|voice)"
         return bool(re.search(ssml_tag_pattern, text, re.IGNORECASE))

    def _remove_ssml_tags(self, ssml_text: Optional[str]) -> str:
         if not ssml_text:
             return ""
         try:
             plain_text = re.sub(r"<[^>]+>", "", ssml_text)
             plain_text = re.sub(r"\s+", " ", plain_text).strip()
             return plain_text
         except Exception as e:
             logger.error(f"移除SSML标记时出错: {e}")
             return re.sub(r"<.*?>", "", ssml_text).strip() # Fallback

    async def generate_script_async(
        self, podcast_dtl: PodcastDetailDto, voices: List[TtsVoiceDefinitionDto]
    ) -> List[PodcastScriptRawItemDto]:
        """生成播客脚本"""
        if not podcast_dtl.content_items:
            raise BusinessException("播客内容为空!")

        source_content_builder = []
        for content_item in podcast_dtl.content_items:
            if content_item.source_content:
                source_content_builder.append(content_item.source_content)
        
        full_source_content = "\n\n".join(source_content_builder)
        if not full_source_content.strip():
            raise BusinessException("播客源内容文本为空!")

        chinese_voices = [v for v in voices if v.locale == "zh-CN"]
        english_voices = [v for v in voices if v.locale in ["en-US", "en-GB"]]

        voice_info_builder = []
        voice_info_builder.append("中文语音：")
        for voice in chinese_voices:
            gender_str = "男声" if voice.gender == VoiceGenderType.MALE else "女声"
            voice_info_builder.append(f"- VoiceSymbol={voice.voice_symbol}：{voice.name}，{gender_str}，{voice.description or ''}")
        
        voice_info_builder.append("\n英文语音：")
        for voice in english_voices:
            gender_str = "男声" if voice.gender == VoiceGenderType.MALE else "女声"
            voice_info_builder.append(f"- VoiceSymbol={voice.voice_symbol}：{voice.name}，{gender_str}，{voice.description or ''}")
        
        available_voices_list = "\n".join(voice_info_builder)

        system_prompt_template = await self.prompt_template_service.get_content_by_key_async("PODCAST_GENERATE_SCRIPT_PROMPT")
        if not system_prompt_template:
            raise BusinessException("未找到播客脚本生成提示词模板 (PODCAST_GENERATE_SCRIPT_PROMPT)")
        
        scene_prompt_builder = [
            "## 播客场景",
            podcast_dtl.scene or "未提供",
            "",
            "## 播客氛围",
            podcast_dtl.atmosphere or "未提供",
            "",
            "## 播客配置",
            "- 主持人数量: 1",
            f"- 嘉宾数量: {podcast_dtl.guest_count}",
            "",
            "## 可用的语音列表如下，请从中为每个角色选择唯一的语音：",
            available_voices_list
        ]
        scene_details_prompt = "\n".join(scene_prompt_builder)

        messages = [
            InputMessage(role=ChatRoleType.SYSTEM, content=system_prompt_template),
            InputMessage(role=ChatRoleType.SYSTEM, content=scene_details_prompt),
            InputMessage(role=ChatRoleType.USER, content=f"以下是我要制作成播客的内容：\n\n{full_source_content}")
        ]

        try:
            script_json_str = await self.ai_service.chat_completion_async(messages)
            logger.info(f"播客 {podcast_dtl.id}，AI生成的脚本原始内容：{script_json_str}")

            json_match = re.search(r"\[\s*\{.*\}\s*\]", script_json_str, re.DOTALL)
            if json_match:
                parsable_json_str = json_match.group(0)
            else:
                 if script_json_str.strip().startswith("[") and script_json_str.strip().endswith("]"):
                      parsable_json_str = script_json_str.strip()
                 else:
                      logger.error(f"AI生成的脚本JSON格式不正确或未找到: {script_json_str}")
                      raise BusinessException("AI生成的脚本JSON格式不正确")

            raw_script_items_data = json.loads(parsable_json_str)
            if not isinstance(raw_script_items_data, list):
                raise BusinessException("AI生成的脚本不是一个列表")
            
            script_items: List[PodcastScriptRawItemDto] = [
                PodcastScriptRawItemDto.model_validate(item) for item in raw_script_items_data
            ]

        except json.JSONDecodeError as e:
            logger.error(f"AI生成的脚本JSON解析失败: {e}. Raw content: {script_json_str}")
            raise BusinessException(f"AI生成的脚本JSON解析失败: {e}")
        except Exception as e:
            logger.error(f"处理AI脚本生成时发生未知错误: {e}. Raw content: {script_json_str}")
            raise BusinessException(f"处理AI脚本时出错: {e}")

        if not script_items:
            raise BusinessException("AI生成的脚本为空")

        processed_script_items = []
        for item_data in script_items:
            ssml_content = item_data.content or ""
            plain_content: str

            if self._contains_ssml_tags(ssml_content):
                plain_content = self._remove_ssml_tags(ssml_content)
            else:
                plain_content = ssml_content

            item_data.no_ssml_content = plain_content
            processed_script_items.append(item_data)
            
        return processed_script_items