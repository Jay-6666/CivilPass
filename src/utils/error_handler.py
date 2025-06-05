import streamlit as st
from functools import wraps
import traceback
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AppError(Exception):
    """自定义应用程序异常基类"""
    def __init__(self, message, error_type="error"):
        self.message = message
        self.error_type = error_type
        super().__init__(self.message)

class DataLoadError(AppError):
    """数据加载错误"""
    pass

class AuthenticationError(AppError):
    """认证错误"""
    pass

class OSSOpertaionError(AppError):
    """OSS操作错误"""
    pass

def error_handler(func):
    """错误处理装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DataLoadError as e:
            logger.error(f"数据加载错误: {str(e)}")
            st.error(f"❌ 数据加载失败: {str(e)}")
        except AuthenticationError as e:
            logger.error(f"认证错误: {str(e)}")
            st.error(f"🔒 认证失败: {str(e)}")
        except OSSOpertaionError as e:
            logger.error(f"OSS操作错误: {str(e)}")
            st.error(f"📁 文件操作失败: {str(e)}")
        except Exception as e:
            logger.error(f"未预期的错误: {str(e)}\n{traceback.format_exc()}")
            st.error(f"❌ 发生错误: {str(e)}")
        return None
    return wrapper

def show_error_message(error_message: str, error_type: str = "error"):
    """统一的错误消息展示"""
    if error_type == "error":
        st.error(f"❌ {error_message}")
    elif error_type == "warning":
        st.warning(f"⚠️ {error_message}")
    elif error_type == "info":
        st.info(f"ℹ️ {error_message}")
    
    logger.error(error_message) 