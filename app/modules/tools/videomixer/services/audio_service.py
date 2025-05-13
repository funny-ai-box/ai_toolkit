"""
音频服务实现
"""
import os
import subprocess
import logging
import datetime
from typing import Tuple, Optional


from app.core.ai.speech.speech_service import AISpeechService
from app.core.config.settings import settings

logger = logging.getLogger(__name__)


class AudioService:
    """音频服务实现类"""
    
    def __init__(self, speech_service: AISpeechService):
        """
        初始化音频服务
        
        Args:
            speech_service: 语音服务
        """
        self.speech_service = speech_service
        
        # 从配置中获取
        self.voice_type = settings.get_or_default("VideoMixer.VoicePlatformType", "AzureSpeech")
        self.voice_symbol = settings.get_or_default("VideoMixer.VoiceSymbol", "zh-CN-XiaoxiaoNeural")
        
        self.audio_local_dir = settings.get_or_default("VideoMixer.VoiceLocalStoragePath", "uploads/videomixer/narration_audio")
        
        # 确保音频存储目录存在
        if not os.path.exists(self.audio_local_dir):
            os.makedirs(self.audio_local_dir, exist_ok=True)
    
    async def text_to_speech_async(self, task_id: int, text: str) -> Tuple[bool, str, datetime.timedelta]:
        """
        将文本转换为语音
        
        Args:
            task_id: 任务ID
            text: 文本内容
            
        Returns:
            元组 (是否成功, 音频URL, 音频时长)
        """
        encoding = "wav"
        audio_file_name = f"{task_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.{encoding}"
        
        # 生成音频文件路径
        audio_path = os.path.join(self.audio_local_dir, audio_file_name)
        
        logger.info(f"开始文本转语音: {text[:min(30, len(text))]}..., 输出路径: {audio_path}")
        
        try:
            # 调用语音服务
            success, audio_duration = await self.speech_service.synthesize_speech_async(
                text, audio_path, self.voice_symbol
            )
            
            if not success:
                logger.error(f"文本转语音失败: {task_id}")
                return False, "", datetime.timedelta()
            
            return True, audio_path, audio_duration
        
        except Exception as e:
            logger.error(f"文本转语音失败: {str(e)}", exc_info=True)
            return False, "", datetime.timedelta()


class AudioHelper:
    """音频处理辅助类"""
    
    @staticmethod
    async def convert_to_mp3_async(input_path: str, output_path: str, bit_rate: int = 128000) -> bool:
        """
        音频转换为mp3格式
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            bit_rate: 比特率
            
        Returns:
            转换是否成功
        """
        try:
            # 使用FFmpeg进行转换
            cmd = [
                "ffmpeg",
                "-i", input_path,
                "-b:a", str(bit_rate),
                "-acodec", "libmp3lame",
                "-q:a", "2",
                "-y",  # 覆盖已存在的文件
                output_path
            ]
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"音频转换失败: {stderr}")
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"音频转换失败: {str(e)}", exc_info=True)
            return False
    
    @staticmethod
    async def adjust_volume_async(input_path: str, output_path: str, volume_scale: float = 1.0) -> bool:
        """
        音频音量调整
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            volume_scale: 音量缩放比例
            
        Returns:
            调整是否成功
        """
        try:
            # 使用FFmpeg调整音量
            cmd = [
                "ffmpeg",
                "-i", input_path,
                "-filter:a", f"volume={volume_scale}",
                "-acodec", "libmp3lame",
                "-b:a", "192000",
                "-y",  # 覆盖已存在的文件
                output_path
            ]
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"音量调整失败: {stderr}")
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"音量调整失败: {str(e)}", exc_info=True)
            return False
    
    @staticmethod
    async def create_looped_version_async(input_path: str, target_duration: datetime.timedelta, output_path: str) -> bool:
        """
        创建循环版本的音频
        
        Args:
            input_path: 输入文件路径
            target_duration: 目标时长
            output_path: 输出文件路径
            
        Returns:
            创建是否成功
        """
        try:
            # 获取原始音频时长
            cmd_duration = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                input_path
            ]
            
            original_duration = float(subprocess.check_output(cmd_duration, universal_newlines=True).strip())
            
            # 计算需要重复的次数
            repetitions = int(target_duration.total_seconds() / original_duration) + 1
            
            # 使用filter_complex进行音频循环
            filter_complex = ""
            
            # 创建输入流引用
            for i in range(repetitions):
                filter_complex += "[0:a]"
            
            # 连接所有片段
            filter_complex += f"concat=n={repetitions}:v=0:a=1[aout]"
            
            # 执行命令
            cmd = [
                "ffmpeg",
                "-i", input_path,
                "-filter_complex", filter_complex,
                "-map", "[aout]",
                "-acodec", "libmp3lame",
                "-b:a", "192000",
                "-t", str(target_duration.total_seconds()),
                "-y",  # 覆盖已存在的文件
                output_path
            ]
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"创建循环版本失败: {stderr}")
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"创建循环版本失败: {str(e)}", exc_info=True)
            return False
    
    @staticmethod
    async def apply_fade_effects_async(
        input_path: str, 
        output_path: str, 
        fade_in_duration: datetime.timedelta, 
        fade_out_duration: datetime.timedelta
    ) -> bool:
        """
        应用淡入淡出效果
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            fade_in_duration: 淡入持续时间
            fade_out_duration: 淡出持续时间
            
        Returns:
            应用是否成功
        """
        try:
            # 获取原始音频时长
            cmd_duration = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                input_path
            ]
            
            original_duration = float(subprocess.check_output(cmd_duration, universal_newlines=True).strip())
            
            # 构建淡入淡出滤镜
            fade_filter = (
                f"afade=t=in:st=0:d={fade_in_duration.total_seconds()},"
                f"afade=t=out:st={original_duration - fade_out_duration.total_seconds()}:d={fade_out_duration.total_seconds()}"
            )
            
            # 执行命令
            cmd = [
                "ffmpeg",
                "-i", input_path,
                "-af", fade_filter,
                "-acodec", "libmp3lame",
                "-b:a", "192000",
                "-y",  # 覆盖已存在的文件
                output_path
            ]
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"应用淡入淡出效果失败: {stderr}")
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"应用淡入淡出效果失败: {str(e)}", exc_info=True)
            return False