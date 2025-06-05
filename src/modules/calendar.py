import streamlit as st
import json
from datetime import datetime
from collections import defaultdict
from src.utils.oss import get_cached_oss_object, bucket
from src.config.settings import ENDPOINT

def display_calendar():
    """显示考试日历"""
    st.title("📅 智能考试日历")
    st.markdown("⚠️ <span style='color:red;'>考试时间仅供参考，请以官方公布为准！</span>", unsafe_allow_html=True)
    st.markdown("---")

    # 加载日历数据
    @st.cache_data(ttl=3600, show_spinner="正在加载考试日历...")
    def load_calendar_data():
        try:
            # 加载结构化考试事件数据
            event_file = bucket.get_object("考试日历/events_date.json").read()
            events = json.loads(event_file)["events"]

            # 加载图片文件索引
            images = []
            result = bucket.list_objects(prefix="考试日历/images/")
            for obj in result.object_list:
                if obj.key.lower().endswith((".jpg", ".jpeg", ".png")):
                    images.append({
                        "key": obj.key,
                        "name": obj.key.split("/")[-1],
                        "url": f"{ENDPOINT}/{obj.key}"
                    })

            return {
                "events": sorted(events, key=lambda x: x["date"]),
                "images": images
            }
        except Exception as e:
            st.error(f"❌ 数据加载失败：{str(e)}")
            return {"events": [], "images": []}

    # 加载数据
    data = load_calendar_data()
    events = data["events"]
    images = data["images"]

    # 过滤控件
    col1, col2 = st.columns([1, 2])
    with col1:
        selected_year = st.selectbox(
            "选择年份",
            options=sorted({datetime.strptime(e["date"], "%Y-%m-%d").year for e in events}, reverse=True),
            index=0
        )
    with col2:
        search_query = st.text_input("🔍 搜索考试名称或地区", placeholder="输入关键词筛选...")

    # 过滤数据
    filtered_events = [
        e for e in events
        if datetime.strptime(e["date"], "%Y-%m-%d").year == selected_year
        and (search_query.lower() in e["name"].lower()
             or any(search_query.lower() in r.lower() for r in e["regions"]))
    ]

    # 按月份显示
    tabs = st.tabs([f"{m}月" for m in range(1, 13)])
    monthly_events = defaultdict(list)
    for event in filtered_events:
        month = datetime.strptime(event["date"], "%Y-%m-%d").month
        monthly_events[month].append(event)

    for idx, tab in enumerate(tabs):
        month_num = idx + 1
        with tab:
            # 查找该月对应图片
            month_images = [img for img in images if f"{selected_year}-{month_num:02}" in img["name"]]
            if month_images:
                for img in month_images:
                    with st.expander(f"📷 {img['name'].split('.')[0]}"):
                        img_data = get_cached_oss_object(img["key"])
                        st.image(img_data, use_column_width=True)

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
                        if event.get("image"):
                            st.image(f"{ENDPOINT}/{event['image']}", width=120)

    # 侧边栏提醒设置
    with st.sidebar:
        st.header("🔔 提醒服务")
        selected_events = st.multiselect(
            "选择要提醒的考试",
            options=[e["name"] for e in filtered_events],
            placeholder="选择考试项目"
        )

        if selected_events:
            remind_time = st.number_input("提前提醒天数", min_value=1, max_value=30, value=7)
            if st.button("设置提醒", type="primary"):
                st.toast("🎉 提醒设置成功！将在考试前{}天通知".format(remind_time)) 