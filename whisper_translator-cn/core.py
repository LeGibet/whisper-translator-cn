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

class FileTypeError(CoreError):
    """文件类型错误"""
    pass

class FileFormatError(CoreError):
    """文件格式错误"""
    pass

class FileProcessor:
    """文件处理类"""
    SUPPORTED_FORMATS: Dict[str, Set[str]] = {
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
            'is_video': suffix in cls.SUPPORTED_FORMATS['video'],
            'is_audio': suffix in cls.SUPPORTED_FORMATS['audio'],
            'is_subtitle': suffix in cls.SUPPORTED_FORMATS['subtitle'],
            'is_lyric': suffix in cls.SUPPORTED_FORMATS['lyric']
        }

    @classmethod
    def validate_input_file(cls, input_path: Path) -> None:
        """验证输入文件"""
        if not input_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")
            
        if not input_path.is_file():
            raise FileTypeError(f"输入路径不是文件: {input_path}")
            
        file_types = cls.get_file_type(input_path)
        if not any(file_types.values()):
            supported = [ext for formats in cls.SUPPORTED_FORMATS.values() for ext in formats]
            raise FileFormatError(
                f"不支持的文件格式: {input_path.suffix}\n"
                f"支持的格式: {', '.join(supported)}"
            )

    @classmethod
    def get_output_path(cls, input_path: Path, output: Optional[str] = None, 
                       format: str = "auto", is_audio: bool = False) -> Path:
        """获取输出路径"""
        if output:
            return Path(output)
        
        output_dir = Path('output')
        output_dir.mkdir(exist_ok=True)
        
        if format == "auto":
            suffix = '.lrcx' if is_audio else '.srt'
        else:
            suffix = '.lrcx' if format == "lrcx" else '.srt'
            
        return output_dir / f"{input_path.stem}_translated{suffix}"

async def process_subtitles(srt_path: Path, output_path: Path, 
                          translation_mode: str = "single",
                          batch_size: int = 50,
                          chinese_only: bool = False) -> None:
    """处理字幕翻译"""
    logger = get_logger()
    try:
        file_types = FileProcessor.get_file_type(srt_path)
        # 解析字幕文件
        entries = parse_lrcx(str(srt_path)) if file_types['is_lyric'] else parse_srt(str(srt_path))
        
        # 确保解析结果不为空
        if not entries:
            raise CoreError(f"未找到有效的字幕条目: {srt_path}")
        
        # 翻译字幕
        console.print("[progress]▶ 翻译字幕[/progress]")
        translated_entries = await translate_subtitles(
            entries,
            translation_mode=translation_mode,
            batch_size=batch_size
        )
        
        # 根据输出格式选择保存方式
        is_lrcx_output = output_path.suffix.lower() == '.lrcx'
        if is_lrcx_output:
            save_lrcx(translated_entries, str(output_path), chinese_only)
        else:
            save_srt(translated_entries, str(output_path), chinese_only)
            
        console.print(f"[success]✓[/success] 翻译字幕已保存到 {output_path}")
        
    except (TranslationError, FileFormatError) as e:
        raise CoreError(f"处理字幕失败: {str(e)}")
    except Exception as e:
        raise CoreError(f"处理字幕时发生错误: {str(e)}")

async def process_media_file(input_path: Path, output_dir: Optional[Path] = None) -> Path:
    """处理媒体文件，生成字幕"""
    logger = get_logger()
    try:
        console.print("[progress]▶ 处理媒体[/progress]")
        whisper_config = get_whisper_config(get_config())
        engine_name = "Whisper.cpp" if whisper_config["engine"] == "whisper-cpp" else "Faster Whisper"
        console.print(f"[info]使用 {engine_name} 生成字幕...[/info]")
        
        if output_dir is None:
            output_dir = Path('output')
            output_dir.mkdir(exist_ok=True)
            
        srt_path, detected_lang = await process_media(input_path, output_dir, whisper_config)
        console.print(f"[success]✓[/success] 字幕生成完成，已保存到 {srt_path}")
        
        return srt_path
        
    except WhisperProcessError as e:
        raise CoreError(f"处理媒体失败: {str(e)}")
    except Exception as e:
        raise CoreError(f"处理媒体时发生错误: {str(e)}")

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
    
    Raises:
        CoreError: 处理过程中的错误
        FileNotFoundError: 输入文件不存在
        FileTypeError: 输入路径类型错误
        FileFormatError: 不支持的文件格式
    """
    logger = get_logger()
    
    try:
        input_path = Path(input_path).resolve()
        FileProcessor.validate_input_file(input_path)
        
        file_types = FileProcessor.get_file_type(input_path)
        output_path = FileProcessor.get_output_path(input_path, output, format, file_types['is_audio'])

        if file_types['is_video'] or file_types['is_audio']:
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
        # 转换所有未知异常为CoreError
        if not isinstance(e, (CoreError, FileNotFoundError, FileTypeError, FileFormatError)):
            e = CoreError(str(e))
        raise e
