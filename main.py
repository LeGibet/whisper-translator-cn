import os
import asyncio
import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple
from logger import logger, console, setup_logger
from config import get_config, get_whisper_config
from subtitle import parse_srt, parse_lrcx, translate_subtitles, save_subtitle
from whisper_process import process_media

# 支持的文件格式
SUPPORTED_FORMATS = {
    'video': {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', 
              '.m4v', '.ts', '.mts', '.m2ts', '.rmvb', '.rm'},
    'audio': {'.mp3', '.wav', '.aac', '.m4a', '.flac', '.ogg', '.wma'},
    'subtitle': {'.srt'},
    'lyric': {'.lrc', '.lrcx'}
}

def get_file_type(file_path: Path) -> dict[str, bool]:
    """获取文件类型"""
    suffix = file_path.suffix.lower()
    return {
        'is_video': suffix in SUPPORTED_FORMATS['video'],
        'is_audio': suffix in SUPPORTED_FORMATS['audio'],
        'is_subtitle': suffix in SUPPORTED_FORMATS['subtitle'],
        'is_lyric': suffix in SUPPORTED_FORMATS['lyric']
    }

def validate_mode(args: argparse.Namespace, file_types: dict) -> None:
    """验证处理模式"""
    # 字幕文件自动切换为翻译模式
    if (file_types['is_subtitle'] or file_types['is_lyric']) and args.mode == 'all':
        args.mode = 'translate'
        console.print("[info]检测到字幕/歌词文件，自动切换为翻译模式[/info]")
        return

    # 验证模式合法性
    if args.mode == 'subtitle':
        if not any([file_types['is_video'], file_types['is_audio']]):
            raise ValueError("仅视频或音频文件支持生成字幕模式")
        if file_types['is_subtitle']:
            raise ValueError("字幕文件不支持生成字幕模式")
            
    if args.mode == 'translate':
        if any([file_types['is_video'], file_types['is_audio']]):
            raise ValueError("视频或音频文件不支持仅翻译模式")

def get_output_path(input_path: Path, args: argparse.Namespace, is_audio: bool) -> Path:
    """获取输出路径"""
    if args.output:
        return Path(args.output)
    
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)
    
    # 根据format参数决定输出格式
    suffix = '.lrcx' if (args.format == "lrcx" or 
                        (args.format == "auto" and is_audio)) else '.srt'
    return output_dir / f"{input_path.stem}_translated{suffix}"

async def process_subtitles(
    srt_path: Path,
    output_path: Path,
    args: argparse.Namespace,
    file_types: dict
) -> None:
    """处理字幕翻译"""
    # 解析字幕文件
    entries = (parse_lrcx(str(srt_path)) if file_types['is_lyric'] 
              else parse_srt(str(srt_path)))
    
    # 翻译字幕
    console.print("[progress]▶ 翻译字幕[/progress]")
    translated_entries = await translate_subtitles(
        entries,
        translation_mode=args.trans_mode,
        batch_size=args.batch_size
    )
    
    # 保存翻译结果
    save_subtitle(
        translated_entries,
        str(output_path),
        chinese_only=args.chinese_only,
        format_type=output_path.suffix.lstrip('.')
    )
    console.print(f"[success]✓[/success] 翻译字幕已保存到 {output_path}")

async def process_media_file(input_path: Path, output_dir: Path) -> Path:
    """处理媒体文件"""
    console.print("[progress]▶ 处理媒体[/progress]")
    
    # 获取Whisper配置
    whisper_config = get_whisper_config(get_config())
    engine_name = ("Whisper.cpp" if whisper_config["engine"] == "whisper-cpp" 
                  else "Faster Whisper")
    console.print(f"[info]使用 {engine_name} 生成字幕...[/info]")
    
    # 处理媒体文件
    srt_path, detected_lang = await process_media(
        input_path,
        output_dir,
        whisper_config
    )
    console.print(f"[info]检测到语言: {detected_lang}[/info]")
    console.print(f"[success]✓[/success] 字幕生成完成，已保存到 {srt_path}")
    
    return srt_path

def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="视频字幕生成与翻译工具")
    
    parser.add_argument("input", help="输入文件路径（视频或字幕文件）")
    parser.add_argument("-o", "--output", help="输出文件路径")
    parser.add_argument(
        "-m", "--mode",
        choices=["all", "subtitle", "translate"],
        default="all",
        help="处理模式"
    )
    parser.add_argument(
        "-t", "--trans-mode",
        choices=["single", "batch"],
        default="batch",
        help="翻译模式"
    )
    parser.add_argument(
        "-b", "--batch-size",
        type=int,
        default=50,
        help="批量翻译时的批次大小"
    )
    parser.add_argument(
        "-c", "--chinese-only",
        action="store_true",
        help="仅输出中文字幕"
    )
    parser.add_argument(
        "-l", "--log-file",
        action="store_true",
        help="启用日志文件"
    )
    parser.add_argument(
        "-f", "--format",
        choices=["auto", "srt", "lrcx"],
        default="auto",
        help="输出格式，auto表示视频输出srt，音频输出lrcx"
    )
    
    return parser.parse_args()

def run() -> None:
    """程序入口"""
    args = parse_args()
    
    # 首先设置日志
    if args.log_file:
        log_file = setup_logger(log_to_file=True)
        if log_file:
            console.print(f"[info]日志文件: {log_file}[/info]")
            logger.debug("日志系统已初始化")
    
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        console.print("\n[warning]程序被用户中断[/warning]")
        sys.exit(1)
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)

async def main(args: argparse.Namespace) -> None:
    """主函数"""
    try:
        # 验证输入文件
        input_path = Path(args.input).resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")
        
        # 处理文件
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
        logger.error(str(e))
        raise

if __name__ == "__main__":
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    run()
