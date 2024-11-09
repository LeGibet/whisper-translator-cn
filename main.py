import os
import asyncio
import argparse
from pathlib import Path
from typing import List, Optional, Tuple
from logger import logger, console, setup_logger, handle_error
from config import get_config, get_whisper_config
from subtitle import parse_srt, translate_subtitles, save_srt, save_lrcx, parse_lrcx
from whisper_process import process_media

SUPPORTED_FORMATS = {
    'video': {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v',
              '.ts', '.mts', '.m2ts', '.rmvb', '.rm'},
    'audio': {'.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg', '.wma'},
    'subtitle': {'.srt'},
    'lyric': {'.lrc', '.lrcx'}
}

def get_file_type(input_path: Path) -> dict[str, bool]:
    """获取文件类型"""
    suffix = input_path.suffix.lower()
    return {
        'is_video': suffix in SUPPORTED_FORMATS['video'],
        'is_audio': suffix in SUPPORTED_FORMATS['audio'],
        'is_subtitle': suffix in SUPPORTED_FORMATS['subtitle'],
        'is_lyric': suffix in SUPPORTED_FORMATS['lyric']
    }

def validate_mode(args, file_types: dict) -> None:
    """验证处理模式是否合法"""
    if file_types['is_subtitle'] or file_types['is_lyric']:
        if args.mode == 'all':
            args.mode = 'translate'
            console.print("[info]检测到字幕/歌词文件，自动切换为翻译模式[/info]")
            return

    error_conditions = {
        'subtitle_only': not any([file_types['is_video'], file_types['is_audio']]) and args.mode == 'subtitle',
        'subtitle_to_subtitle': file_types['is_subtitle'] and args.mode == 'subtitle',
        'media_translate': any([file_types['is_video'], file_types['is_audio']]) and args.mode == 'translate'
    }

    error_messages = {
        'subtitle_only': "仅视频或音频文件支持生成字幕模式",
        'subtitle_to_subtitle': "字幕文件不支持生成字幕模式",
        'media_translate': "视频或音频文件不支持仅翻译模式"
    }

    for condition, message in error_messages.items():
        if error_conditions[condition]:
            raise ValueError(message)

def get_output_path(input_path: Path, args, is_audio: bool) -> Path:
    """获取输出路径"""
    if args.output:
        return Path(args.output)
    
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)
    
    # 根据format参数决定输出格式
    if args.format == "auto":
        suffix = '.lrcx' if is_audio else '.srt'
    else:
        suffix = '.lrcx' if args.format == "lrcx" else '.srt'
        
    return output_dir / f"{input_path.stem}_translated{suffix}"

async def process_subtitles(srt_path: Path, output_path: Path, args, file_types: dict) -> None:
    """处理字幕翻译"""
    try:
        # 解析字幕文件
        entries = parse_lrcx(str(srt_path)) if file_types['is_lyric'] else parse_srt(str(srt_path))
        
        # 翻译字幕
        console.print("[progress]▶ 翻译字幕[/progress]")
        translated_entries = await translate_subtitles(
            entries,
            translation_mode=args.trans_mode,
            batch_size=args.batch_size
        )
        
        # 根据输出格式选择保存方式
        is_lrcx_output = output_path.suffix.lower() == '.lrcx'
        if is_lrcx_output:
            save_lrcx(translated_entries, str(output_path), args.chinese_only)
        else:
            save_srt(translated_entries, str(output_path), args.chinese_only)
            
        console.print(f"[success]✓[/success] 翻译字幕已保存到 {output_path}")
        
    except Exception as e:
        logger.error(f"处理字幕失败: {str(e)}")
        raise

async def process_media_file(input_path: Path, output_dir: Path) -> Tuple[Path, str]:
    """处理媒体文件"""
    try:
        console.print("[progress]▶ 处理媒体[/progress]")
        whisper_config = get_whisper_config(get_config())
        engine_name = "Whisper.cpp" if whisper_config["engine"] == "whisper-cpp" else "Faster Whisper"
        console.print(f"[info]使用 {engine_name} 生成字幕...[/info]")
        
        srt_path, detected_lang = await process_media(input_path, output_dir, whisper_config)
        console.print(f"[info]检测到语言: {detected_lang}[/info]")
        console.print(f"[success]✓[/success] 字幕生成完成，已保存到 {srt_path}")
        
        return srt_path
        
    except Exception as e:
        logger.error(f"处理媒体失败: {str(e)}")
        raise

def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="视频字幕生成与翻译工具")
    parser.add_argument("input", help="输入文件路径（视频或字幕文件）")
    parser.add_argument("-o", "--output", help="输出文件路径")
    parser.add_argument("-m", "--mode", choices=["all", "subtitle", "translate"], 
                       default="all", help="处理模式")
    parser.add_argument("-t", "--trans-mode", choices=["single", "batch"],
                       default="single", help="翻译模式")
    parser.add_argument("-b", "--batch-size", type=int, default=50,
                       help="批量翻译时的批次大小")
    parser.add_argument("-c", "--chinese-only", action="store_true",
                       help="仅输出中文字幕")
    parser.add_argument("-l", "--log-file", action="store_true",
                       help="启用日志文件")
    parser.add_argument("-f", "--format", choices=["auto", "srt", "lrcx"],
                       default="auto", help="输出格式，auto表示视频输出srt，音频输出lrcx")
    return parser.parse_args()

async def main() -> None:
    """主函数"""
    # 首先初始化基础 logger
    setup_logger(log_to_file=False)
    
    try:
        args = parse_args()
        # 如果需要文件日志，重新设置 logger
        if args.log_file:
            log_path = setup_logger(log_to_file=True)
            console.print(f"[info]日志文件: {log_path}[/info]")
        
        input_path = Path(args.input).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")
        
        file_types = get_file_type(input_path)
        validate_mode(args, file_types)
        output_path = get_output_path(input_path, args, file_types['is_audio'])

        if file_types['is_video'] or file_types['is_audio']:
            srt_path = await process_media_file(input_path, output_path.parent)
            if args.mode == 'subtitle':
                return
        else:
            srt_path = input_path

        if args.mode in ['all', 'translate']:
            await process_subtitles(srt_path, output_path, args, file_types)
            
    except Exception as e:
        handle_error(e)

if __name__ == "__main__":
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    asyncio.run(main())
