import streamlit as st
from io import BytesIO
import oss2
from src.utils.oss import get_cached_oss_object, bucket
from src.config.settings import ENDPOINT
import re
from datetime import datetime

def check_oss_path(prefix):
    """检查OSS路径是否存在并返回有效的文件列表"""
    try:
        possible_prefixes = [
            prefix,
            f"{prefix}/",
            f"{prefix}/试题/",
            f"试题/{prefix}/",
        ]

        all_files = []
        for test_prefix in possible_prefixes:
            result = bucket.list_objects(prefix=test_prefix)
            if result.object_list:
                all_files.extend(result.object_list)
                st.session_state.valid_prefix = test_prefix
                break

        return all_files
    except Exception as e:
        st.error(f"检查路径出错：{str(e)}")
        return []

def extract_year(filename):
    """从文件名中提取年份"""
    # 匹配2000-2099年的数字
    match = re.search(r'20\d{2}', filename)
    if match:
        return match.group(0)
    return None

def get_supported_file_types(exam_type):
    """根据试题类型返回支持的文件类型"""
    if exam_type == "面试":
        return (".mp4", ".MP4")
    return (".pdf", ".PDF", ".jpg", ".jpeg", ".png")

def display_materials():
    """显示备考资料"""
    st.title("📚 备考资料")
    st.caption("📢 提供各类备考资料，支持快速下载！")
    st.markdown("---")

    # 初始化session state
    if 'valid_prefix' not in st.session_state:
        st.session_state.valid_prefix = None

    # 试卷类型选择
    exam_types = {
        "行测": "行测试题",
        "申论": "申论试题",
        "面试": "面试真题"
    }
    
    col1, col2 = st.columns([2, 3])
    with col1:
        selected_type = st.radio(
            "选择试题类型",
            list(exam_types.keys()),
            horizontal=True,
            format_func=lambda x: exam_types[x]
        )
    
    with col2:
        # 获取当前年份
        current_year = datetime.now().year
        # 生成年份列表（从当前年份往前推10年）
        years = [str(year) for year in range(current_year, current_year-11, -1)]
        selected_year = st.selectbox(
            "选择年份",
            ["全部"] + years,
            help="选择特定年份的试题"
        )

    try:
        # 检查并获取文件列表
        object_list = check_oss_path(selected_type)
        
        if not object_list:
            st.warning(f"📭 暂无{exam_types[selected_type]}资料")
            return

        # 处理文件列表
        supported_types = get_supported_file_types(selected_type)
        exam_papers = []
        
        for obj in object_list:
            file_name = obj.key.split("/")[-1]
            if file_name.lower().endswith(supported_types):
                # 提取年份
                year = extract_year(file_name)
                if selected_year != "全部" and year != selected_year:
                    continue
                    
                exam_papers.append({
                    "name": file_name,
                    "key": obj.key,
                    "url": f"{ENDPOINT}/{obj.key}",
                    "year": year or "未知年份"
                })

        if not exam_papers:
            if selected_year != "全部":
                st.warning(f"📭 未找到 {selected_year} 年的{exam_types[selected_type]}")
            else:
                st.warning(f"📭 未找到可下载的试题文件")
            return

        # 按年份和文件名排序
        exam_papers.sort(key=lambda x: (x["year"], x["name"]), reverse=True)
        
        # 显示试题列表
        st.subheader(f"📑 {exam_types[selected_type]}")
        
        # 使用表格布局展示试卷
        for i, paper in enumerate(exam_papers, 1):
            col1, col2, col3 = st.columns([1, 3, 1])
            
            with col1:
                st.markdown(f"**{paper['year']}**")
            
            with col2:
                if selected_type == "面试" and paper["name"].lower().endswith((".mp4", ".MP4")):
                    st.markdown(f"🎥 **{paper['name']}**")
                    st.video(paper["url"])
                else:
                    st.markdown(f"📄 **{paper['name']}**")
            
            with col3:
                try:
                    file_data = get_cached_oss_object(paper["key"])
                    mime_type = "video/mp4" if paper["name"].lower().endswith((".mp4", ".MP4")) else \
                              "application/pdf" if paper["name"].lower().endswith(".pdf") else \
                              "image/jpeg"
                    
                    st.download_button(
                        "📥 下载",
                        data=file_data,
                        file_name=paper["name"],
                        mime=mime_type,
                        use_container_width=True
                    )
                except Exception as e:
                    st.error("❌ 下载失败")
            st.markdown("---")

    except Exception as e:
        st.error(f"❌ 加载资料失败：{str(e)}")

    # 移动端优化
    st.markdown(
        """
        <style>
        /* 移动端适配 */
        @media (max-width: 768px) {
            .stDownloadButton {
                width: 100% !important;
            }
            .stVideo {
                width: 100% !important;
                height: auto !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    ) 