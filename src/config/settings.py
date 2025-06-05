import os
from dotenv import load_dotenv

# 环境变量读取
load_dotenv()

# OSS配置
ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID")
ACCESS_KEY_SECRET = os.getenv("ACCESS_KEY_SECRET")
BUCKET_NAME = os.getenv("BUCKET_NAME")
REGION = os.getenv("REGION")
ENDPOINT = f"https://{BUCKET_NAME}.oss-{REGION}.aliyuncs.com"

# API配置
API_KEY = os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen-vl-plus")
BASE_URL = os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

# 管理员配置
ADMIN_PASSWORD = "00277"  # 在实际项目中应该使用更安全的方式存储

# UI配置
MOBILE_BREAKPOINT = 768  # 移动端断点像素值 