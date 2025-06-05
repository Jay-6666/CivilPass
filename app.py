import streamlit as st
from src.modules.chatbot import show_chatbot
from src.modules.calendar import display_calendar
from src.modules.materials import display_materials
from src.modules.news import display_news
from src.modules.experience import display_experience
from src.modules.admin import admin_upload_center
from src.utils.ui import set_dark_mode

def main():
    """主函数"""
    # 夜间模式
    dark_mode = st.sidebar.toggle("🌙 夜间模式")
    set_dark_mode(dark_mode)

    # 侧边栏导航
    st.sidebar.title("🎯 公考助手")
    menu = st.sidebar.radio(
        "📌 功能导航",
        ["智能问答", "考试日历", "备考资料", "政策资讯", "高分经验", "上传资料（管理员）"]
    )

    # 根据选择显示不同模块
    if menu == "智能问答":
        show_chatbot()
    elif menu == "考试日历":
        display_calendar()
    elif menu == "备考资料":
        display_materials()
    elif menu == "政策资讯":
        display_news()
    elif menu == "高分经验":
        display_experience()
    elif menu == "上传资料（管理员）":
        admin_upload_center()

if __name__ == "__main__":
    main()
