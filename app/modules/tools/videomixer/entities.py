"""
视频混剪实体模型
"""
import datetime
from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Float, Text, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.session import Base 


class MixProject(Base):
    """混剪项目实体"""
    __tablename__ = "video_mix_project"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="UserId", comment="用户ID")
    name: Mapped[str] = mapped_column(String(255), nullable=True, name="Name", comment="项目名称")
    description: Mapped[str] = mapped_column(String(500), nullable=True, name="Description", comment="项目描述")
    target_duration: Mapped[int] = mapped_column(Integer, nullable=False, name="TargetDuration", comment="目标视频时长（秒）", default=10)
    scene_keywords: Mapped[str] = mapped_column(String(500), nullable=True, name="SceneKeywords", comment="场景关键词")
    min_relevance_threshold: Mapped[float] = mapped_column(Float(precision=2), nullable=False, name="MinRelevanceThreshold", 
                                                      comment="最低相关度阈值（0-1之间）", default=0.6)
    narration_style: Mapped[str] = mapped_column(String(100), nullable=True, name="NarrationStyle", comment="视频解说词风格")
    background_music_type: Mapped[int] = mapped_column(Integer, nullable=True, name="BackgroundMusicType", 
                                                  comment="背景音乐类型（1=AI生成，2=系统随机内置，3=上传音乐文件）", default=1)
    background_music_path: Mapped[str] = mapped_column(String(500), nullable=True, name="BackgroundMusicPath", 
                                                  comment="上传的背景音乐文件路径（当BackgroundMusicType=3时有值）")
    status: Mapped[int] = mapped_column(Integer, nullable=False, name="Status", 
                                   comment="项目状态 (0=创建, 1=视频上传完成, 2=视频分析完成, 3=场景检测完成, 4=AI分析完成, 5=音频生成完成, 6=视频合成完成，7=生成出现错误)", 
                                   default=0)
    is_generate_lock: Mapped[int] = mapped_column(Integer, nullable=True, name="IsGenerateLock", 
                                             comment="是否视频生成锁定（0=没有, 1=界面点了执行就锁定，后面就不能再编辑和生成）", default=0)
    is_running: Mapped[int] = mapped_column(Integer, nullable=True, name="IsRunning", 
                                       comment="是否正在任务执行中（0=没有, 1=执行中）", default=0)
    final_video_url: Mapped[str] = mapped_column(String(500), nullable=True, name="FinalVideoUrl", comment="最终生成的视频URL")
    error_message: Mapped[str] = mapped_column(Text, nullable=True, name="ErrorMessage", comment="错误信息（如果有）")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", 
                                                      server_default=func.now(), comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", 
                                                           server_default=func.now(), comment="最后修改时间")


class SourceVideo(Base):
    """源视频实体"""
    __tablename__ = "video_mix_source_video"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="ProjectId", comment="所属项目ID")
    file_name: Mapped[str] = mapped_column(String(255), nullable=True, name="FileName", comment="视频文件名")
    file_path: Mapped[str] = mapped_column(String(500), nullable=True, name="FilePath", comment="视频存储路径/URL")
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, name="FileSize", comment="视频大小（字节）")
    duration: Mapped[float] = mapped_column(Float(precision=2), nullable=False, name="Duration", comment="视频时长（秒）", default=0)
    width: Mapped[int] = mapped_column(Integer, nullable=False, name="Width", comment="视频宽度（像素）", default=0)
    height: Mapped[int] = mapped_column(Integer, nullable=False, name="Height", comment="视频高度（像素）", default=0)
    frame_rate: Mapped[float] = mapped_column(Float(precision=2), nullable=False, name="FrameRate", comment="视频帧率", default=0)
    bit_rate: Mapped[int] = mapped_column(BigInteger, nullable=False, name="BitRate", comment="视频比特率", default=0)
    codec: Mapped[str] = mapped_column(String(50), nullable=True, name="Codec", comment="视频编码格式")
    status: Mapped[int] = mapped_column(Integer, nullable=False, name="Status", 
                                   comment="处理状态 (0=上传完成, 1=验证完成, 2=场景检测完成)", default=0)
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", 
                                                      server_default=func.now(), comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", 
                                                           server_default=func.now(), comment="最后修改时间")


class SceneFrame(Base):
    """场景帧实体"""
    __tablename__ = "video_mix_scene_frame"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    source_video_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="SourceVideoId", 
                                            comment="所属源视频ID")
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="ProjectId", comment="所属项目ID")
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False, name="FrameNumber", comment="帧序号")
    frame_time: Mapped[float] = mapped_column(Float(precision=3), nullable=False, name="FrameTime", 
                                         comment="帧时间点（开始时间，秒）")
    end_time: Mapped[float] = mapped_column(Float(precision=3), nullable=False, name="EndTime", 
                                       comment="帧时间点（结束时间，秒）")
    image_path: Mapped[str] = mapped_column(String(500), nullable=True, name="ImagePath", comment="帧图片存储路径")
    image_url: Mapped[str] = mapped_column(String(500), nullable=True, name="ImageUrl", comment="帧图片CDN URL")
    is_selected: Mapped[int] = mapped_column(Integer, nullable=False, name="IsSelected", 
                                        comment="是否被AI选中（0=否, 1=是）", default=0)
    relevance_score: Mapped[float] = mapped_column(Float(precision=4), nullable=False, name="RelevanceScore", 
                                              comment="AI分析的相关度得分（与关键词的匹配程度）", default=0)
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", 
                                                      server_default=func.now(), comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", 
                                                           server_default=func.now(), comment="最后修改时间")


class SelectedScene(Base):
    """选中场景实体"""
    __tablename__ = "video_mix_selected_scene"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="ProjectId", comment="所属项目ID")
    source_video_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="SourceVideoId", 
                                            comment="所属源视频ID")
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, name="SequenceOrder", comment="场景顺序")
    start_time: Mapped[float] = mapped_column(Float(precision=3), nullable=False, name="StartTime", 
                                         comment="场景开始时间（在源视频中的时间点，秒）")
    end_time: Mapped[float] = mapped_column(Float(precision=3), nullable=False, name="EndTime", 
                                       comment="场景结束时间（在源视频中的时间点，秒）")
    duration: Mapped[float] = mapped_column(Float(precision=3), nullable=False, name="Duration", 
                                       comment="场景持续时间（秒）")
    scene_description: Mapped[str] = mapped_column(String(500), nullable=True, name="SceneDescription", 
                                              comment="场景相关性描述")
    scene_video_path: Mapped[str] = mapped_column(String(2000), nullable=True, name="SceneVideoPath", 
                                             comment="生成的场景视频片段路径")
    status: Mapped[int] = mapped_column(Integer, nullable=False, name="Status", 
                                   comment="场景处理状态 (0=选中, 1=解说音频生成完成, 2=场景视频生成完成)", default=0)
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", 
                                                      server_default=func.now(), comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", 
                                                           server_default=func.now(), comment="最后修改时间")


class SelectedSceneNarration(Base):
    """选中场景实体的解说词和音频"""
    __tablename__ = "video_mix_selected_scene_narration"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="ProjectId", comment="所属项目ID")
    selected_scene_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="SelectedSceneId", 
                                              comment="所属场景ID")
    duration: Mapped[float] = mapped_column(Float(precision=3), nullable=False, name="Duration", 
                                        comment="持续时间（秒）")
    narration: Mapped[str] = mapped_column(String(500), nullable=True, name="Narration", comment="场景解说词")
    narration_audio_path: Mapped[str] = mapped_column(String(500), nullable=True, name="NarrationAudioPath", 
                                                 comment="解说音频文件路径")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", 
                                                      server_default=func.now(), comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", 
                                                           server_default=func.now(), comment="最后修改时间")


class FinalVideo(Base):
    """最终视频实体"""
    __tablename__ = "video_mix_final_video"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="ProjectId", comment="所属项目ID")
    title: Mapped[str] = mapped_column(String(255), nullable=True, name="Title", comment="视频标题")
    description: Mapped[str] = mapped_column(String(500), nullable=True, name="Description", comment="视频描述")
    file_path: Mapped[str] = mapped_column(String(500), nullable=True, name="FilePath", comment="视频存储路径")
    video_url: Mapped[str] = mapped_column(String(500), nullable=True, name="VideoUrl", comment="视频CDN URL")
    duration: Mapped[float] = mapped_column(Float(precision=2), nullable=False, name="Duration", comment="视频时长（秒）")
    width: Mapped[int] = mapped_column(Integer, nullable=False, name="Width", comment="视频宽度（像素）")
    height: Mapped[int] = mapped_column(Integer, nullable=False, name="Height", comment="视频高度（像素）")
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, name="FileSize", comment="视频大小（字节）")
    background_music_path: Mapped[str] = mapped_column(String(500), nullable=True, name="BackgroundMusicPath", 
                                                     comment="背景音乐路径")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", 
                                                      server_default=func.now(), comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", 
                                                           server_default=func.now(), comment="最后修改时间")


class ProcessLog(Base):
    """处理日志实体"""
    __tablename__ = "video_mix_process_log"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="ProjectId", comment="所属项目ID")
    process_step: Mapped[int] = mapped_column(Integer, nullable=False, name="ProcessStep", 
                                         comment="处理步骤（1=视频上传, 2=视频分析, 3=场景检测, 4=AI分析, 5=音频生成, 6=视频合成）")
    status: Mapped[int] = mapped_column(Integer, nullable=False, name="Status", 
                                   comment="处理状态（0=进行中, 1=成功, 2=失败）")
    message: Mapped[str] = mapped_column(String(1000), nullable=True, name="Message", comment="处理信息")
    error_details: Mapped[str] = mapped_column(Text, nullable=True, name="ErrorDetails", comment="错误详情（如果有）")
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", 
                                                      server_default=func.now(), comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", 
                                                           server_default=func.now(), comment="最后修改时间")


class AIAnalysis(Base):
    """AI分析结果实体"""
    __tablename__ = "video_mix_ai_analysis"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False, name="Id", comment="主键ID")
    project_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, name="ProjectId", comment="所属项目ID")
    prompt_content: Mapped[str] = mapped_column(Text, nullable=True, name="PromptContent", comment="提示词内容")
    response_content: Mapped[str] = mapped_column(Text, nullable=True, name="ResponseContent", 
                                             comment="AI返回的完整响应")
    narration_script: Mapped[str] = mapped_column(Text, nullable=True, name="NarrationScript", comment="总体叙事脚本")
    status: Mapped[int] = mapped_column(Integer, nullable=False, name="Status", 
                                   comment="分析状态（0=进行中, 1=成功, 2=失败）", default=0)
    create_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="CreateDate", 
                                                      server_default=func.now(), comment="创建时间")
    last_modify_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, name="LastModifyDate", 
                                                           server_default=func.now(), comment="最后修改时间")


# 枚举类
class MixProjectStatus:
    """项目状态枚举"""
    INIT = 0  # 创建
    UPLOAD = 1  # 视频上传完成
    ANALYSE_VIDEO = 2  # 视频分析完成
    DETECT_SCENES = 3  # 场景检测完成
    AI_ANALYZE = 4  # AI分析完成
    AUDIO_GENERATE = 5  # 音频生成完成
    FINAL_VIDEO = 6  # 视频合成完成
    ERROR = 7  # 生成出现错误


class ProcessLogStatus:
    """处理状态枚举"""
    INIT = 0  # 进行中
    SUCCESS = 1  # 成功
    FAIL = 2  # 失败