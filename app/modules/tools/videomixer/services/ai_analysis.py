"""
AI分析服务实现
"""
import os
import json
import logging
import re
from typing import List, Dict, Any, Optional


from app.core.ai.chat.base import IChatAIService
from app.modules.base.prompts.services import PromptTemplateService
from app.modules.tools.videomixer.dtos import SceneFrameInfo, AIAnalysisResult, AnalysisRequest

logger = logging.getLogger(__name__)


class AIAnalysisService:
    """AI服务实现类"""
    
    def __init__(self, ai_service: IChatAIService, prompt_template_service: PromptTemplateService):
        """
        初始化AI服务
        
        Args:
            ai_service: AI服务实例
            prompt_template_service: 提示词模板服务
        """
        self.ai_service = ai_service
        self.prompt_template_service = prompt_template_service
    
    async def analyze_scenes_async(
        self, 
        project_id: int, 
        analysis_request: AnalysisRequest,
        frames: List[SceneFrameInfo]
    ) -> AIAnalysisResult:
        """
        分析场景图片并选择最佳组合
        
        Args:
            project_id: 项目ID
            analysis_request: 视频分析参数
            frames: 场景帧信息列表
            
        Returns:
            AI分析结果
        """
        try:
            logger.info(
                f"开始分析场景: 项目ID={project_id}, "
                f"目标时长={analysis_request.target_duration}秒, "
                f"关键词={analysis_request.scene_keywords}"
            )
            
            if not frames:
                raise ValueError("场景帧列表为空")
            
            # 构建分析提示词
            messages = await self._build_message_list(frames, analysis_request)
            
            # 调用AI服务进行分析
            response_json = await self.ai_service.chat_completion_async(messages)
            
            # 处理分析结果
            final_scenes = self._process_response(response_json, frames, analysis_request)
            
            result = AIAnalysisResult()
            result.analysis_id = 0  # 将由调用者设置
            result.selected_scenes = final_scenes
            
            if final_scenes:
                narratives = [scene.narratives for scene in final_scenes if scene.narratives]
                all_narratives = []
                for narr_list in narratives:
                    if narr_list:
                        all_narratives.extend(narr_list)
                
                result.narration_script = " ".join(all_narratives) if all_narratives else ""
            
            logger.info(f"场景分析完成: 选择了 {len(final_scenes) if final_scenes else 0} 个场景")
            return result
        
        except Exception as e:
            logger.error(f"分析场景失败: {str(e)}")
            raise
    
    async def generate_music_async(self, scene_keywords: str, output_path: str) -> bool:
        """
        根据场景和关键词生成音乐
        
        Args:
            scene_keywords: 场景关键词
            output_path: 输出文件路径
            
        Returns:
            操作是否成功
        """
        try:
            logger.info(f"开始生成背景音乐，关键词: {scene_keywords}")
            
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            # 从媒体库中选择一个预设音频文件
            from app.core.config.settings import settings
            preset_music_path = settings.get_or_default("VideoMixer.PresetMusicPath", "Files/PresetMusic/")
            
            if not os.path.exists(preset_music_path):
                logger.warning("预设音乐文件不存在，无法生成背景音乐")
                return False
            
            # 获取目录下的所有mp3文件
            import glob
            mp3_files = glob.glob(os.path.join(preset_music_path, "*.mp3"))
            
            if not mp3_files:
                logger.warning("预设音乐目录下没有音乐文件")
                return False
            
            # 随机选择一个音乐文件
            import random
            selected_music = random.choice(mp3_files)
            
            # 复制预设音乐文件到输出路径
            import shutil
            shutil.copy2(selected_music, output_path)
            
            logger.info(f"背景音乐生成完成: {output_path}")
            return True
        
        except Exception as e:
            logger.error(f"生成背景音乐失败: {str(e)}")
            return False
    
    async def _build_message_list(
        self, 
        frames: List[SceneFrameInfo], 
        request: AnalysisRequest
    ) -> List[Dict[str, Any]]:
        """
        构建消息列表
        
        Args:
            frames: 场景帧列表
            request: 分析请求
            
        Returns:
            消息列表
        """
        messages = []
        
        # 系统提示词
        system_prompt = await self.prompt_template_service.get_content_by_key_async("VIDEOMIXER_SCENE_ANALYSIS_PROMPT")
        if not system_prompt:
            # 如果没有模板，使用默认提示词
            system_prompt = (
                "你是视频编辑专家，负责从提供的视频帧中选择最相关的场景，"
                "并根据场景内容生成自然流畅的解说词。"
                "请根据场景关键词和目标时长，选择最适合的场景组合，"
                "确保选择的场景具有故事连贯性和吸引力。"
                "对于每个选定的场景，请提供详细的解说词，语言风格要符合要求。"
            )
        
        messages.append({"role": "system", "content": system_prompt})
        
        # 变量提示词
        variable_prompt = f"""目标关键词：@keywords = {request.scene_keywords}
最小关键词相关度：@minRelevance = {request.min_relevance_threshold}
目标时长（秒）：@targetDuration = {request.target_duration}
期望风格：@narrationStyle = {request.narration_style}"""
        
        messages.append({"role": "system", "content": variable_prompt})
        
        # 帧数据上下文
        context_message = f"**帧数据：**\n总共有 {len(frames)} 帧待分析"
        messages.append({"role": "user", "content": context_message})
        
        # 添加每一帧的图片
        for frame in frames:
            if frame.image_url:
                frame_message = {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"帧图片编号：{frame.id}; 时长：{frame.duration.total_seconds():.1f}秒\n"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": frame.image_url
                            }
                        }
                    ]
                }
                messages.append(frame_message)
        
        # 请求分析
        messages.append({
            "role": "user",
            "content": (
                f"请分析以上视频帧，基于关键词\"{request.scene_keywords}\"选择相关度最高的场景，"
                f"总时长接近{request.target_duration}秒。"
                f"为每个场景生成风格为\"{request.narration_style}\"的解说词。"
                f"请以JSON格式回复，包含场景ID、时间、描述、相关度、解说词等信息。"
            )
        })
        
        return messages
    
    def _process_response(
        self, 
        content: str, 
        frames: List[SceneFrameInfo],
        request: AnalysisRequest
    ) -> List[SceneFrameInfo]:
        """
        处理分析响应
        
        Args:
            content: AI响应内容
            frames: 场景帧列表
            request: 分析请求
            
        Returns:
            处理后的场景帧列表
        """
        try:
            # 提取JSON部分
            json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个响应
                json_str = content
            
            # 解析JSON
            response = json.loads(json_str)
            
            # 更新帧信息
            frame_dict = {frame.id: frame for frame in frames}
            selected_frames = []
            
            # 首先检查是否存在frames数组
            if "frames" in response:
                for analysis in response["frames"]:
                    if analysis.get("isSelected", False):
                        frame_id = analysis.get("id")
                        if frame_id in frame_dict:
                            frame = frame_dict[frame_id]
                            frame.content = analysis.get("description", "")
                            frame.selected = True
                            frame.sequence_order = analysis.get("sequenceNumber", 0)
                            frame.keywords = analysis.get("keywords", [])
                            frame.narratives = analysis.get("narratives", [])
                            frame.relevance_score = analysis.get("relevanceScore", 0.0)
                            selected_frames.append(frame)
            
            # 按序号排序
            selected_frames.sort(key=lambda f: f.sequence_order)
            
            return selected_frames
        
        except Exception as e:
            logger.error(f"处理AI响应失败: {str(e)}")
            # 出错时返回空列表
            return []