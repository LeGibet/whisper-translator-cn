import os
import asyncio
import argparse
from pathlib import Path
from typing import Optional
from .logger import setup_logger, handle_error, console
from .core import process_file, CoreError, FileTypeError, FileFormatError
from .config import init_config, CONFIG_ENV_VAR, ConfigurationError

def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="Whisper Translator CN - 视频字幕生成与翻译工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # init 命令
    init_parser = subparsers.add_parser(
        "init", 
        help="初始化配置文件",
        description="创建默认配置文件模板，需要手动编辑填入必要的配置信息。"
    )
    init_parser.add_argument(
        "-p", "--path", 
        help="指定配置文件路径，默认在用户配置目录"
    )
    
    # run 命令
    run_parser = subparsers.add_parser(
        "run", 
        help="运行字幕处理",
        description="处理视频/音频文件生成字幕，或翻译已有字幕文件。"
    )
    run_parser.add_argument(
        "input",
        help="输入文件路径（支持视频、音频、字幕文件）"
    )
    run_parser.add_argument(
        "-o", "--output",
        help="输出文件路径，默认在output目录"
    )
    run_parser.add_argument(
        "-m", "--mode",
        choices=["all", "subtitle", "translate"],
        default="all",
        help="处理模式：all(完整处理) subtitle(仅生成字幕) translate(仅翻译)"
    )
    run_parser.add_argument(
        "-t", "--trans-mode",
        choices=["single", "batch"],
        default="single",
        help="翻译模式：single(逐条翻译) batch(批量翻译)"
    )
    run_parser.add_argument(
        "-b", "--batch-size",
        type=int,
        default=50,
        help="批量翻译时的批次大小"
    )
    run_parser.add_argument(
        "-c", "--chinese-only",
        action="store_true",
        help="仅输出中文字幕，不包含原文"
    )
    run_parser.add_argument(
        "-l", "--log-file",
        action="store_true",
        help="启用日志文件，记录详细处理信息"
    )
    run_parser.add_argument(
        "-f", "--format",
        choices=["auto", "srt", "lrcx"],
        default="auto",
        help="输出格式：auto(自动) srt(字幕) lrcx(歌词)"
    )
    
    return parser

def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = create_parser()
    args = parser.parse_args()
    
    # 如果没有指定命令，显示帮助
    if not args.command:
        parser.print_help()
        raise SystemExit(1)
        
    return args

async def handle_init(config_path: Optional[str]) -> None:
    """处理init命令"""
    try:
        path = Path(config_path) if config_path else None
        created_path = init_config(path)
        console.print(f"[success]✓[/success] 配置文件已创建在: {created_path}")
        
        if CONFIG_ENV_VAR in os.environ:
            console.print(
                f"[warning]注意：环境变量 {CONFIG_ENV_VAR} 已设置为 "
                f"{os.environ[CONFIG_ENV_VAR]}，这可能会覆盖新创建的配置文件[/warning]"
            )
    except Exception as e:
        handle_error(ConfigurationError(f"初始化配置失败: {str(e)}"))
        raise SystemExit(1)

async def handle_run(args: argparse.Namespace) -> None:
    """处理run命令"""
    try:
        # 设置日志
        setup_logger(log_to_file=False)
        if args.log_file:
            log_path = setup_logger(log_to_file=True)
            console.print(f"[info]详细日志将写入: {log_path}[/info]")
        
        # 处理文件
        await process_file(
            input_path=args.input,
            output=args.output,
            mode=args.mode,
            translation_mode=args.trans_mode,
            batch_size=args.batch_size,
            chinese_only=args.chinese_only,
            format=args.format
        )
            
    except (CoreError, FileTypeError, FileFormatError, ConfigurationError) as e:
        handle_error(e)
        raise SystemExit(1)
    except Exception as e:
        handle_error(CoreError(f"处理失败: {str(e)}"))
        raise SystemExit(1)

async def main() -> None:
    """主函数"""
    args = parse_args()
    
    try:
        if args.command == "init":
            await handle_init(args.path)
        elif args.command == "run":
            await handle_run(args)
    except SystemExit as e:
        raise e
    except Exception as e:
        handle_error(e)
        raise SystemExit(1)

def run() -> None:
    """命令行入口点"""
    try:
        # 设置环境变量，避免某些库的警告
        os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
        asyncio.run(main())
    except SystemExit as e:
        raise e
    except KeyboardInterrupt:
        console.print("\n[warning]用户中断执行[/warning]")
        raise SystemExit(130)
    except Exception as e:
        handle_error(e)
        raise SystemExit(1)

if __name__ == "__main__":
    run()
