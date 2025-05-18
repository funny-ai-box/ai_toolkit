"""
视频混剪路由
"""
import logging
from typing import List, Optional
from fastapi import (
    APIRouter, Depends, UploadFile, File, Form, HTTPException, 
    status, Request, BackgroundTasks, Body
)
from sqlalchemy.ext.asyncio import AsyncSession

# 导入核心依赖获取函数
from app.core.database.session import get_db
from app.core.config.settings import settings

from app.api.dependencies import (
    get_current_active_user_id,
    get_storage_service_from_state,
    get_chatai_service_from_state,
    get_speech_service_from_state,
    RateLimiter
)

# 导入核心DTO和异常
from app.core.dtos import ApiResponse, BaseIdRequestDto, PagedResultDto, BasePageRequestDto
from app.core.exceptions import NotFoundException, BusinessException

# 导入视频混剪模块的DTOs
from app.modules.tools.videomixer.dtos import (
    CreateProjectDto, CreateProjectResultDto,
    UploadVideoResultDto, UploadAudioResultDto,
    ProjectDto, ProjectListItemDto, 
    SourceVideoDto, SelectedSceneDto, SelectedSceneNarrationDto,
    FinalVideoDto, GenerateVideoResultDto,
    ProcessLogDto
)

# 导入服务和仓储
from app.modules.tools.videomixer.repositories import (
    MixProjectRepository,
    SourceVideoRepository,
    SceneFrameRepository,
    SelectedSceneRepository,
    SelectedSceneNarrationRepository,
    FinalVideoRepository,
    ProcessLogRepository,
    AIAnalysisRepository
)
from app.modules.tools.videomixer.services import (
    FileService,
    FileValidationService,
    VideoAnalysisService,
    AIAnalysisService,
    AudioService,
    VideoMixerService
)

# 导入模型
from app.modules.tools.videomixer.entities import MixProject

# 获取Logger
logger = logging.getLogger(__name__)

# 创建视频混剪API路由器
router = APIRouter(
    prefix="/videomixer",
    tags=["AI视频混剪"]
)

# 内部依赖项工厂：获取VideoMixerService实例
def _get_video_mixer_service(
    # 核心依赖
    db: AsyncSession = Depends(get_db),
    storage_service = Depends(get_storage_service_from_state),
    ai_service = Depends(get_chatai_service_from_state),
    speech_service = Depends(get_speech_service_from_state)
) -> VideoMixerService:
    """内部依赖项：创建并返回VideoMixerService及其内部所有依赖"""
    # 创建仓储
    project_repository = MixProjectRepository(db)
    source_video_repository = SourceVideoRepository(db)
    scene_frame_repository = SceneFrameRepository(db)
    selected_scene_narration_repository = SelectedSceneNarrationRepository(db)
    selected_scene_repository = SelectedSceneRepository(db, selected_scene_narration_repository)
    final_video_repository = FinalVideoRepository(db)
    process_log_repository = ProcessLogRepository(db)
    ai_analysis_repository = AIAnalysisRepository(db)
    
    # 创建服务
    file_service = FileService(storage_service)
    file_validation_service = FileValidationService()
    video_analysis_service = VideoAnalysisService()
    
    # 导入提示词服务
    from app.modules.base.prompts.services import PromptTemplateService
    from app.modules.base.prompts.repositories import PromptTemplateRepository
    
    # 创建提示词服务
    from app.core.redis.service import RedisService
    redis_service = RedisService()
    prompt_repository = PromptTemplateRepository(db)
    prompt_service = PromptTemplateService(db, prompt_repository, redis_service)
    
    # 创建AI分析服务
    ai_analysis_service = AIAnalysisService(ai_service, prompt_service)
    
    # 创建音频服务
    audio_service = AudioService(speech_service)
    
    # 创建视频混剪服务
    video_mixer_service = VideoMixerService(
        project_repository=project_repository,
        source_video_repository=source_video_repository,
        scene_frame_repository=scene_frame_repository,
        selected_scene_repository=selected_scene_repository,
        selected_scene_narration_repository=selected_scene_narration_repository,
        final_video_repository=final_video_repository,
        process_log_repository=process_log_repository,
        ai_analysis_repository=ai_analysis_repository,
        file_service=file_service,
        file_validation_service=file_validation_service,
        video_analysis_service=video_analysis_service,
        ai_analysis_service=ai_analysis_service,
        audio_service=audio_service
    )
    
    return video_mixer_service


# 获取文件验证服务
def _get_file_validation_service(
    db: AsyncSession = Depends(get_db)
) -> FileValidationService:
    """内部依赖项：创建并返回FileValidationService"""
    return FileValidationService()


# 创建项目
@router.post(
    "/projects/create",
    response_model=ApiResponse[CreateProjectResultDto],
    summary="创建混剪项目",
    description="创建一个新的视频混剪项目",
    dependencies=[
        Depends(get_current_active_user_id),
        Depends(RateLimiter(limit=5, period_seconds=300, limit_type="user"))
    ]
)
async def create_project(
    model: CreateProjectDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    video_mixer_service: VideoMixerService = Depends(_get_video_mixer_service)
):
    """
    创建混剪项目接口
    
    - **name**: 项目名称 (必需)
    - **description**: 项目描述 (可选)
    - **targetDuration**: 目标视频时长(秒) (必需，默认10秒)
    - **sceneKeywords**: 场景关键词 (必需)
    - **minRelevanceThreshold**: 最低相关度阈值 (必需，默认0.6)
    - **narrationStyle**: 解说词风格 (可选)
    - **backgroundMusicType**: 背景音乐类型 (必需，默认1)
    
    *需要有效的登录令牌 (Authorization header)*
    """
    # 创建项目
    project_id = await video_mixer_service.create_project_async(
        user_id,
        model.name or "",
        model.description or "",
        model.target_duration,
        model.scene_keywords or "",
        model.min_relevance_threshold,
        model.narration_style or "",
        model.background_music_type
    )
    
    # 返回结果
    result = CreateProjectResultDto(
        projectId=project_id,
        name=model.name,
        createDate=datetime.datetime.now()
    )
    
    return ApiResponse.success(data=result, message="项目创建成功")


# 上传源视频
@router.post(
    "/projects/uploadvideos",
    response_model=ApiResponse[UploadVideoResultDto],
    summary="上传源视频",
    description="上传源视频到指定项目",
    dependencies=[Depends(get_current_active_user_id)]
)
async def upload_video(
    video_file: UploadFile = File(...),
    project_id: int = Form(...),
    user_id: int = Depends(get_current_active_user_id),
    video_mixer_service: VideoMixerService = Depends(_get_video_mixer_service),
    file_validation_service: FileValidationService = Depends(_get_file_validation_service)
):
    """
    上传源视频接口
    
    - **videoFile**: 视频文件 (必需)
    - **projectId**: 项目ID (必需)
    
    *需要有效的登录令牌 (Authorization header)*
    """
    # 验证文件
    is_valid, error_message = file_validation_service.validate_video_file(video_file)
    if not is_valid:
        return ApiResponse.fail(message=error_message, code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
    
    # 获取项目信息
    try:
        project = await video_mixer_service.get_project_async(project_id)
        
        # 验证项目所有权
        if project.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限访问此项目"
            )
        
        # 检查项目是否已锁定
        if project.is_generate_lock != 0:
            return ApiResponse.fail(message="视频已开始生成，不能编辑项目")
    
    except NotFoundException as e:
        return ApiResponse.fail(message=str(e), code=status.HTTP_404_NOT_FOUND)
    
    # 上传视频
    video_id = await video_mixer_service.upload_source_video_async(project_id, video_file)
    
    # 返回结果
    result = UploadVideoResultDto(
        videoId=video_id,
        fileName=video_file.filename,
        fileSize=video_file.size,
        uploadedAt=datetime.datetime.now()
    )
    
    return ApiResponse.success(data=result, message="视频上传成功")


# 上传背景音乐
@router.post(
    "/projects/uploadmusic",
    response_model=ApiResponse[UploadAudioResultDto],
    summary="上传背景音乐",
    description="上传背景音乐到指定项目",
    dependencies=[Depends(get_current_active_user_id)]
)
async def upload_music(
    music_file: UploadFile = File(...),
    project_id: int = Form(...),
    user_id: int = Depends(get_current_active_user_id),
    video_mixer_service: VideoMixerService = Depends(_get_video_mixer_service),
    file_validation_service: FileValidationService = Depends(_get_file_validation_service)
):
    """
    上传背景音乐接口
    
    - **musicFile**: 音乐文件 (必需)
    - **projectId**: 项目ID (必需)
    
    *需要有效的登录令牌 (Authorization header)*
    """
    # 验证文件
    is_valid, error_message = file_validation_service.validate_audio_file(music_file)
    if not is_valid:
        return ApiResponse.fail(message=error_message, code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
    
    # 获取项目信息
    try:
        project = await video_mixer_service.get_project_async(project_id)
        
        # 验证项目所有权
        if project.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限访问此项目"
            )
        
        # 检查项目是否已锁定
        if project.is_generate_lock != 0:
            return ApiResponse.fail(message="视频已开始生成，不能编辑项目")
    
    except NotFoundException as e:
        return ApiResponse.fail(message=str(e), code=status.HTTP_404_NOT_FOUND)
    
    # 上传音乐
    success = await video_mixer_service.upload_background_music_async(project_id, music_file)
    
    # 返回结果
    result = UploadAudioResultDto(
        fileName=music_file.filename,
        fileSize=music_file.size,
        uploadedAt=datetime.datetime.now()
    )
    
    if success:
        return ApiResponse.success(data=result, message="背景音乐上传成功")
    else:
        return ApiResponse.fail(message="背景音乐上传失败")


# 分析视频
@router.post(
    "/projects/video/analyze",
    response_model=ApiResponse,
    summary="分析视频",
    description="分析指定项目的所有源视频并生成场景帧",
    dependencies=[Depends(get_current_active_user_id)]
)
async def analyze_videos(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    video_mixer_service: VideoMixerService = Depends(_get_video_mixer_service)
):
    """
    分析视频接口
    
    - **id**: 项目ID (必需)
    
    *需要有效的登录令牌 (Authorization header)*
    """
    # 获取项目信息
    try:
        project = await video_mixer_service.get_project_async(request.id)
        
        # 验证项目所有权
        if project.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限访问此项目"
            )
    
    except NotFoundException as e:
        return ApiResponse.fail(message=str(e), code=status.HTTP_404_NOT_FOUND)
    
    # 分析视频
    success = await video_mixer_service.analyze_videos_async(request.id)
    
    if success:
        return ApiResponse.success(message="视频分析成功")
    else:
        return ApiResponse.fail(message="视频分析失败")


# AI分析场景
@router.post(
    "/projects/video/aiscenes",
    response_model=ApiResponse,
    summary="AI分析场景",
    description="使用AI分析指定项目的场景帧并生成脚本",
    dependencies=[Depends(get_current_active_user_id)]
)
async def ai_analyze_scenes(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    video_mixer_service: VideoMixerService = Depends(_get_video_mixer_service)
):
    """
    AI分析场景接口
    
    - **id**: 项目ID (必需)
    
    *需要有效的登录令牌 (Authorization header)*
    """
    # 获取项目信息
    try:
        project = await video_mixer_service.get_project_async(request.id)
        
        # 验证项目所有权
        if project.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限访问此项目"
            )
    
    except NotFoundException as e:
        return ApiResponse.fail(message=str(e), code=status.HTTP_404_NOT_FOUND)
    
    # AI分析场景
    success = await video_mixer_service.ai_analyze_scenes_async(request.id)
    
    if success:
        return ApiResponse.success(message="AI分析场景成功")
    else:
        return ApiResponse.fail(message="AI分析场景失败")


# 生成解说音频
@router.post(
    "/projects/video/generate-narration",
    response_model=ApiResponse,
    summary="生成解说音频",
    description="为指定项目的选中场景生成解说音频",
    dependencies=[Depends(get_current_active_user_id)]
)
async def generate_narration_audio(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    video_mixer_service: VideoMixerService = Depends(_get_video_mixer_service)
):
    """
    生成解说音频接口
    
    - **id**: 项目ID (必需)
    
    *需要有效的登录令牌 (Authorization header)*
    """
    # 获取项目信息
    try:
        project = await video_mixer_service.get_project_async(request.id)
        
        # 验证项目所有权
        if project.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限访问此项目"
            )
    
    except NotFoundException as e:
        return ApiResponse.fail(message=str(e), code=status.HTTP_404_NOT_FOUND)
    
    # 生成解说音频
    success = await video_mixer_service.generate_narration_audio_async(request.id)
    
    if success:
        return ApiResponse.success(message="解说音频生成成功")
    else:
        return ApiResponse.fail(message="解说音频生成失败")


# 生成最终视频
@router.post(
    "/projects/video/mixfinal-video",
    response_model=ApiResponse[GenerateVideoResultDto],
    summary="生成最终视频",
    description="为指定项目生成最终合成视频",
    dependencies=[Depends(get_current_active_user_id)]
)
async def generate_final_video(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    video_mixer_service: VideoMixerService = Depends(_get_video_mixer_service)
):
    """
    生成最终视频接口
    
    - **id**: 项目ID (必需)
    
    *需要有效的登录令牌 (Authorization header)*
    """
    # 获取项目信息
    try:
        project = await video_mixer_service.get_project_async(request.id)
        
        # 验证项目所有权
        if project.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限访问此项目"
            )
    
    except NotFoundException as e:
        return ApiResponse.fail(message=str(e), code=status.HTTP_404_NOT_FOUND)
    
    # 生成最终视频
    video_id = await video_mixer_service.generate_final_video_async(request.id)
    
    # 获取最终视频信息
    final_video = await video_mixer_service.get_final_video_async(request.id)
    
    # 返回结果
    result = GenerateVideoResultDto(
        videoId=video_id,
        videoUrl=final_video.video_url or "",
        duration=final_video.duration,
        width=final_video.width,
        height=final_video.height,
        fileSize=final_video.file_size,
        generatedAt=final_video.create_date
    )
    
    return ApiResponse.success(data=result, message="最终视频生成成功")


# 开始生成视频
@router.post(
    "/projects/video/generate-video",
    response_model=ApiResponse[int],
    summary="开始生成视频",
    description="启动视频生成流程，将依次执行分析、AI场景选择、音频生成和视频合成",
    dependencies=[Depends(get_current_active_user_id)]
)
async def start_generate_video(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    video_mixer_service: VideoMixerService = Depends(_get_video_mixer_service)
):
    """
    开始生成视频接口
    
    - **id**: 项目ID (必需)
    
    *需要有效的登录令牌 (Authorization header)*
    """
    # 获取项目信息
    try:
        project = await video_mixer_service.get_project_async(request.id)
        
        # 验证项目所有权
        if project.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限访问此项目"
            )
        
        if project.is_generate_lock == 1:
            return ApiResponse.fail(message="视频生成已经执行过")
    
    except NotFoundException as e:
        return ApiResponse.fail(message=str(e), code=status.HTTP_404_NOT_FOUND)
    
    # 锁定项目开始生成
    await video_mixer_service.update_generate_lock_async(request.id, 1)
    
    return ApiResponse.success(data=request.id, message="视频开始生成中，请耐心等待")


# 获取项目信息
@router.post(
    "/projects/dtl",
    response_model=ApiResponse[ProjectDto],
    summary="获取项目详情",
    description="获取指定项目的详细信息，包括源视频、选中场景和最终视频",
    dependencies=[Depends(get_current_active_user_id)]
)
async def get_project(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    video_mixer_service: VideoMixerService = Depends(_get_video_mixer_service)
):
    """
    获取项目详情接口
    
    - **id**: 项目ID (必需)
    
    *需要有效的登录令牌 (Authorization header)*
    """
    # 获取项目信息
    try:
        project = await video_mixer_service.get_project_async(request.id)
        
        # 验证项目所有权
        if project.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限访问此项目"
            )
    
    except NotFoundException as e:
        return ApiResponse.fail(message=str(e), code=status.HTTP_404_NOT_FOUND)
    
    # 获取最终视频信息
    final_video = await video_mixer_service.get_final_video_async(request.id)
    
    # 获取源视频列表
    source_videos = await video_mixer_service.get_source_videos_by_project_id_async(request.id)
    
    # 获取选中场景列表
    selected_scenes = await video_mixer_service.get_selected_scenes_by_project_id_async(request.id)
    
    # 构建返回结果
    result = ProjectDto(
        id=project.id,
        name=project.name,
        description=project.description,
        targetDuration=project.target_duration,
        sceneKeywords=project.scene_keywords,
        minRelevanceThreshold=project.min_relevance_threshold,
        narrationStyle=project.narration_style,
        backgroundMusicType=project.background_music_type,
        backgroundMusicPath=project.background_music_path,
        status=project.status,
        isGenerateLock=project.is_generate_lock,
        isRunning=project.is_running,
        createDate=project.create_date,
        finalVideoUrl=project.final_video_url,
        errorMessage=project.error_message,
        sourceVideos=[],
        selectedScenes=[]
    )
    
    # 如果有最终视频，添加视频信息
    if final_video:
        result.finalVideo = FinalVideoDto(
            id=final_video.id,
            videoUrl=final_video.video_url or "",
            duration=final_video.duration,
            width=final_video.width,
            height=final_video.height,
            fileSize=final_video.file_size,
            createDate=final_video.create_date
        )
    
    # 添加源视频信息
    for source_video in source_videos:
        result.sourceVideos.append(SourceVideoDto(
            id=source_video.id,
            fileName=source_video.file_name or "",
            fileSize=source_video.file_size,
            duration=source_video.duration,
            width=source_video.width,
            height=source_video.height,
            frameRate=source_video.frame_rate,
            bitRate=source_video.bit_rate,
            status=source_video.status,
            createDate=source_video.create_date
        ))
    
    # 添加选中场景信息
    for selected_scene in selected_scenes:
        scene_dto = SelectedSceneDto(
            id=selected_scene.id,
            sourceVideoId=selected_scene.source_video_id,
            sequenceOrder=selected_scene.sequence_order,
            startTime=str(selected_scene.start_time),
            endTime=str(selected_scene.end_time),
            duration=selected_scene.duration,
            sceneDescription=selected_scene.scene_description,
            status=selected_scene.status,
            createDate=selected_scene.create_date,
            narrations=[]
        )
        
        # 添加解说词
        if hasattr(selected_scene, 'narrations') and selected_scene.narrations:
            for narration in selected_scene.narrations:
                scene_dto.narrations.append(SelectedSceneNarrationDto(
                    id=narration.id,
                    selectedSceneId=narration.selected_scene_id,
                    narration=narration.narration,
                    narrationAudioPath=narration.narration_audio_path or "",
                    duration=narration.duration,
                    createDate=narration.create_date
                ))
        
        result.selectedScenes.append(scene_dto)
    
    return ApiResponse.success(data=result)


# 获取用户项目列表
@router.post(
    "/projects/list",
    response_model=ApiResponse[PagedResultDto[ProjectListItemDto]],
    summary="获取项目列表",
    description="获取当前用户的所有视频混剪项目",
    dependencies=[Depends(get_current_active_user_id)]
)
async def get_user_projects(
    request: BasePageRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    video_mixer_service: VideoMixerService = Depends(_get_video_mixer_service)
):
    """
    获取项目列表接口
    
    - **pageIndex**: 页码 (必需, >= 1)
    - **pageSize**: 每页大小 (必需, >= 1)
    
    *需要有效的登录令牌 (Authorization header)*
    """
    # 获取用户项目列表
    projects, total_count = await video_mixer_service.get_user_projects_async(
        user_id, 
        request.page_index, 
        request.page_size
    )
    
    # 构建返回结果
    items = []
    for project in projects:
        items.append(ProjectListItemDto(
            id=project.id,
            name=project.name,
            description=project.description,
            targetDuration=project.target_duration,
            sceneKeywords=project.scene_keywords,
            minRelevanceThreshold=project.min_relevance_threshold,
            narrationStyle=project.narration_style,
            backgroundMusicType=project.background_music_type,
            backgroundMusicPath=project.background_music_path,
            status=project.status,
            createDate=project.create_date,
            finalVideoUrl=project.final_video_url,
            errorMessage=project.error_message
        ))
    
    # 构建分页结果
    result = PagedResultDto[ProjectListItemDto](
        items=items,
        totalCount=total_count,
        pageIndex=request.page_index,
        pageSize=request.page_size,
        totalPages=int((total_count + request.page_size - 1) // request.page_size)
    )
    
    return ApiResponse.success(data=result)


# 获取项目处理日志
@router.post(
    "/projects/dtl/logs",
    response_model=ApiResponse[List[ProcessLogDto]],
    summary="获取处理日志",
    description="获取指定项目的处理日志",
    dependencies=[Depends(get_current_active_user_id)]
)
async def get_project_logs(
    request: BaseIdRequestDto = Body(...),
    user_id: int = Depends(get_current_active_user_id),
    video_mixer_service: VideoMixerService = Depends(_get_video_mixer_service)
):
    """
    获取处理日志接口
    
    - **id**: 项目ID (必需)
    
    *需要有效的登录令牌 (Authorization header)*
    """
    # 获取项目信息
    try:
        project = await video_mixer_service.get_project_async(request.id)
        
        # 验证项目所有权
        if project.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限访问此项目"
            )
    
    except NotFoundException as e:
        return ApiResponse.fail(message=str(e), code=status.HTTP_404_NOT_FOUND)
    
    # 获取项目处理日志
    logs = await video_mixer_service.get_process_logs_by_project_id_async(request.id)
    
    # 构建返回结果
    result = []
    for log in logs:
        result.append(ProcessLogDto(
            id=log.id,
            processStep=log.process_step,
            status=log.status,
            message=log.message or "",
            createDate=log.create_date
        ))
    
    return ApiResponse.success(data=result)


# 导入所需的datetime模块，应该放在文件顶部，这里为了完整性再次添加
import datetime


# 定时任务路由：这部分路由用于后台任务，由调度器调用
# 注册后台任务服务
from app.core.job.decorators import job_endpoint
from app.modules.tools.videomixer.services.background_service import VideoProcessingService

# 定时处理待处理视频任务
@router.post(
    "/tasks/process-videos",
    response_model=ApiResponse,
    summary="处理待处理视频",
    description="定时任务：处理所有待处理的视频项目",
    include_in_schema=False  # 不在Swagger文档中显示
)
async def process_pending_videos(
    video_mixer_service: VideoMixerService = Depends(_get_video_mixer_service)
):
    """定时任务：处理待处理视频"""
    # 创建视频处理服务
    video_processing_service = VideoProcessingService(video_mixer_service)
    
    # 处理待处理视频
    await video_processing_service.process_pending_videos_async()
    
    return ApiResponse.success(message="处理待处理视频任务已执行")