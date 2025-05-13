"""
视频混剪数据传输对象
"""
import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, field_serializer, HttpUrl, validator


class CreateProjectDto(BaseModel):
    """创建项目DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    name: Optional[str] = Field(None, max_length=255, alias="name")
    description: Optional[str] = Field(None, max_length=500, alias="description")
    target_duration: int = Field(10, ge=10, le=300, alias="targetDuration")
    scene_keywords: Optional[str] = Field(None, max_length=500, alias="sceneKeywords")
    min_relevance_threshold: float = Field(0.6, ge=0, le=1, alias="minRelevanceThreshold")
    narration_style: Optional[str] = Field(None, max_length=100, alias="narrationStyle")
    background_music_type: int = Field(1, ge=1, le=3, alias="backgroundMusicType")


class CreateProjectResultDto(BaseModel):
    """创建项目结果DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    project_id: int = Field(..., alias="projectId")
    name: Optional[str] = Field(None, alias="name")
    create_date: datetime.datetime = Field(..., alias="createDate")


class UploadVideoResultDto(BaseModel):
    """上传视频结果DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    video_id: int = Field(..., alias="videoId")
    file_name: Optional[str] = Field(None, alias="fileName")
    file_size: int = Field(..., alias="fileSize")
    uploaded_at: datetime.datetime = Field(..., alias="uploadedAt")


class UploadAudioResultDto(BaseModel):
    """上传音频结果DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    file_name: Optional[str] = Field(None, alias="fileName")
    file_size: int = Field(..., alias="fileSize")
    uploaded_at: datetime.datetime = Field(..., alias="uploadedAt")


class SourceVideoDto(BaseModel):
    """源视频DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(..., alias="id")
    file_name: Optional[str] = Field(None, alias="fileName")
    file_size: int = Field(..., alias="fileSize")
    duration: float = Field(..., alias="duration")
    width: int = Field(..., alias="width")
    height: int = Field(..., alias="height")
    frame_rate: float = Field(..., alias="frameRate")
    bit_rate: int = Field(..., alias="bitRate")
    status: int = Field(..., alias="status")
    create_date: datetime.datetime = Field(..., alias="createDate")


class SelectedSceneNarrationDto(BaseModel):
    """选中场景的解说词DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(..., alias="id")
    selected_scene_id: int = Field(..., alias="selectedSceneId")
    narration: Optional[str] = Field(None, alias="narration")
    narration_audio_path: Optional[str] = Field(None, alias="narrationAudioPath")
    duration: float = Field(..., alias="duration")
    create_date: datetime.datetime = Field(..., alias="createDate")


class SelectedSceneDto(BaseModel):
    """选中场景DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(..., alias="id")
    source_video_id: int = Field(..., alias="sourceVideoId")
    sequence_order: int = Field(..., alias="sequenceOrder")
    start_time: str = Field(..., alias="startTime")
    end_time: str = Field(..., alias="endTime")
    duration: float = Field(..., alias="duration")
    scene_description: Optional[str] = Field(None, alias="sceneDescription")
    status: int = Field(..., alias="status")
    create_date: datetime.datetime = Field(..., alias="createDate")
    narrations: Optional[List[SelectedSceneNarrationDto]] = Field(None, alias="narrations")
    
    # 将float类型的时间转换为"hh:mm:ss.fff"格式字符串
    @field_serializer('start_time', 'end_time')
    def serialize_time(self, time_str: str) -> str:
        # 假设输入是timedelta或秒数，转换为 HH:MM:SS.fff 格式
        hours, remainder = divmod(float(time_str), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02}:{int(minutes):02}:{seconds:06.3f}"
    
    # 格式化器，处理时间字符串转换
    @field_validator('start_time', 'end_time', mode='before')
    @classmethod
    def validate_time(cls, v):
        if isinstance(v, (int, float)):
            # 如果是数字，表示秒数
            return str(v)
        if hasattr(v, 'total_seconds'):
            # 如果是timedelta对象
            return str(v.total_seconds())
        # 原样返回字符串
        return str(v)


class FinalVideoDto(BaseModel):
    """最终视频DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(..., alias="id")
    video_url: Optional[str] = Field(None, alias="videoUrl")
    duration: float = Field(..., alias="duration")
    width: int = Field(..., alias="width")
    height: int = Field(..., alias="height")
    file_size: int = Field(..., alias="fileSize")
    create_date: datetime.datetime = Field(..., alias="createDate")


class GenerateVideoResultDto(BaseModel):
    """生成视频结果DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    video_id: int = Field(..., alias="videoId")
    video_url: Optional[str] = Field(None, alias="videoUrl")
    duration: float = Field(..., alias="duration")
    width: int = Field(..., alias="width")
    height: int = Field(..., alias="height")
    file_size: int = Field(..., alias="fileSize")
    generated_at: datetime.datetime = Field(..., alias="generatedAt")


class ProcessLogDto(BaseModel):
    """处理日志DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(..., alias="id")
    process_step: int = Field(..., alias="processStep")
    status: int = Field(..., alias="status")
    message: Optional[str] = Field(None, alias="message")
    create_date: datetime.datetime = Field(..., alias="createDate")
    
    # 派生属性
    process_step_name: Optional[str] = Field(None, alias="processStepName")
    status_name: Optional[str] = Field(None, alias="statusName")
    
    @field_serializer('process_step_name')
    def serialize_process_step_name(self, v, _) -> str:
        # 如果已经有值，直接返回
        if v is not None:
            return v
        # 否则根据process_step计算
        step_names = {
            1: "视频上传",
            2: "视频分析",
            3: "场景检测",
            4: "AI分析",
            5: "音频生成",
            6: "视频合成",
            7: "处理失败"
        }
        return step_names.get(self.process_step, "未知步骤")
    
    @field_serializer('status_name')
    def serialize_status_name(self, v, _) -> str:
        # 如果已经有值，直接返回
        if v is not None:
            return v
        # 否则根据status计算
        status_names = {
            0: "进行中",
            1: "成功",
            2: "失败"
        }
        return status_names.get(self.status, "未知状态")


class ProjectListItemDto(BaseModel):
    """项目列表项DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(..., alias="id")
    name: Optional[str] = Field(None, alias="name")
    description: Optional[str] = Field(None, alias="description")
    target_duration: int = Field(..., alias="targetDuration")
    scene_keywords: Optional[str] = Field(None, alias="sceneKeywords")
    min_relevance_threshold: float = Field(..., alias="minRelevanceThreshold")
    narration_style: Optional[str] = Field(None, alias="narrationStyle")
    background_music_type: int = Field(..., alias="backgroundMusicType")
    background_music_path: Optional[str] = Field(None, alias="backgroundMusicPath")
    status: int = Field(..., alias="status")
    create_date: datetime.datetime = Field(..., alias="createDate")
    final_video_url: Optional[str] = Field(None, alias="finalVideoUrl")
    error_message: Optional[str] = Field(None, alias="errorMessage")


class ProjectDto(BaseModel):
    """项目DTO"""
    model_config = ConfigDict(populate_by_name=True)
    
    id: int = Field(..., alias="id")
    name: Optional[str] = Field(None, alias="name")
    description: Optional[str] = Field(None, alias="description")
    target_duration: int = Field(..., alias="targetDuration")
    scene_keywords: Optional[str] = Field(None, alias="sceneKeywords")
    min_relevance_threshold: float = Field(..., alias="minRelevanceThreshold")
    narration_style: Optional[str] = Field(None, alias="narrationStyle")
    background_music_type: int = Field(..., alias="backgroundMusicType")
    background_music_path: Optional[str] = Field(None, alias="backgroundMusicPath")
    status: int = Field(..., alias="status")
    is_generate_lock: int = Field(..., alias="isGenerateLock")
    is_running: int = Field(..., alias="isRunning")
    create_date: datetime.datetime = Field(..., alias="createDate")
    final_video_url: Optional[str] = Field(None, alias="finalVideoUrl")
    error_message: Optional[str] = Field(None, alias="errorMessage")
    final_video: Optional[FinalVideoDto] = Field(None, alias="finalVideo")
    source_videos: List[SourceVideoDto] = Field(default_factory=list, alias="sourceVideos")
    selected_scenes: List[SelectedSceneDto] = Field(default_factory=list, alias="selectedScenes")
    status_name: Optional[str] = Field(None, alias="statusName")
    
    @field_serializer('status_name')
    def serialize_status_name(self, v, _) -> str:
        # 如果已经有值，直接返回
        if v is not None:
            return v
        # 否则根据status计算
        status_names = {
            0: "已创建",
            1: "视频上传完成",
            2: "视频分析完成",
            3: "场景检测完成",
            4: "AI分析完成",
            5: "音频生成完成",
            6: "视频合成完成",
            7: "视频处理失败"
        }
        return status_names.get(self.status, "未知状态")


class VideoMetadata:
    """视频元数据类"""
    duration: float = 0.0  # 视频时长(秒)
    width: int = 0  # 视频宽度(像素)
    height: int = 0  # 视频高度(像素)
    frame_rate: float = 0.0  # 视频帧率
    bit_rate: int = 0  # 视频比特率
    codec: Optional[str] = None  # 视频编码格式


class SceneFrameInfo:
    """场景帧信息类"""
    id: int = 0  # 编号Id
    frame_number: int = 0  # 帧序号
    sequence_order: int = 0  # AI会重排编号
    frame_time: datetime.timedelta = datetime.timedelta(0)  # 帧时间点（开始时间）
    end_time: datetime.timedelta = datetime.timedelta(0)  # 帧时间点（结束时间）
    image_path: Optional[str] = None  # 帧图片存储路径
    image_url: Optional[str] = None  # 帧图片CDN URL
    source_video_id: int = 0  # 源视频ID
    selected: bool = False  # 是否被选中
    content: Optional[str] = None  # 场景内容描述
    keywords: List[str] = []  # 关键词列表
    narratives: Optional[List[str]] = None  # 解说词列表
    relevance_score: float = 0.0  # 相关性得分
    
    @property
    def duration(self) -> datetime.timedelta:
        """获取时长"""
        return self.end_time - self.frame_time


class AIAnalysisResult:
    """AI分析结果类"""
    analysis_id: int = 0  # AI分析结果ID
    selected_scenes: Optional[List[SceneFrameInfo]] = None  # 选中的场景列表
    narration_script: Optional[str] = None  # 总体叙事脚本


class AnalysisRequest:
    """视频分析参数"""
    scene_keywords: Optional[str] = None  # 场景关键词
    narration_style: Optional[str] = None  # 解说词风格
    content_filter: Optional[str] = None  # 内容过滤
    target_duration: int = 10  # 目标视频时长（秒）
    min_relevance_threshold: float = 0.6  # 最低相关度阈值