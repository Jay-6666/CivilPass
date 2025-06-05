import hashlib
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import streamlit as st

def generate_cache_key(*args: Any, **kwargs: Any) -> str:
    """生成缓存键"""
    key = str(args) + str(sorted(kwargs.items()))
    return hashlib.md5(key.encode()).hexdigest()

def format_date(date_str: str, output_format: str = "%Y年%m月%d日") -> str:
    """格式化日期"""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime(output_format)
    except ValueError:
        return date_str

def validate_file_extension(filename: str, allowed_extensions: tuple) -> bool:
    """验证文件扩展名"""
    return filename.lower().endswith(allowed_extensions)

def format_file_size(size_in_bytes: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.2f} TB"

def sanitize_filename(filename: str) -> str:
    """清理文件名"""
    # 移除非法字符
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # 确保文件名不超过255字符
    name, ext = os.path.splitext(filename)
    if len(filename) > 255:
        return name[:255-len(ext)] + ext
    return filename

def get_date_range(days: int = 7) -> tuple:
    """获取日期范围"""
    today = datetime.now()
    future = today + timedelta(days=days)
    return today.strftime("%Y-%m-%d"), future.strftime("%Y-%m-%d")

def chunk_text(text: str, chunk_size: int = 1000) -> List[str]:
    """文本分块"""
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

def create_success_message(message: str, duration: int = 3):
    """创建成功消息"""
    st.success(message)
    time.sleep(duration)
    st.empty()

def validate_date_format(date_str: str) -> bool:
    """验证日期格式"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def extract_keywords(text: str, max_keywords: int = 5) -> List[str]:
    """提取关键词"""
    # 这里可以使用jieba等分词工具实现
    # 示例实现
    words = text.split()
    return words[:max_keywords]

def format_time_ago(timestamp: datetime) -> str:
    """格式化时间间隔"""
    now = datetime.now()
    diff = now - timestamp
    
    if diff.days > 365:
        return f"{diff.days // 365}年前"
    elif diff.days > 30:
        return f"{diff.days // 30}个月前"
    elif diff.days > 0:
        return f"{diff.days}天前"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600}小时前"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60}分钟前"
    else:
        return "刚刚" 