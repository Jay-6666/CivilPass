import streamlit as st
import openai
import oss2
import time
import pandas as pd
from io import BytesIO
from dotenv import load_dotenv
import os
import base64
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 环境变量读取
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
def set_dark_mode(dark: bool):
    if dark:
        st.markdown("""
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

                .stRadio > div {
                    background-color: #2B2D3C !important;
                    padding: 0.5rem;
                    border-radius: 8px;
                }

                .css-qrbaxs, .css-1xarl3l {
                    color: #F0F0F0 !important;
                }

                ::-webkit-scrollbar {
                    width: 8px;
                }

                ::-webkit-scrollbar-track {
                    background: #1E1F29;
                }

                ::-webkit-scrollbar-thumb {
                    background: #4B4D62;
                    border-radius: 4px;
                }

                /* 动画过渡 */
                .block-container {
                    animation: fadeSlideIn 0.5s ease-in-out;
                }

                @keyframes fadeSlideIn {
                    0% {
                        opacity: 0;
                        transform: translateY(20px);
                    }
                    100% {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }

            </style>
        """, unsafe_allow_html=True)

# 消息气泡 UI
def chat_message(message, is_user=True):
    avatar = "🧑‍💻" if is_user else "🤖"
    alignment = "flex-end" if is_user else "flex-start"
    bg_color = "#0E76FD" if is_user else "#2E2E2E"
    text_color = "#FFFFFF" if is_user else "#DDDDDD"

    st.markdown(f"""
        <div style='display: flex; justify-content: {alignment}; margin: 10px 0;'>
            <div style='background-color: {bg_color}; color: {text_color}; padding: 10px 15px;
                        border-radius: 12px; max-width: 70%;'>
                <strong>{avatar}</strong> {message}
            </div>
        </div>
    """, unsafe_allow_html=True)

# 缓存 OSS 内容
@st.cache_data(show_spinner=False)
def get_cached_oss_object(key):
    try:
        return bucket.get_object(key).read()
    except Exception:
        return None

# 上传文件
def upload_file_to_oss(file, category="public"):
    file_name = f"{category}/{int(time.time())}_{file.name}"
    ext = os.path.splitext(file.name)[-1].lower()
    content_type_map = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".mp4": "video/mp4"
    }
    headers = {"Content-Type": content_type_map.get(ext, "application/octet-stream")}
    try:
        bucket.put_object(file_name, file.getvalue(), headers=headers)
        return f"{ENDPOINT}/{file_name}"
    except Exception as e:
        st.error(f"❌ 上传失败: {e}")
        return None

# 千问 API
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
    st.markdown("---")

    col1, col2 = st.columns([2, 1])
    with col1:
        info = st.text_input("✍️ 问题输入", placeholder="请在此输入你的问题...", label_visibility="visible")
    with col2:
        uploaded_file = st.file_uploader("📷 上传试题图片", type=["jpg", "png", "jpeg"])

    image_url = None
    if uploaded_file:
        st.image(uploaded_file, caption="🖼 已上传图片", use_column_width=True)
        with st.spinner("🔄 正在上传图片..."):
            image_url = upload_file_to_oss(uploaded_file, category="civilpass/images")
        if image_url:
            st.success("✅ 图片上传成功！")

    if st.button("🚀 获取 AI 答案", use_container_width=True):
        if not info and not image_url:
            st.warning("⚠️ 请填写问题或上传图片")
        else:
            chat_message(info if info else "（仅上传图片）", is_user=True)
            with st.spinner("🤖 AI 正在解析中..."):
                answer = query_qwen_api(info, image_url)
            chat_message(answer, is_user=False)

# 备考资料模块
def display_study_materials():
    st.title("📚 备考资料")
    st.caption("📢 提供各类备考资料，支持按年份搜索、在线查看和下载！")
    st.markdown("---")

    categories = ["行测", "申论", "视频"]
    selected_categories = st.multiselect("📂 选择类别", categories)
    year_keyword = st.text_input("🔎 输入年份关键词（如 2025）")

    for category in selected_categories:
        st.subheader(f"📁 {category}")
        try:
            result = bucket.list_objects(prefix=category)
            if not result.object_list:
                st.warning(f"📭 当前类别暂无内容")
                continue

            count = 0
            for obj in result.object_list:
                file_name = obj.key.split("/")[-1]
                file_url = f"{ENDPOINT}/{obj.key}"
                file_data = get_cached_oss_object(obj.key)

                if year_keyword and year_keyword not in file_name:
                    continue

                if category == "视频" and file_name.endswith((".mp4", ".webm")):
                    st.markdown(f"🎬 **{file_name}**")
                    st.video(file_url)
                elif file_name.endswith(".pdf"):
                    if not year_keyword and count >= 5:
                        continue
                    st.markdown(f"📄 **{file_name}**")
                elif file_name.endswith((".jpg", ".jpeg", ".png")):
                    st.image(BytesIO(file_data), caption=file_name, use_column_width=True)

                st.markdown(f"[📥 下载]({file_url})")
                st.markdown("---")
                count += 1
        except Exception as e:
            st.error(f"❌ 加载失败：{e}")

# 高分经验模块
def display_experience():
    st.title("🌟 高分经验")
    st.caption("📢 来自高分考生的真实经验分享")
    st.markdown("---")

    # 用户上传功能区（独立目录）
    with st.expander("📤 上传我的学习资料", expanded=False):
        # 创建两列布局
        col_upload, col_desc = st.columns([2, 3])

        with col_upload:
            upload_type = st.radio("选择上传类型",
                                   ["学习笔记", "错题集"],
                                   horizontal=True,
                                   help="请选择资料分类")

            uploaded_files = st.file_uploader("选择文件",
                                              type=["pdf", "jpg", "jpeg", "png"],
                                              accept_multiple_files=True,
                                              help="支持格式：PDF/图片")

            if st.button("🚀 开始上传", key="user_upload"):
                if not uploaded_files:
                    st.warning("请先选择要上传的文件")
                    return

                success_count = 0
                target_folder = "学习笔记" if upload_type == "学习笔记" else "错题集"

                for file in uploaded_files:
                    # 生成规范化文件名：时间戳_原始文件名
                    timestamp = int(time.time())
                    safe_name = f"{timestamp}_{file.name.replace(' ', '_')}"
                    oss_path = f"{target_folder}/{safe_name}"

                    try:
                        bucket.put_object(oss_path, file.getvalue())
                        success_count += 1
                    except Exception as e:
                        st.error(f"'{file.name}' 上传失败: {str(e)}")

                if success_count > 0:
                    st.success(f"成功上传 {success_count}/{len(uploaded_files)} 个文件！")
                    st.balloons()

        with col_desc:
            st.markdown("""
                **📝 上传说明**
                - 文件命名建议：`科目_内容`（示例：行测_图形推理技巧.pdf）
                - 单个文件大小限制：不超过20MB
                - 审核机制：上传内容将在24小时内人工审核
                - 禁止上传包含个人隐私信息的资料
            """)

    # 资料展示功能区
    st.markdown("## 📚 资料浏览")
    tab_exp, tab_notes, tab_errors = st.tabs([
        "📜 高分经验",
        "📖 学习笔记",
        "❌ 错题集"
    ])

    # 公共显示函数
    def display_files(prefix, tab):
        try:
            file_list = []
            for obj in oss2.ObjectIterator(bucket, prefix=prefix):
                if not obj.key.endswith('/'):
                    # 解析文件名（去除时间戳）
                    raw_name = obj.key.split("/")[-1]
                    display_name = "_".join(raw_name.split("_")[1:])  # 去掉时间戳

                    file_list.append({
                        "display": display_name,
                        "raw_name": raw_name,
                        "url": f"{ENDPOINT}/{obj.key}",
                        "type": "pdf" if obj.key.lower().endswith(".pdf") else "image"
                    })

            if not file_list:
                tab.warning("当前分类下暂无资料")
                return

            # 网格布局展示
            cols = tab.columns(3)
            for idx, file_info in enumerate(file_list):
                with cols[idx % 3]:
                    # 文件预览区域
                    with st.container(border=True):
                        # 显示预览
                        if file_info["type"] == "image":
                            img_data = get_cached_oss_object(obj.key)
                            st.image(BytesIO(img_data),
                                     use_column_width=True,
                                     caption=file_info["display"])
                        else:
                            # PDF显示带文件名
                            st.markdown(f"📄 **{file_info['display']}**")
                            base64_pdf = base64.b64encode(bucket.get_object(obj.key).read()).decode()
                            st.markdown(f"""
                                <iframe 
                                    src="data:application/pdf;base64,{base64_pdf}"
                                    width="100%" 
                                    height="300px"
                                    style="border:1px solid #eee; border-radius:5px;">
                                </iframe>
                            """, unsafe_allow_html=True)

                        # 下载按钮
                        st.markdown(f"""
                            <div style="margin-top:10px; text-align:center;">
                                <a href="{file_info['url']}" download>
                                    <button style="
                                        background: #4CAF50;
                                        color: white;
                                        border: none;
                                        padding: 8px 20px;
                                        border-radius: 5px;
                                        cursor: pointer;">
                                        ⬇️ 下载
                                    </button>
                                </a>
                            </div>
                        """, unsafe_allow_html=True)

        except Exception as e:
            tab.error(f"加载失败：{str(e)}")

    # 各标签页内容
    with tab_exp:  # 原始高分经验
        display_files(prefix="高分经验/", tab=tab_exp)

    with tab_notes:  # 独立学习笔记
        display_files(prefix="学习笔记/", tab=tab_notes)

    with tab_errors:  # 独立错题集
        display_files(prefix="错题集/", tab=tab_errors)

# 政策资讯模块
def display_policy_news():
    st.title("📰 政策资讯")
    st.caption("📢 最新公务员政策动态与权威解读")
    st.markdown("---")

    @st.cache_data(ttl=3600, show_spinner="正在加载最新政策资讯...")
    def load_policy_data():
        try:
            csv_data = bucket.get_object("政策咨询/civilpass_data.csv").read()
            df = pd.read_csv(
                BytesIO(csv_data),
                parse_dates=['date'],
                usecols=['title', 'source', 'date', 'url']
            )
            df = df.dropna(subset=['title', 'url']).drop_duplicates('url')
            df['summary'] = '暂无摘要'
            df['region'] = '全国'
            df['hotness'] = 0
            return df
        except Exception as e:
            st.error(f"❌ 数据加载失败：{str(e)}")
            return pd.DataFrame()

    df = load_policy_data()
    if df.empty:
        return

    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1

    with st.expander("🔍 智能筛选", expanded=True):
        col1, col2 = st.columns([2, 3])
        with col1:
            date_range = st.date_input(
                "📅 日期范围",
                value=(df['date'].min().date(), df['date'].max().date()),
                format="YYYY/MM/DD"
            )
            sources = st.multiselect(
                "🏛️ 信息来源",
                options=df['source'].unique(),
                placeholder="全部来源"
            )
        with col2:
            keyword = st.text_input(
                "🔎 关键词搜索",
                placeholder="标题/内容关键词（支持空格分隔多个关键词）",
                help="示例：公务员 待遇 调整"
            )
            regions = st.multiselect(
                "🌍 相关地区",
                options=df['region'].unique(),
                placeholder="全国范围"
            )

    sort_col, _ = st.columns([1, 2])
    with sort_col:
        sort_option = st.selectbox(
            "排序方式",
            options=["最新优先", "最旧优先", "热度排序", "来源分类"],
            index=0
        )

    def process_data(df):
        start_date = pd.Timestamp(date_range[0])
        end_date = pd.Timestamp(date_range[1])
        filtered = df[df['date'].between(start_date, end_date)]
        if sources:
            filtered = filtered[filtered['source'].isin(sources)]
        if regions:
            filtered = filtered[filtered['region'].isin(regions)]
        if keyword:
            keywords = [k.strip() for k in keyword.split()]
            pattern = '|'.join(keywords)
            filtered = filtered[
                filtered['title'].str.contains(pattern, case=False) |
                filtered['summary'].str.contains(pattern, case=False)
            ]
        if sort_option == "最新优先":
            return filtered.sort_values('date', ascending=False)
        elif sort_option == "最旧优先":
            return filtered.sort_values('date', ascending=True)
        elif sort_option == "热度排序":
            return filtered.sort_values('hotness', ascending=False)
        else:
            return filtered.sort_values(['source', 'date'], ascending=[True, False])

    processed_df = process_data(df)

    PAGE_SIZE = 10
    total_items = len(processed_df)
    total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)

    # ⏮ 翻页按钮
    col_prev, col_page, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.button("← 上一页") and st.session_state.current_page > 1:
            st.session_state.current_page -= 1
    with col_next:
        if st.button("下一页 →") and st.session_state.current_page < total_pages:
            st.session_state.current_page += 1
    with col_page:
        st.markdown(
            f"<div style='text-align: center; padding-top: 8px;'>第 {st.session_state.current_page} 页 / 共 {total_pages} 页</div>",
            unsafe_allow_html=True
        )

    # 页码重置逻辑（每次筛选条件变化时都重置为第 1 页）
    if st.session_state.current_page > total_pages:
        st.session_state.current_page = total_pages

    start_idx = (st.session_state.current_page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    current_data = processed_df.iloc[start_idx:end_idx]

    if current_data.empty:
        st.warning("😢 未找到符合条件的资讯")
    else:
        st.markdown(f"""
            <div style="background: #f0f2f6; padding: 12px; border-radius: 8px; margin: 10px 0;">
                📊 找到 <strong>{len(processed_df)}</strong> 条结果 | 
                📅 时间跨度：{date_range[0]} 至 {date_range[1]} | 
                🌟 平均热度值：{processed_df['hotness'].mean():.1f}
            </div>
        """, unsafe_allow_html=True)

        for _, row in current_data.iterrows():
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"### [{row['title']}]({row['url']})")
                    meta_cols = st.columns(3)
                    with meta_cols[0]:
                        st.markdown(f"📅 **日期**: {row['date'].strftime('%Y/%m/%d')}")
                    with meta_cols[1]:
                        st.markdown(f"🏛️ **来源**: {row['source']}")
                    with meta_cols[2]:
                        st.markdown(f"🌍 **地区**: {row['region']}")
                    with st.expander("📝 查看摘要"):
                        st.write(row['summary'])
                with col2:
                    st.metric("🔥 热度指数", f"{row['hotness']}")
                    if st.button("⭐ 收藏", key=f"fav_{row['url']}"):
                        st.toast("已加入收藏夹！", icon="✅")
                    st.markdown("---")
                    st.markdown(f"""
                        <div style="text-align: center; margin-top: 8px;">
                            <a href="{row['url']}" target="_blank" style="text-decoration: none; font-size: 14px;">🔗 查看原文</a>
                        </div>
                    """, unsafe_allow_html=True)

    with st.expander("📈 数据洞察", expanded=False):
        tab1, tab2, tab3 = st.tabs(["来源分析", "时间趋势", "地区分布"])

        with tab1:
            source_counts = processed_df['source'].value_counts().head(10)
            st.bar_chart(source_counts)

        with tab2:
            time_series = processed_df.set_index('date').resample('W').size()
            st.area_chart(time_series)

        with tab3:
            import matplotlib.pyplot as plt
            from matplotlib import font_manager

            region_counts = processed_df['region'].value_counts()
            fig, ax = plt.subplots(figsize=(8, 8))
            region_counts.plot.pie(autopct='%1.1f%%', ax=ax)
            ax.set_ylabel("")
            st.pyplot(fig)

        st.download_button(
            label="📥 导出当前结果（CSV）",
            data=processed_df.to_csv(index=False).encode('utf-8'),
            file_name=f"policy_news_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            help="导出当前筛选条件下的所有结果"
        )

    st.markdown("""
        <style>
            @media (max-width: 768px) {
                .stContainer > div {
                    flex-direction: column !important;
                }
                .element-container {
                    margin-bottom: 1rem;
                }
            }
        </style>
    """, unsafe_allow_html=True)

#考试日历模块
def display_exam_calendar():
    import json
    from collections import defaultdict
    from io import BytesIO
    from PIL import Image
    import jinja2
    from datetime import datetime

    st.title("📅 智能考试日历")
    st.markdown("⚠️ <span style='color:red;'>考试时间仅供参考，请以官方公布为准！</span>", unsafe_allow_html=True)
    st.markdown("---")

    # 样式注入
    st.markdown("""
        <style>
            .timeline {
                border-left: 3px solid #3C82F6;
                padding-left: 20px;
                margin: 20px 0;
            }
            .timeline-item {
                margin: 15px 0;
                padding: 15px;
                background: #f5f7fb;
                border-radius: 8px;
                position: relative;
            }
            .timeline-date {
                font-weight: bold;
                color: #3C82F6;
                margin-bottom: 8px;
            }
            .timeline-content {
                margin-left: 25px;
            }
            .calendar-tag {
                display: inline-block;
                padding: 2px 8px;
                border-radius: 12px;
                background: #e6f0ff;
                color: #3C82F6;
                font-size: 0.8em;
                margin: 2px;
            }
            @media (max-width: 768px) {
                .timeline-item { padding: 10px; }
            }
        </style>
    """, unsafe_allow_html=True)

    # 缓存数据加载
    @st.cache_data(ttl=3600, show_spinner="正在加载考试日历...")
    def load_calendar_data():
        try:
            # 加载结构化考试事件数据
            event_file = bucket.get_object("考试日历/events_date.json").read()
            events = json.loads(event_file)['events']

            # 加载图片文件索引
            images = []
            for obj in oss2.ObjectIterator(bucket, prefix="考试日历/images/"):
                if obj.key.lower().endswith((".jpg", ".jpeg", ".png")):
                    images.append({
                        "key": obj.key,
                        "name": obj.key.split("/")[-1],
                        "url": f"{ENDPOINT}/{obj.key}"
                    })

            return {
                "events": sorted(events, key=lambda x: x['date']),
                "images": images
            }

        except Exception as e:
            st.error(f"❌ 数据加载失败：{str(e)}")
            return {"events": [], "images": []}

    # 加载数据
    data = load_calendar_data()
    events = data['events']
    images = data['images']

    # 顶部过滤栏
    with st.container():
        col1, col2, col3 = st.columns([2, 3, 2])
        with col1:
            selected_year = st.selectbox(
                "选择年份",
                options=sorted({datetime.strptime(e['date'], "%Y-%m-%d").year for e in events}, reverse=True),
                index=0
            )
        with col2:
            search_query = st.text_input("🔍 搜索考试名称或地区", placeholder="输入关键词筛选...")
        with col3:
            view_mode = "🗓 月历视图"  # 强制固定视图模式
            st.markdown('<div style="visibility:hidden">占位</div>', unsafe_allow_html=True)

    # 过滤数据
    filtered_events = [
        e for e in events
        if datetime.strptime(e['date'], "%Y-%m-%d").year == selected_year
        and (search_query.lower() in e['name'].lower()
             or any(search_query.lower() in r.lower() for r in e['regions']))
    ]

    # 展示内容
    if view_mode == "🗓 月历视图":
        tabs = st.tabs([f"{m}月" for m in range(1, 13)])

        monthly_events = defaultdict(list)
        for event in filtered_events:
            month = datetime.strptime(event['date'], "%Y-%m-%d").month
            monthly_events[month].append(event)

        for idx, tab in enumerate(tabs):
            month_num = idx + 1
            with tab:
                # 查找该月对应图片
                month_images = [img for img in images if f"{selected_year}-{month_num:02}" in img['name']]

                if month_images:
                    cols = st.columns(2)
                    for img_idx, img in enumerate(month_images):
                        with cols[img_idx % 2]:
                            with st.popover(f"📷 {img['name'].split('.')[0]}"):
                                img_data = get_cached_oss_object(img['key'])
                                st.image(BytesIO(img_data), use_column_width=True)
                                st.download_button(
                                    "下载原图",
                                    data=img_data,
                                    file_name=img['name'],
                                    mime="image/jpeg"
                                )
                            st.caption(f"📅 {img['name'].split('.')[0]}")

                # 展示事件
                st.subheader(f"{month_num}月重要考试")
                if not monthly_events.get(month_num):
                    st.info("本月暂无已公布的考试安排")
                    continue

                for event in monthly_events[month_num]:
                    with st.expander(f"📌 {event['name']} - {event['date']}"):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**日期**: {event['date']}")
                            st.markdown(f"**地区**: {', '.join(event['regions'])}")
                            st.markdown(f"**来源**: {', '.join(event['sources'])}")
                        with col2:
                            if event.get('image'):
                                st.image(f"{ENDPOINT}/{event['image']}", width=120)

    # 侧边提醒栏
    with st.sidebar:
        st.header("🔔 提醒服务")
        selected_events = st.multiselect(
            "选择要提醒的考试",
            options=[e['name'] for e in filtered_events],
            placeholder="选择考试项目"
        )

        if selected_events:
            remind_time = st.number_input("提前提醒天数", min_value=1, max_value=30, value=7)
            if st.button("设置提醒", type="primary"):
                st.toast("🎉 提醒设置成功！将在考试前{}天通知".format(remind_time))

        st.markdown("---")
        st.markdown("**📲 手机订阅**")
        st.write("扫描二维码订阅日历")
        try:
            qr_code = Image.open("path_to_qrcode.png")  # 替换为你的二维码图片路径
            st.image(qr_code, width=150)
        except Exception:
            st.warning("⚠️ 未找到二维码图片")

    # 移动端适配
    st.markdown("""
        <script>
            window.addEventListener('resize', function() {
                const images = document.querySelectorAll('img');
                images.forEach(img => {
                    if(window.innerWidth < 768) {
                        img.style.maxHeight = '200px';
                    } else {
                        img.style.maxHeight = 'none';
                    }
                });
            });
        </script>
    """, unsafe_allow_html=True)


# 管理员上传模块
def admin_upload_center():
    st.title("📤 管理员上传中心")
    st.caption("⚠️ 仅限授权人员使用")
    st.markdown("---")

    password = st.text_input("🔐 输入管理员密码", type="password")
    if password != "cjl20030623":
        st.warning("🔒 密码错误，无法访问上传功能")
        return

    category = st.selectbox("📁 上传目录", ["行测", "申论", "视频", "高分经验", "政策咨询", "考试日历"])
    files = st.file_uploader("📎 选择文件", accept_multiple_files=True)
    if st.button("🚀 上传文件"):
        with st.spinner("📤 正在上传中..."):
            for file in files:
                upload_file_to_oss(file, category=category)
        st.success("✅ 上传完成！")

# 主函数
def main():
    dark_mode = st.sidebar.toggle("🌙 夜间模式")
    set_dark_mode(dark_mode)

    st.sidebar.title("🎯 公考助手")
    menu = st.sidebar.radio("📌 功能导航",
                            ["智能问答", "考试日历", "备考资料", "政策资讯", "高分经验", "上传资料（管理员）"])

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
