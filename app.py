import streamlit as st
import openai
import oss2
import time
import pandas as pd
from io import BytesIO
from dotenv import load_dotenv
import os

# ========== 加载环境变量 ==========
load_dotenv()

# 配置信息
ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID")
ACCESS_KEY_SECRET = os.getenv("ACCESS_KEY_SECRET")
BUCKET_NAME = os.getenv("BUCKET_NAME")
REGION = os.getenv("REGION")
API_KEY = os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen-vl-plus")
BASE_URL = os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

ENDPOINT = f"https://{BUCKET_NAME}.oss-{REGION}.aliyuncs.com"

# ========== 配置阿里云 OSS ==========
auth = oss2.Auth(ACCESS_KEY_ID, ACCESS_KEY_SECRET)
bucket = oss2.Bucket(auth, f"http://oss-{REGION}.aliyuncs.com", BUCKET_NAME)


# ========== 上传图片到 OSS（优化版）==========
def upload_image_to_oss(image_file):
    file_name = f"public/{int(time.time())}_{image_file.name}"

    # 设置正确的Content-Type
    content_type = "image/jpeg"
    if image_file.name.lower().endswith(".png"):
        content_type = "image/png"
    elif image_file.name.lower().endswith(".jpg") or image_file.name.lower().endswith(".jpeg"):
        content_type = "image/jpeg"

    headers = {'Content-Type': content_type}
    bucket.put_object(file_name, image_file.getvalue(), headers=headers)
    oss_url = f"{ENDPOINT}/{file_name}"
    return oss_url


# ========== 调用大模型 ==========
def query_qwen_api(user_input, image_url=None):
    client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL)
    messages = [{"role": "user", "content": []}]

    if user_input:
        messages[0]["content"].append({"type": "text", "text": user_input})
    if image_url:
        messages[0]["content"].append({"type": "image_url", "image_url": {"url": image_url}})

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"❌ AI 解析失败: {str(e)}"


# ========== 智能问答模块 ==========
def showLLMChatbot():
    st.title("📝 智能公考助手")
    st.caption("📢 输入你的公考问题，或上传试题截图，AI 帮你解答！")

    question_type = st.selectbox("🔍 选择问题类型",
                                 ["普通问题", "定义问题", "解释问题", "历史问题"])
    info = st.text_input("✍️ 请输入你的问题：")
    uploaded_file = st.file_uploader("📷 上传试题截图（支持 JPG/PNG）",
                                     type=["jpg", "png", "jpeg"])

    image_url = None
    if uploaded_file:
        st.image(uploaded_file, caption="已上传的试题截图", use_container_width=True)
        with st.spinner("🔄 正在上传图片..."):
            image_url = upload_image_to_oss(uploaded_file)
        st.success("✅ 图片上传成功！")

    if st.button("🤖 获取答案"):
        if not info and not image_url:
            st.warning("⚠️ 请输入问题或上传试题图片！")
        else:
            st.write(f"📢 **你问:** {info if info else '（仅上传图片）'}")
            answer = query_qwen_api(info, image_url)
            st.success("✅ AI 解析结果：")
            st.write(answer)


# ========== 备考资料模块（优化版）==========
def display_study_materials():
    st.title("📚 备考资料")
    st.caption("📢 提供各类备考资料，支持在线预览和下载！")

    categories = ["行测", "申论", "视频"]
    selected_categories = st.multiselect("选择备考资料类型", categories)

    if selected_categories:
        for category in selected_categories:
            st.header(f"📂 {category} 类别")
            result = bucket.list_objects(prefix=category)

            if result.object_list:
                for obj in result.object_list:
                    file_url = f"{ENDPOINT}/{obj.key}"
                    file_name = obj.key.split("/")[-1].lower()

                    # 视频文件处理
                    if file_name.endswith((".mp4", ".mov", ".avi", ".webm")):
                        st.markdown(f"🎬 **{obj.key.split('/')[-1]}**")
                        st.video(file_url)
                        st.markdown(f"[📥 下载视频]({file_url})")

                    # PDF文件处理
                    elif file_name.endswith(".pdf"):
                        st.markdown(f"📄 **{obj.key.split('/')[-1]}**")
                        preview_url = f"https://docs.google.com/gview?url={file_url}&embedded=true"
                        st.markdown(f'<iframe src="{preview_url}" width="100%" height="800"></iframe>',
                                    unsafe_allow_html=True)
                        st.markdown(f"[📥 下载PDF]({file_url})")

                    # 图片文件处理
                    elif file_name.endswith((".jpg", ".jpeg", ".png")):
                        st.markdown(f"🖼️ **{obj.key.split('/')[-1]}**")
                        st.image(file_url, use_column_width=True)
                        st.markdown(f"[📥 下载图片]({file_url})")

                    # 其他文件类型
                    else:
                        st.markdown(f"📁 **{obj.key.split('/')[-1]}**")
                        st.markdown(f"[📥 下载文件]({file_url})")

                    st.markdown("---")
            else:
                st.warning(f"没有找到 {category} 类别的资料。")
    else:
        st.warning("⚠️ 请先选择至少一个备考资料类别。")


# ========== 高分经验模块（优化版）==========
def display_experience():
    st.title("🌟 高分经验")
    st.caption("📢 来自高分考生的分享资料，支持在线预览！")

    result = bucket.list_objects(prefix="高分经验/")
    if result.object_list:
        for obj in result.object_list:
            file_url = f"{ENDPOINT}/{obj.key}"
            file_name = obj.key.split("/")[-1].lower()

            if file_name.endswith(".pdf"):
                st.markdown(f"📄 **{obj.key.split('/')[-1]}**")
                preview_url = f"https://docs.google.com/gview?url={file_url}&embedded=true"
                st.markdown(f'<iframe src="{preview_url}" width="100%" height="800"></iframe>',
                            unsafe_allow_html=True)
                st.markdown(f"[📥 下载PDF]({file_url})")
                st.markdown("---")
            else:
                st.markdown(f"📁 **{obj.key.split('/')[-1]}**")
                st.markdown(f"[📥 下载文件]({file_url})")
                st.markdown("---")
    else:
        st.warning("😢 暂无高分经验资料。")


# ========== 政策资讯模块 ==========
def display_policy_news():
    st.title("📰 政策资讯")
    st.caption("📢 最新公务员政策、公告信息一网打尽")

    csv_key = "政策咨询/civilpass_data.csv"
    try:
        csv_data = bucket.get_object(csv_key)
        df = pd.read_csv(BytesIO(csv_data.read()), encoding="utf-8")

        # 数据清洗
        if df.shape[1] == 1:
            df.columns = ['url']
            df['title'] = [f"政策资讯第{i + 1}条" for i in range(len(df))]
            df['source'] = '未知来源'
            df['date'] = '无'
        elif not {"title", "source", "date", "url"}.issubset(df.columns):
            st.error("❌ CSV 文件缺少必要列：title, source, date, url")
            return

        df['date'] = pd.to_datetime(df['date'], errors='coerce')

        # 筛选功能
        with st.expander("🔍 筛选功能"):
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("📅 起始日期", pd.to_datetime("2024-01-01"))
            with col2:
                end_date = st.date_input("📅 截止日期", pd.to_datetime("today"))

            keyword = st.text_input("🔎 输入关键词（支持标题/来源搜索）")

        # 数据过滤
        filtered_df = df.copy()
        if not df['date'].isna().all():
            filtered_df = filtered_df[(filtered_df['date'] >= pd.to_datetime(start_date)) &
                                      (filtered_df['date'] <= pd.to_datetime(end_date))]
        if keyword:
            keyword_lower = keyword.lower()
            filtered_df = filtered_df[
                filtered_df['title'].str.lower().str.contains(keyword_lower, na=False) |
                filtered_df['source'].str.lower().str.contains(keyword_lower, na=False)
                ]

        # 展示结果
        if not filtered_df.empty:
            for _, row in filtered_df.sort_values(by="date", ascending=False).head(30).iterrows():
                st.markdown(f"### 🔗 [{row['title']}]({row['url']})")
                st.markdown(
                    f"📅 日期: {row['date'].date() if pd.notna(row['date']) else '无'} | 🏛 来源: {row['source']}")
                st.markdown("---")
        else:
            st.warning("😢 没有找到匹配的政策资讯，请调整关键词或日期范围。")

    except oss2.exceptions.NoSuchKey:
        st.error("❌ 未找到政策资讯文件 civilpass_data.csv")
    except Exception as e:
        st.error(f"❌ 加载政策资讯失败：{str(e)}")


# ========== 考试日历模块 ==========
def display_exam_calendar():
    st.title("📅 考试日历")
    st.markdown("### ⚠️ <span style='color:red;font-weight:bold;'>考试时间仅供参考，请以官方公布为准！</span>",
                unsafe_allow_html=True)

    try:
        result = bucket.list_objects(prefix="考试日历/")
        if result.object_list:
            # 中文月份映射表
            month_mapping = {
                "一月": 1, "二月": 2, "三月": 3, "四月": 4,
                "五月": 5, "六月": 6, "七月": 7, "八月": 8,
                "九月": 9, "十月": 10, "十一月": 11, "十二月": 12
            }

            # 排序逻辑
            def extract_month_index(filename):
                name = filename.split("/")[-1]
                for month_name, idx in month_mapping.items():
                    if name.startswith(month_name):
                        return idx
                return 999

            sorted_images = sorted(
                [obj for obj in result.object_list if obj.key.lower().endswith((".jpg", ".png", ".jpeg"))],
                key=lambda obj: extract_month_index(obj.key)
            )

            # 展示图片
            for obj in sorted_images:
                img_url = f"{ENDPOINT}/{obj.key}"
                st.image(img_url, caption=obj.key.split("/")[-1], use_container_width=True)
                st.markdown("---")
        else:
            st.warning("😢 OSS 中没有考试日历图片。")
    except Exception as e:
        st.error(f"❌ 读取考试日历失败：{str(e)}")


# ========== 主函数 ==========
def main():
    st.sidebar.title("🎯 公考助手")
    menu = st.sidebar.radio("📌 选择功能",
                            ["智能问答", "考试日历", "备考资料", "政策资讯", "高分经验"])

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


# ========== 启动应用 ==========
if __name__ == '__main__':
    main()