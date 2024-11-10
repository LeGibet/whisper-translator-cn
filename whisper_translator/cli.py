import os
import asyncio
import argparse
import sys
from pathlib import Path
from .logger import logger, console, setup_logger
from .core import process_file
from .config import init_config, ConfigurationError

def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="视频字幕生成与翻译工具")
    
    parser.add_argument("input", help="输入文件路径（视频、音频或字幕文件）")
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

async def main() -> None:
    """主函数"""
    args = parse_args()
    
    # 首先设置日志
    if args.log_file:
        log_file = setup_logger(log_to_file=True)
        if log_file:
            console.print(f"[info]日志文件: {log_file}[/info]")
            logger.debug("日志系统已初始化")
    
    try:
        await process_file(
            input_path=args.input,
            output=args.output,
            mode=args.mode,
            translation_mode=args.trans_mode,
            batch_size=args.batch_size,
            chinese_only=args.chinese_only,
            format=args.format
        )
            
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)

def run() -> None:
    """命令行入口点"""
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[warning]程序被用户中断[/warning]")
        sys.exit(1)
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)

def init() -> None:
    """初始化配置文件"""
    config_path = Path("config.yaml")
    try:
        init_config(config_path)
        console.print(f"[success]✓[/success] 配置文件已创建: {config_path}")
    except Exception as e:
        logger.error(f"初始化配置失败: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    run()
