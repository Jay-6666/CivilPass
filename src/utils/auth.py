import streamlit as st
from src.config.settings import ADMIN_PASSWORD

def check_admin_auth(password: str) -> bool:
    """检查管理员密码"""
    return password == ADMIN_PASSWORD

def require_admin_auth():
    """要求管理员认证装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            password = st.text_input("🔐 输入管理员密码", type="password")
            if check_admin_auth(password):
                return func(*args, **kwargs)
            else:
                st.warning("🔒 密码错误，无法访问上传功能")
                return None
        return wrapper
    return decorator 