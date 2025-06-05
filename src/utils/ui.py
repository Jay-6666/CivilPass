import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

def is_mobile():
    """通过浏览器 User-Agent 自动检测移动端设备"""
    try:
        ctx = get_script_run_ctx()
        if ctx is None:
            return False
        user_agent = ctx.request.headers.get("User-Agent", "").lower()
        return any(keyword in user_agent for keyword in ["mobi", "android", "iphone"])
    except Exception:
        return False

def set_dark_mode(dark: bool):
    """设置夜间模式"""
    if dark:
        st.markdown(
            """
            <style>
                body, .stApp {
                    background-color: #1E1F29;
                    color: #F0F0F0;
                }

                .css-1d391kg, .css-1v0mbdj, .css-1cypcdb {
                    background-color: #2B2D3C !important;
                    color: #F0F0F0 !important;
                    border-radius: 10px;
                    padding: 10px;
                    transition: all 0.3s ease-in-out;
                }

                .stButton>button {
                    background-color: #3C82F6 !important;
                    color: white !important;
                    border: none;
                    padding: 0.5rem 1rem;
                    border-radius: 5px;
                    transition: all 0.2s ease-in-out;
                }

                .stButton>button:hover {
                    background-color: #559DFF !important;
                    transform: scale(1.03);
                }

                .stTextInput>div>div>input, .stSelectbox>div>div>div {
                    background-color: #3C3F51 !important;
                    color: #FFFFFF !important;
                    border-radius: 5px;
                    border: 1px solid #5A5D78;
                    transition: all 0.2s ease-in-out;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

def chat_message(message, is_user=True):
    """消息气泡 UI"""
    avatar = "🧑‍💻" if is_user else "🤖"
    alignment = "flex-end" if is_user else "flex-start"
    bg_color = "#0E76FD" if is_user else "#2E2E2E"
    text_color = "#FFFFFF" if is_user else "#DDDDDD"

    st.markdown(
        f"""
        <div style='display: flex; justify-content: {alignment}; margin: 10px 0;'>
            <div style='background-color: {bg_color}; color: {text_color}; padding: 10px 15px;
                        border-radius: 12px; max-width: 70%;'>
                <strong>{avatar}</strong> {message}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    ) 