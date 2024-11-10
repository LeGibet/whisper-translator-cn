import logging
import sys
import re
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.theme import Theme
from typing import Optional

# 自定义主题
console = Console(theme=Theme({
    'info': 'cyan',
    'warning': 'yellow',
    'error': 'red bold',
    'success': 'green',
    'progress': 'blue'
}))

def strip_ansi(text: str) -> str:
    """移除ANSI转义码"""
    return re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])').sub('', text)

class StreamToLogger:
    """将标准输出重定向到logger的简单封装"""
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level

    def write(self, msg):
        if msg.strip():
            self.logger.log(self.level, msg.rstrip())

    def flush(self):
        pass

# 创建全局logger实例
logger = logging.getLogger('whisper_translator')
logger.setLevel(logging.DEBUG)

# 默认的控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(console_handler)

def setup_logger(log_to_file: bool = False) -> Optional[Path]:
    """配置logger
    
    Args:
        log_to_file: 是否启用文件日志
        
    Returns:
        Optional[Path]: 日志文件路径(如果启用了文件日志)
    """
    if not log_to_file:
        return None
        
    # 创建日志目录
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # 创建日志文件
    log_file = log_dir / f'translate_{datetime.now():%Y%m%d_%H%M%S}.log'
    
    # 文件处理器 - 清除颜色代码
    file_handler = logging.FileHandler(str(log_file), encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    
    # 自定义格式化以移除颜色代码
    original_format = file_handler.format
    file_handler.format = lambda record: strip_ansi(original_format(record))
    
    logger.addHandler(file_handler)
    
    # 重定向标准输出到logger
    sys.stdout = StreamToLogger(logger, logging.INFO)
    sys.stderr = StreamToLogger(logger, logging.ERROR)
    
    return log_file

def get_logger() -> logging.Logger:
    """获取logger实例"""
    return logger

# 导出常用日志方法
debug = logger.debug
info = logger.info
warning = logger.warning
error = logger.error

def log_subprocess(process_output: bytes, level=logging.DEBUG):
    """记录子进程输出
    
    Args:
        process_output: 子进程输出的字节数据
        level: 日志级别
    """
    if process_output:
        try:
            msg = process_output.decode().strip()
            if msg:
                logger.log(level, msg)
        except UnicodeDecodeError:
            logger.warning("无法解码子进程输出")

def handle_error(e: Exception) -> None:
    """统一错误处理
    
    Args:
        e: 异常对象
    """
    error_msg = f"错误: {str(e)}"
    logger.error(error_msg)
    console.print(f"[error]✗ {error_msg}[/error]")
