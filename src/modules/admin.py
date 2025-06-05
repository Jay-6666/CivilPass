import streamlit as st
from src.utils.auth import require_admin_auth
from src.utils.oss import upload_file_to_oss

@require_admin_auth()
def admin_upload_center():
    """管理员上传中心"""
    st.title("📤 管理员上传中心")
    st.caption("⚠️ 仅限授权人员使用")
    st.markdown("---")

    category = st.selectbox(
        "📁 上传目录",
        ["行测", "申论", "视频", "高分经验", "政策咨询", "考试日历"]
    )

    files = st.file_uploader("📎 选择文件", accept_multiple_files=True)

    if st.button("🚀 上传文件"):
        with st.spinner("📤 正在上传中..."):
            success_count = 0
            for file in files:
                if upload_file_to_oss(file, category=category):
                    success_count += 1
            
            if success_count > 0:
                st.success(f"✅ 成功上传 {success_count}/{len(files)} 个文件！")
            else:
                st.error("❌ 上传失败") 