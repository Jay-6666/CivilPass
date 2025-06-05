import streamlit as st
from io import BytesIO
from src.utils.oss import get_cached_oss_object, upload_file_to_oss, bucket
from src.config.settings import ENDPOINT

def display_experience():
    """显示高分经验"""
    st.title("🌟 高分经验")
    st.caption("📢 来自高分考生的真实经验分享")
    st.markdown("---")

    # 用户上传功能区
    with st.expander("📤 上传我的学习资料", expanded=False):
        col_upload, col_desc = st.columns([2, 3])

        with col_upload:
            upload_type = st.radio(
                "选择上传类型",
                ["学习笔记", "错题集"],
                horizontal=True,
                help="请选择资料分类"
            )

            uploaded_files = st.file_uploader(
                "选择文件",
                type=["pdf", "jpg", "jpeg", "png"],
                accept_multiple_files=True,
                help="支持格式：PDF/图片"
            )

            if st.button("🚀 开始上传", key="user_upload"):
                if not uploaded_files:
                    st.warning("请先选择要上传的文件")
                    return

                success_count = 0
                target_folder = "学习笔记" if upload_type == "学习笔记" else "错题集"

                for file in uploaded_files:
                    if upload_file_to_oss(file, category=target_folder):
                        success_count += 1

                if success_count > 0:
                    st.success(f"成功上传 {success_count}/{len(uploaded_files)} 个文件！")
                    st.balloons()

        with col_desc:
            st.markdown(
                """
                **📝 上传说明**
                - 文件命名建议：`科目_内容`（示例：行测_图形推理技巧.pdf）
                - 单个文件大小限制：不超过20MB
                - 审核机制：上传内容将在24小时内人工审核
                - 禁止上传包含个人隐私信息的资料
                """
            )

    # 资料展示功能区
    st.markdown("## 📚 资料浏览")
    tab_exp, tab_notes, tab_errors = st.tabs(["📜 高分经验", "📖 学习笔记", "❌ 错题集"])

    def display_files(prefix, tab):
        """公共显示函数"""
        try:
            file_list = []
            objects = bucket.list_objects(prefix=prefix).object_list
            if not objects:
                tab.warning("当前分类下暂无资料")
                return

            for obj in objects:
                if not obj.key.endswith("/"):
                    raw_name = obj.key.split("/")[-1]
                    display_name = "_".join(raw_name.split("_")[1:])
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
                    with st.container(border=True):
                        if file_info["type"] == "image":
                            img_data = get_cached_oss_object(file_info["raw_name"])
                            st.image(BytesIO(img_data), use_column_width=True)
                        else:
                            st.markdown(f"📄 **{file_info['display']}**")

                        st.markdown(
                            f"""
                            <div style="text-align: center;">
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
                            """,
                            unsafe_allow_html=True
                        )

        except Exception as e:
            tab.error(f"加载失败：{str(e)}")

    # 各标签页内容
    with tab_exp:
        display_files(prefix="高分经验/", tab=tab_exp)

    with tab_notes:
        display_files(prefix="学习笔记/", tab=tab_notes)

    with tab_errors:
        display_files(prefix="错题集/", tab=tab_errors) 