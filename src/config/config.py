import os
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional

# 加载环境变量
load_dotenv()

@dataclass
class OSSConfig:
    """OSS配置"""
    access_key_id: str
    access_key_secret: str
    bucket_name: str
    endpoint: str
    region: str

@dataclass
class APIConfig:
    """API配置"""
    api_key: str
    api_base: Optional[str] = None
    model_name: str = "qwen-max"

@dataclass
class AppConfig:
    """应用配置"""
    debug: bool = False
    cache_ttl: int = 3600
    max_upload_size: int = 50 * 1024 * 1024  # 50MB
    allowed_extensions: tuple = ('.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png')

class Config:
    """配置管理类"""
    def __init__(self):
        # OSS配置
        self.oss = OSSConfig(
            access_key_id=os.getenv('ACCESS_KEY_ID', ''),
            access_key_secret=os.getenv('ACCESS_KEY_SECRET', ''),
            bucket_name=os.getenv('BUCKET_NAME', ''),
            endpoint=os.getenv('OSS_ENDPOINT', ''),
            region=os.getenv('REGION', '')
        )
        
        # API配置
        self.api = APIConfig(
            api_key=os.getenv('API_KEY', ''),
            api_base=os.getenv('API_BASE', None),
            model_name=os.getenv('MODEL_NAME', 'qwen-max')
        )
        
        # 应用配置
        self.app = AppConfig(
            debug=os.getenv('DEBUG', 'False').lower() == 'true',
            cache_ttl=int(os.getenv('CACHE_TTL', 3600)),
            max_upload_size=int(os.getenv('MAX_UPLOAD_SIZE', 50 * 1024 * 1024)),
            allowed_extensions=tuple(os.getenv('ALLOWED_EXTENSIONS', 
                '.pdf,.doc,.docx,.txt,.jpg,.jpeg,.png').split(','))
        )
    
    def validate(self):
        """验证配置完整性"""
        # 验证OSS配置
        if not all([self.oss.access_key_id, self.oss.access_key_secret, 
                   self.oss.bucket_name, self.oss.endpoint]):
            raise ValueError("OSS配置不完整，请检查环境变量")
        
        # 验证API配置
        if not self.api.api_key:
            raise ValueError("API密钥未配置，请检查环境变量")
        
        return True

# 创建全局配置实例
config = Config() 