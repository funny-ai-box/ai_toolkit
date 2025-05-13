"""
视频分析服务实现
"""
import os
import re
import json
import logging
import subprocess
import datetime
from typing import List, Dict, Tuple, Optional, Any

from app.modules.tools.videomixer.dtos import VideoMetadata, SceneFrameInfo

logger = logging.getLogger(__name__)


class VideoAnalysisService:
    """视频分析服务实现类"""
    
    def __init__(self):
        """初始化视频分析服务"""
        pass
    
    async def analyse_video_async(self, video_path: str) -> VideoMetadata:
        """
        分析视频元数据
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            视频元数据
        """
        try:
            logger.info(f"开始分析视频元数据: {video_path}")
            
            # 使用FFProbe分析视频文件
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                video_path
            ]
            
            # 执行命令并获取输出
            output = subprocess.check_output(cmd, universal_newlines=True)
            media_info = json.loads(output)
            
            # 提取视频流信息
            video_stream = None
            for stream in media_info.get("streams", []):
                if stream.get("codec_type") == "video":
                    video_stream = stream
                    break
            
            if not video_stream:
                raise ValueError("无法获取视频流信息")
            
            # 提取信息
            duration = float(media_info.get("format", {}).get("duration", "0"))
            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))
            
            # 解析帧率
            frame_rate = 0.0
            frame_rate_str = video_stream.get("r_frame_rate", "")
            if frame_rate_str and "/" in frame_rate_str:
                num, denom = map(int, frame_rate_str.split("/"))
                if denom > 0:
                    frame_rate = num / denom
            
            # 解析比特率
            bit_rate = 0
            bit_rate_str = video_stream.get("bit_rate") or media_info.get("format", {}).get("bit_rate", "0")
            if bit_rate_str:
                bit_rate = int(bit_rate_str)
            
            # 创建元数据对象
            metadata = VideoMetadata()
            metadata.duration = duration
            metadata.width = width
            metadata.height = height
            metadata.frame_rate = frame_rate
            metadata.bit_rate = bit_rate
            metadata.codec = video_stream.get("codec_name", "")
            
            logger.info(f"视频元数据分析完成: Duration={metadata.duration}s, Resolution={metadata.width}x{metadata.height}, FrameRate={metadata.frame_rate}")
            return metadata
        
        except Exception as e:
            logger.error(f"分析视频元数据失败: {str(e)}", exc_info=True)
            raise
    
    async def detect_scenes_async(
        self, 
        video_path: str, 
        output_dir: str,
        scene_threshold: float = 0.3, 
        image_quality: int = 3
    ) -> List[SceneFrameInfo]:
        """
        检测视频场景关键帧
        
        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            scene_threshold: 场景阈值，差异值被归一化到 0-1 范围，当差异值大于 0.3（30%）时，认为发生了明显的场景变化
            image_quality: 图片质量(1-31，1为最高)
            
        Returns:
            场景帧列表
        """
        try:
            logger.info(f"开始检测视频场景: {video_path}, 阈值: {scene_threshold}")
            
            # 确保输出目录存在
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            # 生成输出文件名模式
            output_pattern = os.path.join(output_dir, "frame_%06d.jpg")
            
            # 用于存储帧号和时间点的映射
            pts_mapping = {}
            
            # 正则表达式用来匹配输出中的 n:值 和 pts_time:值
            info_regex = re.compile(r'n:\s*(\d+).*pts_time:(\d+(?:\.\d+)?)')
            
            # 配置场景检测参数
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-vf", f"select='isnan(prev_selected_t)+gt(scene,{scene_threshold})',showinfo",
                "-vsync", "vfr",
                "-q:v", str(image_quality),
                "-threads", "4",
                output_pattern
            ]
            
            # 执行命令并捕获标准错误输出
            process = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                universal_newlines=True
            )
            
            # 读取stderr并解析信息
            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break
                
                # 解析帧信息
                match = info_regex.search(line)
                if match:
                    frame_number = int(match.group(1))
                    pts_time = float(match.group(2))
                    pts_mapping[frame_number] = pts_time
            
            # 等待进程完成
            process.wait()
            
            # 检查进程是否成功
            if process.returncode != 0:
                raise RuntimeError(f"场景检测失败，FFmpeg返回代码: {process.returncode}")
            
            if not pts_mapping:
                raise ValueError("场景PTS帧检测失败，未能找到帧映射信息")
            
            # 收集检测到的场景帧信息
            scene_frames = self._create_frame_list_from_files(output_dir, output_pattern, pts_mapping)
            
            # 按帧时间排序
            scene_frames.sort(key=lambda x: x.frame_time.total_seconds())
            
            logger.info(f"场景检测完成，共检测到 {len(scene_frames)} 个场景帧")
            return scene_frames
        
        except Exception as e:
            logger.error(f"检测视频场景失败: {str(e)}", exc_info=True)
            raise
    
    def _create_frame_list_from_files(
        self, 
        temp_folder: str, 
        pattern: str, 
        pts_mapping: Dict[int, float]
    ) -> List[SceneFrameInfo]:
        """
        从文件创建帧列表
        
        Args:
            temp_folder: 临时文件夹
            pattern: 文件名模式
            pts_mapping: 帧号和时间点的映射
            
        Returns:
            帧列表
        """
        frames = []
        pattern_dir = os.path.dirname(pattern) or temp_folder
        pattern_base = os.path.basename(pattern).replace("%06d", "*")
        
        # 获取所有匹配的文件
        import glob
        frame_files = sorted(glob.glob(os.path.join(pattern_dir, pattern_base)))
        
        for i, file_path in enumerate(frame_files):
            # 从文件名中提取帧号
            frame_number = self._extract_frame_number(file_path)
            
            # 获取时间点，如果没有则使用0
            second = 0
            if i >= 1 and i in pts_mapping:
                second = pts_mapping[i]
            
            # 创建帧信息对象
            frame = SceneFrameInfo()
            frame.id = 0  # 暂时使用0，后面会由仓储层赋值
            frame.frame_number = frame_number
            frame.frame_time = datetime.timedelta(seconds=second)
            frame.image_path = file_path
            
            frames.append(frame)
        
        # 计算结束时间
        for i in range(len(frames)):
            if i < len(frames) - 1:
                # 如果不是最后一帧，结束时间为下一帧的开始时间减去间隔
                next_frame_start = frames[i + 1].frame_time
                frames[i].end_time = next_frame_start - datetime.timedelta(milliseconds=200)  # 200ms间隔
            else:
                # 如果是最后一帧，结束时间为当前帧开始时间加上平均帧间隔
                avg_frame_interval = self._calculate_average_frame_interval(frames)
                frames[i].end_time = frames[i].frame_time + avg_frame_interval - datetime.timedelta(milliseconds=200)
        
        return frames
    
    def _extract_frame_number(self, file_path: str) -> int:
        """
        从文件名中提取帧号
        
        Args:
            file_path: 文件路径
            
        Returns:
            帧号
        """
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        number_part = file_name.split('_')[-1]
        return int(number_part) if number_part.isdigit() else 0
    
    def _calculate_average_frame_interval(self, frames: List[SceneFrameInfo]) -> datetime.timedelta:
        """
        计算平均帧间隔
        
        Args:
            frames: 帧列表
            
        Returns:
            平均帧间隔
        """
        if len(frames) <= 1:
            return datetime.timedelta(seconds=1/30)  # 默认使用30fps
        
        total_duration = frames[-1].frame_time - frames[0].frame_time
        return datetime.timedelta(microseconds=total_duration.microseconds // (len(frames) - 1))