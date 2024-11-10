import os
from pathlib import Path
from typing import Optional, Dict, Union
from .logger import logger, console
from .config import get_config, get_whisper_config
from .subtitle import (
    parse_srt, translate_subtitles, save_subtitle,
    parse_lrcx
)
from .whisper_process import process_media

# 支持的文件格式
SUPPORTED_FORMATS = {
    'video': {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', 
              '.m4v', '.ts', '.mts', '.m2ts', '.rmvb', '.rm'},
    'audio': {'.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg', '.wma'},
    'subtitle': {'.srt'},
    'lyric': {'.lrc', '.lrcx'}
}

def get_file_type(file_path: Path) -> Dict[str, bool]:
    """获取文件类型"""
    suffix = file_path.suffix.lower()
    return {
        'is_video': suffix in SUPPORTED_FORMATS['video'],
        'is_audio': suffix in SUPPORTED_FORMATS['audio'],
        'is_subtitle': suffix in SUPPORTED_FORMATS['subtitle'],
        'is_lyric': suffix in SUPPORTED_FORMATS['lyric']
    }

def validate_mode(file_types: Dict[str, bool], mode: str) -> str:
    """验证处理模式
    
    Args:
        file_types: 文件类型字典
        mode: 处理模式
        
    Returns:
        str: 验证后的模式
        
    Raises:
        ValueError: 当模式与文件类型不兼容时
    """
    # 字幕文件自动切换为翻译模式
    if (file_types['is_subtitle'] or file_types['is_lyric']) and mode == 'all':
        console.print("[info]检测到字幕/歌词文件，自动切换为翻译模式[/info]")
        return 'translate'

    # 验证模式合法性
    if mode == 'subtitle':
        if not any([file_types['is_video'], file_types['is_audio']]):
            raise ValueError("仅视频或音频文件支持生成字幕模式")
        if file_types['is_subtitle']:
            raise ValueError("字幕文件不支持生成字幕模式")
            
    if mode == 'translate':
        if any([file_types['is_video'], file_types['is_audio']]):
            raise ValueError("视频或音频文件不支持仅翻译模式")
    
    return mode

def get_output_path(input_path: Path, output: Optional[str] = None,
                   format: str = "auto", is_audio: bool = False) -> Path:
    """获取输出路径"""
    if output:
        return Path(output)
    
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)
    
    # 根据format参数决定输出格式
    suffix = '.lrcx' if (format == "lrcx" or 
                        (format == "auto" and is_audio)) else '.srt'
    return output_dir / f"{input_path.stem}_translated{suffix}"

async def process_subtitles(
    srt_path: Path,
    output_path: Path,
    translation_mode: str = "single",
    batch_size: int = 50,
    chinese_only: bool = False,
    file_types: Optional[Dict[str, bool]] = None
) -> None:
    """处理字幕翻译"""
    # 如果未提供file_types，重新获取
    if file_types is None:
        file_types = get_file_type(srt_path)
        
    # 解析字幕文件
    entries = (parse_lrcx(str(srt_path)) if file_types['is_lyric'] 
              else parse_srt(str(srt_path)))
    
    # 翻译字幕
    console.print("[progress]▶ 翻译字幕[/progress]")
    translated_entries = await translate_subtitles(
        entries,
        translation_mode=translation_mode,
        batch_size=batch_size
    )
    
    # 保存翻译结果
    save_subtitle(
        translated_entries,
        str(output_path),
        chinese_only=chinese_only,
        format_type=output_path.suffix.lstrip('.')
    )
    console.print(f"[success]✓[/success] 翻译字幕已保存到 {output_path}")

async def process_media_file(input_path: Path, output_dir: Path) -> Path:
    """处理媒体文件，生成字幕"""
    console.print("[progress]▶ 处理媒体[/progress]")
    
    # 获取Whisper配置
    whisper_config = get_whisper_config(get_config())
    engine_name = ("Whisper.cpp" if whisper_config["engine"] == "whisper-cpp" 
                  else "Faster Whisper")
    console.print(f"[info]使用 {engine_name} 生成字幕...[/info]")
    
    # 处理媒体文件
    srt_path, detected_lang = await process_media(input_path, output_dir, whisper_config)
    console.print(f"[info]检测到语言: {detected_lang}[/info]")
    console.print(f"[success]✓[/success] 字幕生成完成，已保存到 {srt_path}")
    
    return srt_path

async def process_file(
    input_path: Union[str, Path],
    output: Optional[str] = None,
    mode: str = "all",
    translation_mode: str = "single",
    batch_size: int = 50,
    chinese_only: bool = False,
    format: str = "auto"
) -> None:
    """
    处理单个文件（主入口函数）
    
    Args:
        input_path: 输入文件路径
        output: 输出文件路径
        mode: 处理模式 ("all", "subtitle", "translate")
        translation_mode: 翻译模式 ("single" or "batch")
        batch_size: 批量翻译时的批次大小
        chinese_only: 是否仅输出中文字幕
        format: 输出格式 ("auto", "srt", "lrcx")
        
    Raises:
        FileNotFoundError: 输入文件不存在
        ValueError: 参数错误
    """
    # 标准化路径
    input_path = Path(input_path).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")
        
    # 获取文件类型并验证模式
    file_types = get_file_type(input_path)
    mode = validate_mode(file_types, mode)
    
    # 获取输出路径
    output_path = get_output_path(input_path, output, format, file_types['is_audio'])

    try:
        # 处理媒体文件
        if file_types['is_video'] or file_types['is_audio']:
            srt_path = await process_media_file(input_path, output_path.parent)
            if mode == 'subtitle':
                return
        else:
            srt_path = input_path

        # 翻译处理
        if mode in ['all', 'translate']:
            await process_subtitles(
                srt_path,
                output_path,
                translation_mode=translation_mode,
                batch_size=batch_size,
                chinese_only=chinese_only,
                file_types=file_types
            )
            
    except Exception as e:
        logger.error(str(e))
        raise
