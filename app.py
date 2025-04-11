import streamlit as st
import openai
import oss2
import time
import pandas as pd
from io import BytesIO
from dotenv import load_dotenv
import os
import base64

# 读取环境变量
load_dotenv()
ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID")
ACCESS_KEY_SECRET = os.getenv("ACCESS_KEY_SECRET")
BUCKET_NAME = os.getenv("BUCKET_NAME")
REGION = os.getenv("REGION")
API_KEY = os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen-vl-plus")
BASE_URL = os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
ENDPOINT = f"https://{BUCKET_NAME}.oss-{REGION}.aliyuncs.com"

# OSS 初始化
auth = oss2.Auth(ACCESS_KEY_ID, ACCESS_KEY_SECRET)
bucket = oss2.Bucket(auth, f"http://oss-{REGION}.aliyuncs.com", BUCKET_NAME)

# 夜间模式
def set_dark_mode(enabled):
    if enabled:
        st.markdown("""
            <style>
                body, .stApp {
                    background-color: #1E1E1E;
                    color: #FFFFFF;
                }
            </style>
        """, unsafe_allow_html=True)

# 缓存 OSS 内容
@st.cache_data(show_spinner=False)
def get_cached_oss_object(key):
    try:
        return bucket.get_object(key).read()
    except Exception:
        return None

# 上传文件至 OSS
def upload_file_to_oss(file, category="public"):
    file_name = f"{category}/{int(time.time())}_{file.name}"
    content_type_map = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".mp4": "video/mp4"
    }
    ext = os.path.splitext(file.name)[-1].lower()
    content_type = content_type_map.get(ext, "application/octet-stream")
    headers = {"Content-Type": content_type}
    try:
        bucket.put_object(file_name, file.getvalue(), headers=headers)
        return f"{ENDPOINT}/{file_name}"
    except Exception as e:
        st.error(f"❌ 上传失败: {e}")
        return None

# 调用千问 API
def query_qwen_api(user_input, image_url=None):
    client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL)
    messages = [{"role": "user", "content": []}]
    if user_input:
        messages[0]["content"].append({"type": "text", "text": user_input})
    if image_url:
        messages[0]["content"].append({"type": "image_url", "image_url": {"url": image_url}})
    try:
        completion = client.chat.completions.create(model=MODEL_NAME, messages=messages)
        return completion.choices[0].message.content
    except Exception as e:
        return f"❌ AI 解析失败: {str(e)}"

# 智能问答模块
def showLLMChatbot():
    st.title("📝 智能公考助手")
    st.caption("📢 输入你的公考问题，或上传试题截图，AI 帮你解答！")
    question_type = st.selectbox("🔍 选择问题类型", ["普通问题", "定义问题", "解释问题", "历史问题"])
    info = st.text_input("✍️ 请输入你的问题：")
    uploaded_file = st.file_uploader("📷 上传试题截图（支持 JPG/PNG）", type=["jpg", "png", "jpeg"])

    image_url = None
    if uploaded_file:
        st.image(uploaded_file, caption="已上传的试题截图", use_container_width=True)
        with st.spinner("🔄 正在上传图片..."):
            image_url = upload_file_to_oss(uploaded_file)
        if image_url:
            st.success("✅ 图片上传成功！")

    if st.button("🤖 获取答案"):
        if not info and not image_url:
            st.warning("⚠️ 请输入问题或上传试题图片！")
        else:
            st.write(f"📢 **你问:** {info if info else '（仅上传图片）'}")
            with st.spinner("🤖 AI 正在解析..."):
                answer = query_qwen_api(info, image_url)
            st.success("✅ AI 解析结果：")
            st.write(answer)

# 备考资料模块
def display_study_materials():
    st.title("📚 备考资料")
    st.caption("📢 提供各类备考资料，支持在线预览和下载！")
    categories = ["行测", "申论", "视频"]
    selected_categories = st.multiselect("选择备考资料类型", categories)

    for category in selected_categories:
        st.header(f"📂 {category} 类别")
        try:
            result = bucket.list_objects(prefix=category)
            if not result.object_list:
                st.warning(f"❗ 没有找到 {category} 类别的资料。")
                continue
            for obj in result.object_list:
                file_name = obj.key.split("/")[-1].lower()
                file_data = get_cached_oss_object(obj.key)
                file_url = f"{ENDPOINT}/{obj.key}"
                file_id = f"{category}_{file_name}"

                if file_name.endswith((".mp4", ".mov", ".avi", ".webm")):
                    st.markdown(f"🎬 **{file_name}**")
                    st.video(file_url)
                elif file_name.endswith(".pdf"):
                    st.markdown(f"📄 **{file_name}**")
                    if st.button(f"👁️ 点击预览 - {file_name}", key=file_id):
                        if file_data:
                            b64_pdf = base64.b64encode(file_data).decode()
                            st.markdown(f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="800px"></iframe>', unsafe_allow_html=True)
                elif file_name.endswith((".jpg", ".jpeg", ".png")):
                    st.image(BytesIO(file_data), caption=file_name, use_column_width=True)

                st.markdown(f"[📥 下载]({file_url})")
                st.markdown("---")
        except Exception as e:
            st.error(f"❌ 加载失败：{e}")

# 高分经验模块
def display_experience():
    st.title("🌟 高分经验")
    st.caption("📢 来自高分考生的分享资料，支持在线预览！")
    try:
        result = bucket.list_objects(prefix="高分经验/")
        if not result.object_list:
            st.warning("😢 暂无高分经验资料。")
            return
        for obj in result.object_list:
            file_name = obj.key.split("/")[-1]
            file_data = get_cached_oss_object(obj.key)
            file_url = f"{ENDPOINT}/{obj.key}"
            file_id = f"经验_{file_name}"

            st.markdown(f"📄 **{file_name}**")
            if file_name.endswith(".pdf"):
                if st.button(f"👁️ 点击预览 - {file_name}", key=file_id):
                    if file_data:
                        b64_pdf = base64.b64encode(file_data).decode()
                        st.markdown(f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="800px"></iframe>', unsafe_allow_html=True)

            st.markdown(f"[📥 下载]({file_url})")
            st.markdown("---")
    except Exception as e:
        st.error(f"❌ 加载失败：{e}")

# 政策资讯模块
def display_policy_news():
    st.title("📰 政策资讯")
    st.caption("📢 最新公务员政策、公告信息一网打尽")
    csv_key = "政策咨询/civilpass_data.csv"
    try:
        csv_data = get_cached_oss_object(csv_key)
        if not csv_data:
            st.error("❌ 无法加载政策资讯。")
            return
        df = pd.read_csv(BytesIO(csv_data), encoding="utf-8")
        df['date'] = pd.to_datetime(df['date'], errors='coerce')

        with st.expander("🔍 筛选功能"):
            col1, col2 = st.columns(2)
            start_date = col1.date_input("📅 起始日期", pd.to_datetime("2024-01-01"))
            end_date = col2.date_input("📅 截止日期", pd.to_datetime("today"))
            keyword = st.text_input("🔎 输入关键词")

        filtered_df = df.copy()
        if not df['date'].isna().all():
            filtered_df = filtered_df[(df['date'] >= pd.to_datetime(start_date)) & (df['date'] <= pd.to_datetime(end_date))]
        if keyword:
            filtered_df = filtered_df[df['title'].str.contains(keyword, na=False)]

        if filtered_df.empty:
            st.warning("😢 没有找到相关政策资讯。")
        else:
            for _, row in filtered_df.sort_values(by="date", ascending=False).head(30).iterrows():
                st.markdown(f"### 🔗 [{row['title']}]({row['url']})")
                st.markdown(f"📅 日期: {row['date'].date() if pd.notna(row['date']) else '无'} | 🏛 来源: {row['source']}")
                st.markdown("---")
    except Exception as e:
        st.error(f"❌ 加载失败：{str(e)}")

# 考试日历模块
def display_exam_calendar():
    st.title("📅 考试日历")
    st.markdown("### ⚠️ <span style='color:red;'>考试时间仅供参考，请以官方公布为准！</span>", unsafe_allow_html=True)
    try:
        result = bucket.list_objects(prefix="考试日历/")
        month_mapping = {
            "一月": 1, "二月": 2, "三月": 3, "四月": 4, "五月": 5,
            "六月": 6, "七月": 7, "八月": 8, "九月": 9, "十月": 10,
            "十一月": 11, "十二月": 12
        }
        def extract_month_index(name):
            for k, v in month_mapping.items():
                if name.startswith(k):
                    return v
            return 999
        sorted_images = sorted(
            [obj for obj in result.object_list if obj.key.lower().endswith((".jpg", ".png", ".jpeg"))],
            key=lambda obj: extract_month_index(obj.key.split("/")[-1])
        )
        for obj in sorted_images:
            image_data = get_cached_oss_object(obj.key)
            if image_data:
                st.image(BytesIO(image_data), caption=obj.key.split("/")[-1], use_container_width=True)
                st.markdown("---")
    except Exception as e:
        st.error(f"❌ 加载考试日历失败：{str(e)}")

# 管理员上传模块
def admin_upload_center():
    st.title("📤 管理员上传中心")
    st.caption("仅管理员可上传各类备考资料至 OSS。")
    upload_category = st.selectbox("📁 选择上传目录", ["行测", "申论", "视频", "高分经验", "政策咨询", "考试日历"])
    files = st.file_uploader("📎 选择文件上传", accept_multiple_files=True)
    if st.button("🚀 开始上传") and files:
        with st.spinner("📤 正在上传中..."):
            for file in files:
                upload_file_to_oss(file, category=upload_category)
        st.success("✅ 所有文件上传完成！")

# 主程序
def main():
    dark_mode = st.sidebar.toggle("🌙 夜间模式")
    set_dark_mode(dark_mode)

    st.sidebar.title("🎯 公考助手")
    menu = st.sidebar.radio("📌 选择功能", ["智能问答", "考试日历", "备考资料", "政策资讯", "高分经验", "上传资料（管理员）"])
    if menu == "智能问答":
        showLLMChatbot()
    elif menu == "考试日历":
        display_exam_calendar()
    elif menu == "备考资料":
        display_study_materials()
    elif menu == "政策资讯":
        display_policy_news()
    elif menu == "高分经验":
        display_experience()
    elif menu == "上传资料（管理员）":
        admin_upload_center()

if __name__ == '__main__':
    main()
