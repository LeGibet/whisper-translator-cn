from rich.console import Console
from rich.theme import Theme
from rich.logging import RichHandler
import rich.errors
from config import ConfigurationError
import logging
from datetime import datetime
from pathlib import Path
import functools

# 自定义主题
custom_theme = Theme({
    'info': 'cyan',
    'warning': 'yellow',
    'error': 'red',
    'success': 'green',
    'progress': 'blue'
})

console = Console(theme=custom_theme)
logger = None

class DetailedLogHandler(logging.FileHandler):
    """详细日志处理器，记录所有输出"""
    def __init__(self, filename):
        super().__init__(filename, encoding='utf-8')
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
    def emit(self, record):
        try:
            msg = self.format(record)
            self.stream.write(msg + '\n')
            self.flush()
        except Exception:
            self.handleError(record)

def setup_logger(log_to_file=False):
    """设置并返回logger"""
    global logger
    
    logger = logging.getLogger('subtitle_translator')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    
    # 控制台处理器 - 只显示简洁信息
    console_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_time=False,
        show_path=False,
        markup=True
    )
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    # 控制台只显示非详细日志
    console_handler.addFilter(lambda record: not hasattr(record, 'detailed_only'))
    logger.addHandler(console_handler)
    
    log_file = None
    # 如果启用文件日志，添加详细日志处理器
    if log_to_file:
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f'translate_{timestamp}.log'
        
        file_handler = DetailedLogHandler(log_file)
        logger.addHandler(file_handler)
    
    return log_file

def log_detail(message):
    """记录详细日志，仅当启用日志文件时写入"""
    if logger:
        record = logging.LogRecord(
            name=logger.name,
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg=message,
            args=(),
            exc_info=None
        )
        record.detailed_only = True
        logger.handle(record)

def api_call(func):
    """API调用装饰器"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            logger.error(f"API调用失败: {str(e)}")
            raise
    return wrapper

def handle_error(e: Exception):
    """错误处理函数"""
    error_msg = str(e)
    if isinstance(e, FileNotFoundError):
        error_msg = f"找不到文件: {error_msg}"
    elif isinstance(e, ConfigurationError):
        error_msg = f"配置错误: {error_msg}"
    elif isinstance(e, rich.errors.LiveError):
        error_msg = "显示错误: 不能同时显示多个进度条"
    
    # 确保 logger 已初始化
    if logger is not None:
        logger.error(error_msg)
    
    # 总是使用 console 显示错误，因为它是独立的
    console.print(f"[error]✗ {error_msg}[/error]")

def get_logger():
    """获取或初始化 logger"""
    global logger
    if logger is None:
        logger = setup_logger()
    return logger
