import os
from pathlib import Path
from typing import Optional, Tuple, Dict, Set
from .logger import get_logger, console
from .config import get_config, get_whisper_config
from .subtitle import (
    parse_srt, translate_subtitles, save_srt, save_lrcx, 
    parse_lrcx, SubtitleEntry
)
from .whisper_process import process_media, WhisperProcessError
from .translate import TranslationError

class CoreError(Exception):
    """核心处理错误"""
    pass

class FileTypeError(Exception):
    """文件类型错误"""
    pass

class FileFormatError(Exception):
    """文件格式错误"""
    pass

class FileProcessor:
    """文件处理类"""
    FORMATS = {
        'video': {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', 
                 '.m4v', '.ts', '.mts', '.m2ts', '.rmvb', '.rm'},
        'audio': {'.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg', '.wma'},
        'subtitle': {'.srt'},
        'lyric': {'.lrc', '.lrcx'}
    }

    @classmethod
    def get_file_type(cls, input_path: Path) -> Dict[str, bool]:
        """获取文件类型"""
        suffix = input_path.suffix.lower()
        return {
            type_name: suffix in formats
            for type_name, formats in cls.FORMATS.items()
        }

    @classmethod
    def validate_input_file(cls, input_path: Path) -> None:
        """验证输入文件"""
        if not input_path.is_file():
            raise FileNotFoundError(f"输入文件不存在或不是文件: {input_path}")
            
        file_types = cls.get_file_type(input_path)
        if not any(file_types.values()):
            supported = [ext for formats in cls.FORMATS.values() for ext in formats]
            raise FileTypeError(f"不支持的文件格式: {input_path.suffix}\n支持的格式: {', '.join(supported)}")

    @classmethod
    def get_output_path(cls, input_path: Path, output: Optional[str] = None, 
                       format: str = "auto", is_audio: bool = False) -> Path:
        """获取输出路径"""
        if output:
            return Path(output)
        
        output_dir = Path('output')
        output_dir.mkdir(exist_ok=True)
        suffix = '.lrcx' if (is_audio or format == "lrcx") else '.srt'
        return output_dir / f"{input_path.stem}_translated{suffix}"

async def process_subtitles(srt_path: Path, output_path: Path, 
                          translation_mode: str = "single",
                          batch_size: int = 50,
                          chinese_only: bool = False) -> None:
    """处理字幕翻译"""
    try:
        file_types = FileProcessor.get_file_type(srt_path)
        entries = parse_lrcx(str(srt_path)) if file_types['lyric'] else parse_srt(str(srt_path))
        
        if not entries:
            raise CoreError(f"未找到有效的字幕条目: {srt_path}")
        
        console.print("[progress]▶ 翻译字幕[/progress]")
        translated_entries = await translate_subtitles(
            entries,
            translation_mode=translation_mode,
            batch_size=batch_size
        )
        
        is_lrcx_output = output_path.suffix.lower() == '.lrcx'
        save_func = save_lrcx if is_lrcx_output else save_srt
        save_func(translated_entries, str(output_path), chinese_only)
        console.print(f"[success]✓[/success] 翻译字幕已保存到 {output_path}")
        
    except Exception as e:
        raise CoreError(str(e))

async def process_media_file(input_path: Path, output_dir: Optional[Path] = None) -> Path:
    """处理媒体文件，生成字幕"""
    try:
        console.print("[progress]▶ 处理媒体[/progress]")
        whisper_config = get_whisper_config(get_config())
        engine_name = "Whisper.cpp" if whisper_config["engine"] == "whisper-cpp" else "Faster Whisper"
        console.print(f"[info]使用 {engine_name} 生成字幕...[/info]")
        
        if not output_dir:
            output_dir = Path('output')
            output_dir.mkdir(exist_ok=True)
            
        srt_path, detected_lang = await process_media(input_path, output_dir, whisper_config)
        console.print(f"[success]✓[/success] 字幕生成完成，已保存到 {srt_path}")
        return srt_path
        
    except Exception as e:
        raise CoreError(str(e))

async def process_file(input_path: str, output: Optional[str] = None,
                      mode: str = "all", translation_mode: str = "single",
                      batch_size: int = 50, chinese_only: bool = False,
                      format: str = "auto") -> None:
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
    """
    try:
        input_path = Path(input_path).resolve()
        FileProcessor.validate_input_file(input_path)
        
        file_types = FileProcessor.get_file_type(input_path)
        output_path = FileProcessor.get_output_path(input_path, output, format, file_types['audio'])

        if file_types['video'] or file_types['audio']:
            srt_path = await process_media_file(input_path, output_path.parent)
            if mode == 'subtitle':
                return
        else:
            srt_path = input_path

        if mode in ['all', 'translate']:
            await process_subtitles(
                srt_path, 
                output_path, 
                translation_mode=translation_mode,
                batch_size=batch_size,
                chinese_only=chinese_only
            )
            
    except Exception as e:
        raise CoreError(str(e))
