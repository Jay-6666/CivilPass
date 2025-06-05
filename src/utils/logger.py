import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

def setup_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    """配置日志记录器"""
    # 创建日志目录
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器
    log_file = os.path.join(
        log_dir, 
        f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
    )
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

# 创建应用日志记录器
app_logger = setup_logger("civilpass")

def log_error(error: Exception, context: dict = None):
    """记录错误信息"""
    app_logger.error(
        f"Error: {str(error)}, Context: {context if context else 'No context provided'}", 
        exc_info=True
    )

def log_info(message: str, context: dict = None):
    """记录信息"""
    app_logger.info(
        f"{message} - Context: {context if context else 'No context provided'}"
    )

def log_warning(message: str, context: dict = None):
    """记录警告信息"""
    app_logger.warning(
        f"{message} - Context: {context if context else 'No context provided'}"
    )

def log_debug(message: str, context: dict = None):
    """记录调试信息"""
    app_logger.debug(
        f"{message} - Context: {context if context else 'No context provided'}"
    ) 