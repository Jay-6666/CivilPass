import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from src.utils.oss import get_cached_oss_object, bucket
import math

def display_news():
    """显示政策资讯"""
    st.title("📰 政策资讯")
    st.caption("📢 最新公务员政策动态与权威解读")
    st.markdown("---")

    @st.cache_data(ttl=3600, show_spinner="正在加载最新政策资讯...")
    def load_all_policy_data():
        # 配置参数
        OSS_PATH = "政策咨询"  # OSS存储路径
        REQUIRED_COLUMNS = ["title", "source", "date", "url"]  # 必要字段
        DEFAULT_VALUES = {"summary": "暂无摘要", "region": "全国", "hotness": 0}  # 默认值配置

        all_dfs = []
        error_files = []

        try:
            # 获取目录下所有CSV文件
            files = bucket.list_objects(OSS_PATH).object_list
            csv_files = [f.key for f in files if f.key.endswith(".csv")]

            if not csv_files:
                st.error("❌ 目录中未找到CSV文件")
                return pd.DataFrame()

            progress_text = f"正在加载 {len(csv_files)} 个数据源..."
            progress_bar = st.progress(0, text=progress_text)

            for i, file_path in enumerate(csv_files):
                try:
                    # 读取CSV文件
                    csv_data = bucket.get_object(file_path).read()
                    df = pd.read_csv(BytesIO(csv_data), parse_dates=["date"])

                    # 字段校验
                    missing_cols = set(REQUIRED_COLUMNS) - set(df.columns)
                    if missing_cols:
                        raise ValueError(f"缺少必要字段：{', '.join(missing_cols)}")

                    # 添加数据源标识
                    df["data_source"] = file_path.split("/")[-1]

                    # 补充默认值
                    for col, value in DEFAULT_VALUES.items():
                        df[col] = value

                    all_dfs.append(df)

                except Exception as e:
                    error_files.append((file_path, str(e)))
                finally:
                    progress_bar.progress((i + 1) / len(csv_files), text=progress_text)

            # 合并数据
            if not all_dfs:
                st.error("❌ 所有文件加载失败")
                return pd.DataFrame()

            combined_df = pd.concat(all_dfs, ignore_index=True)

            # 数据清洗
            combined_df = (combined_df.dropna(subset=["title", "url"])
                         .drop_duplicates("url", keep="first")
                         .sort_values("date", ascending=False)
                         .reset_index(drop=True))

            return combined_df

        except Exception as e:
            st.error(f"❌ 目录访问失败：{str(e)}")
            return pd.DataFrame()

    df = load_all_policy_data()
    if df.empty:
        st.warning("⚠️ 当前无可用政策数据")
        return

    with st.expander("🔍 智能筛选", expanded=True):
        col1, col2 = st.columns([2, 3])
        with col1:
            date_range = st.date_input(
                "📅 日期范围",
                value=(df["date"].min().date(), df["date"].max().date()),
                format="YYYY/MM/DD"
            )
            sources = st.multiselect(
                "🏛️ 信息来源",
                options=df["source"].unique(),
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
                options=df["region"].unique(),
                placeholder="全国范围"
            )

    def process_data(df):
        start_date = pd.Timestamp(date_range[0])
        end_date = pd.Timestamp(date_range[1])
        filtered = df[df["date"].between(start_date, end_date)]
        
        if sources:
            filtered = filtered[filtered["source"].isin(sources)]
        if regions:
            filtered = filtered[filtered["region"].isin(regions)]
        if keyword:
            keywords = [k.strip() for k in keyword.split()]
            pattern = "|".join(keywords)
            filtered = filtered[
                filtered["title"].str.contains(pattern, case=False) |
                filtered["summary"].str.contains(pattern, case=False)
            ]
        
        return filtered.sort_values("date", ascending=False)

    processed_df = process_data(df)

    if processed_df.empty:
        st.warning("😢 未找到符合条件的资讯")
    else:
        # 分页设置
        items_per_page = 30
        total_items = len(processed_df)
        total_pages = math.ceil(total_items / items_per_page)
        
        col1, col2, col3 = st.columns([2, 3, 2])
        with col2:
            current_page = st.number_input(
                "页码",
                min_value=1,
                max_value=total_pages,
                value=1,
                help=f"共 {total_pages} 页"
            )

        start_idx = (current_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_df = processed_df.iloc[start_idx:end_idx]

        st.markdown(
            f"""
            <div style="background: #f0f2f6; padding: 12px; border-radius: 8px; margin: 10px 0;">
                📊 共找到 <strong>{total_items}</strong> 条结果 | 
                📄 当前显示第 {start_idx + 1}-{min(end_idx, total_items)} 条 |
                📅 时间跨度：{date_range[0]} 至 {date_range[1]} | 
                🌟 平均热度值：{processed_df['hotness'].mean():.1f}
            </div>
            """,
            unsafe_allow_html=True
        )

        # 显示分页导航按钮
        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
        with col1:
            if current_page > 1:
                if st.button("⏮️ 第一页"):
                    st.session_state.current_page = 1
                    st.rerun()
        with col2:
            if current_page > 1:
                if st.button("◀️ 上一页"):
                    st.session_state.current_page = current_page - 1
                    st.rerun()
        with col3:
            if current_page < total_pages:
                if st.button("▶️ 下一页"):
                    st.session_state.current_page = current_page + 1
                    st.rerun()
        with col4:
            if current_page < total_pages:
                if st.button("⏭️ 最后一页"):
                    st.session_state.current_page = total_pages
                    st.rerun()

        for _, row in page_df.iterrows():
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    st.markdown(
                        f"""
                        <a href="{row['url']}" target="_blank" style="text-decoration: none;">
                            <h3>{row['title']}</h3>
                        </a>
                        """,
                        unsafe_allow_html=True
                    )
                    st.markdown(f"📅 **日期**: {row['date'].strftime('%Y/%m/%d')}")
                    st.markdown(f"🏛️ **来源**: {row['source']}")
                    st.markdown(f"🌍 **地区**: {row['region']}")
                
                with col2:
                    st.markdown(f"🔥 热度：{row['hotness']}")
                    st.link_button("🔗 查看原文", row['url'], type="primary", use_container_width=True)

        # 导出功能
        st.download_button(
            label="📥 导出当前结果（CSV）",
            data=processed_df.to_csv(index=False).encode("utf-8"),
            file_name=f"policy_news_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            help="导出当前筛选条件下的所有结果"
        ) 