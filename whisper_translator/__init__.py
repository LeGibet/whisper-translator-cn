"""
Whisper Translator CN - 一个视频字幕生成与翻译工具
"""

from .core import process_file, process_media_file, process_subtitles
from .config import get_config, get_whisper_config, init_config
from .subtitle import parse_srt, parse_lrcx, save_srt, save_lrcx
from .translate import translate_single, translate_batch
from .whisper_process import process_media
from .logger import setup_logger, console, logger

__version__ = "0.1.0"
__all__ = [
    'process_file',
    'process_media_file',
    'process_subtitles',
    'get_config',
    'get_whisper_config',
    'init_config',
    'parse_srt',
    'parse_lrcx',
    'save_srt',
    'save_lrcx',
    'translate_single',
    'translate_batch',
    'process_media',
    'setup_logger',
    'console',
    'logger'
]
