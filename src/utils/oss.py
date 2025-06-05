import oss2
import streamlit as st
from io import BytesIO
import time
from src.config.settings import (
    ACCESS_KEY_ID,
    ACCESS_KEY_SECRET,
    BUCKET_NAME,
    REGION,
    ENDPOINT
)

# OSS 初始化
auth = oss2.Auth(ACCESS_KEY_ID, ACCESS_KEY_SECRET)
bucket = oss2.Bucket(auth, f"http://oss-{REGION}.aliyuncs.com", BUCKET_NAME)

@st.cache_data(show_spinner=False)
def get_cached_oss_object(key):
    """缓存 OSS 内容"""
    try:
        return bucket.get_object(key).read()
    except Exception:
        return None

def upload_file_to_oss(file, category="public"):
    """上传文件到OSS"""
    file_name = f"{category}/{int(time.time())}_{file.name}"
    ext = file.name.split('.')[-1].lower()
    content_type_map = {
        "pdf": "application/pdf",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "mp4": "video/mp4",
    }
    headers = {"Content-Type": content_type_map.get(ext, "application/octet-stream")}
    
    try:
        bucket.put_object(file_name, file.getvalue(), headers=headers)
        return f"{ENDPOINT}/{file_name}"
    except Exception as e:
        st.error(f"❌ 上传失败: {e}")
        return None 