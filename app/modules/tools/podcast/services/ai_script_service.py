"""
AI脚本生成服务 - 负责将文本内容转换为播客脚本
"""
import re
import json
import logging
from typing import List, Dict, Any, Optional

from app.core.ai.chat.base import IChatAIService

from app.core.ai.dtos import ChatRoleType
from app.core.utils.json_helper import safe_parse_json
from app.modules.base.prompts.services import PromptTemplateService

from app.core.exceptions import BusinessException
from app.modules.tools.pkb.dtos.chat_message import ChatMessageDto
from app.modules.tools.podcast.dtos import (
    PodcastDetailDto, PodcastScriptRawItemDto, TtsVoiceDefinition
)

logger = logging.getLogger(__name__)


class AIScriptService:
    """AI播客脚本生成服务"""
    
    def __init__(
        self, 
        ai_service: IChatAIService,
        prompt_template_service: PromptTemplateService
    ):
        """
        初始化AI脚本生成服务
        
        Args:
            ai_service: AI聊天服务
            prompt_template_service: 提示词模板服务
        """
        self.ai_service = ai_service
        self.prompt_template_service = prompt_template_service
    
    async def generate_script_async(
        self, podcast_dtl: PodcastDetailDto, voices: List[TtsVoiceDefinition]
    ) -> List[PodcastScriptRawItemDto]:
        """
        生成播客脚本
        
        Args:
            podcast_dtl: 播客内容
            voices: 支持的声音类型
        
        Returns:
            生成的脚本列表
        """
        # 检验播客内容是否为空
        if not podcast_dtl.content_items:
            raise BusinessException("播客内容为空!")
        
        # 文档的内容拼接在一起
        source_content = ""
        for content in podcast_dtl.content_items:
            if content.source_content:
                source_content += content.source_content + "\n\n"
        
        # 划分为中文和英文声音
        chinese_voices = [v for v in voices if v.locale == "zh-CN"]
        english_voices = [v for v in voices if v.locale in ["en-US", "en-GB"]]
        
        # 创建语音列表的文本格式，分组显示
        voice_info = "中文语音：\n"
        for voice in chinese_voices:
            gender_text = "男声" if voice.gender == 1 else "女声"
            voice_info += f"- VoiceSymbol={voice.voice_symbol}：{voice.name}，{gender_text}，{voice.description or ''}\n"
        
        voice_info += "\n英文语音：\n"
        for voice in english_voices:
            gender_text = "男声" if voice.gender == 1 else "女声"
            voice_info += f"- VoiceSymbol={voice.voice_symbol}：{voice.name}，{gender_text}，{voice.description or ''}\n"
        
        # 准备AI提示词
        system_prompt = await self.prompt_template_service.get_content_by_key_async("PODCAST_GENERATE_SCRIPT_PROMPT")
        if not system_prompt:
            system_prompt = self._get_default_system_prompt()
        
        # 场景描述相关提示词
        scene_prompt = f"""## 播客场景
{podcast_dtl.scene}

## 播客氛围
{podcast_dtl.atmosphere}

## 播客配置
- 主持人数量: 1
- 嘉宾数量: {podcast_dtl.guest_count}

## 可用的语音列表如下，请从中为每个角色选择唯一的语音：
{voice_info}
"""
        
        # 准备消息
        messages = [
            ChatMessageDto(role=ChatRoleType.SYSTEM, content=system_prompt),
            ChatMessageDto(role=ChatRoleType.SYSTEM, content=scene_prompt),
            ChatMessageDto(role=ChatRoleType.USER, content=f"以下是我要制作成播客的内容：\n\n{source_content}")
        ]
        
        # 调用AI生成脚本
        script_json = await self.ai_service.chat_completion_async(messages)
        logger.info(f"播客{podcast_dtl.id}，AI生成的脚本：{script_json}")
        
        # 提取JSON部分
        script_items = self._parse_script_json(script_json)
        
        if not script_items:
            raise BusinessException("AI生成的脚本为空")
        
        # 处理SSML内容
        for script_item in script_items:
            ssml_content = script_item.content or ""
            
            try:
                # 验证SSML的合法性
                if self._contains_ssml_tags(ssml_content):
                    # 提取纯文本内容
                    plain_content = self._remove_ssml_tags(ssml_content)
                else:
                    # 没有SSML标记，作为普通文本处理
                    plain_content = ssml_content
                    # 简单地添加基础SSML标记
                    ssml_content = f"<p>{plain_content}</p>"
            except Exception as e:
                logger.error(f"处理SSML内容时出错: {e}")
                # 失败时使用原始内容
                plain_content = self._remove_ssml_tags(ssml_content)
            
            script_item.no_ssml_content = plain_content
            script_item.content = ssml_content
        
        return script_items
    
    def _parse_script_json(self, script_json: str) -> List[PodcastScriptRawItemDto]:
        """
        解析AI返回的脚本JSON
        
        Args:
            script_json: AI生成的脚本JSON字符串
        
        Returns:
            解析后的脚本列表
        """
        try:
            # 尝试直接解析JSON
            data = safe_parse_json(script_json)
            if isinstance(data, list):
                return [PodcastScriptRawItemDto.model_validate(item) for item in data]
        except Exception as e:
            logger.warning(f"直接解析JSON失败: {e}")
        
        # 如果直接解析失败，尝试提取JSON部分
        try:
            # 匹配 JSON 数组格式
            json_pattern = r'\[\s*{[\s\S]*}\s*\]'
            match = re.search(json_pattern, script_json)
            
            if match:
                json_str = match.group(0)
                data = json.loads(json_str)
                return [PodcastScriptRawItemDto.model_validate(item) for item in data]
            else:
                logger.error("未找到有效的JSON数组")
                return []
        except Exception as e:
            logger.error(f"解析脚本JSON失败: {e}")
            raise BusinessException(f"解析AI生成的脚本失败: {e}")
    
    def _contains_ssml_tags(self, text: str) -> bool:
        """
        检查文本是否包含SSML标记
        
        Args:
            text: 要检查的文本
        
        Returns:
            是否包含SSML标记
        """
        if not text:
            return False
        
        # 检查是否包含常见的SSML标记
        ssml_tag_pattern = r'<(?:prosody|emphasis|break|mstts:express-as|p|s|say-as|sub|voice)'
        return bool(re.search(ssml_tag_pattern, text))
    
    def _remove_ssml_tags(self, ssml_text: str) -> str:
        """
        移除SSML标记，保留纯文本内容
        
        Args:
            ssml_text: 包含SSML标记的文本
        
        Returns:
            纯文本内容
        """
        if not ssml_text:
            return ""
        
        try:
            # 移除所有XML标签，保留标签内的文本内容
            plain_text = re.sub(r'<[^>]+>', '', ssml_text)
            
            # 移除多余的空白字符
            plain_text = re.sub(r'\s+', ' ', plain_text).strip()
            
            return plain_text
        except Exception as e:
            logger.error(f"移除SSML标记时出错: {e}")
            # 如果处理失败，尝试使用更简单的方法
            return re.sub(r'<.*?>', '', ssml_text).strip()
    
    def _get_default_system_prompt(self) -> str:
        """
        获取默认系统提示词
        
        Returns:
            默认系统提示词
        """
        return """你是一个专业的播客脚本生成AI。你需要根据提供的内容，生成一段播客对话脚本。

请按照以下格式生成JSON数组输出:
[
  {
    "roleType": "host",
    "roleName": "主持人名称",
    "voiceSymbol": "语音角色ID",
    "content": "对话内容"
  },
  {
    "roleType": "guest",
    "roleName": "嘉宾名称",
    "voiceSymbol": "语音角色ID",
    "content": "对话内容"
  },
  ...
]

注意:
1. roleType必须是 "host"(主持人) 或 "guest"(嘉宾)
2. 根据用户提供的场景和氛围进行创作
3. 语音角色(voiceSymbol)必须从提供的列表中选择
4. 脚本应当有适当的开场白、对话衔接和结束语
5. 每段对话长度控制在50-200字之间
6. 主持人在一开始一定要介绍本期播客的主题
7. 对话应该生动有趣，符合播客的口语风格
8. 总对话轮次控制在10-20轮之间
9. 尽量将内容的重点信息覆盖到对话中

请只返回JSON数组格式的内容，不要有其他解释文字。"""