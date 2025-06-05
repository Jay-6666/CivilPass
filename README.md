# 公考助手 (Civil Service Exam Assistant)

一个基于Streamlit的公务员考试辅助系统，提供智能问答、考试日历、备考资料、政策资讯等功能。

## 功能特点

- 🤖 **智能问答**：基于千问API的智能问答系统，支持文本和图片输入
- 📅 **考试日历**：可视化的考试日程管理，支持日期筛选和提醒设置
- 📚 **备考资料**：提供各类备考资料，支持在线预览和下载
- 📰 **政策资讯**：实时更新的公考政策动态
- 🌟 **高分经验**：来自高分考生的经验分享
- 👨‍💼 **管理后台**：便捷的资料管理系统

## 项目结构

```
streamlit_civilpass/
├── src/
│   ├── modules/         # 功能模块
│   ├── utils/          # 工具函数
│   └── config/         # 配置文件
├── static/             # 静态资源
├── app.py             # 主程序
├── requirements.txt   # 依赖包
└── README.md         # 项目说明
```

## 环境要求

- Python 3.8+
- Streamlit 1.10+
- 其他依赖见 requirements.txt

## 安装步骤

1. 克隆项目：
```bash
git clone https://github.com/yourusername/streamlit_civilpass.git
cd streamlit_civilpass
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
创建 `.env` 文件并填入以下配置：
```
ACCESS_KEY_ID=your_access_key_id
ACCESS_KEY_SECRET=your_access_key_secret
BUCKET_NAME=your_bucket_name
REGION=your_region
API_KEY=your_api_key
```

4. 运行项目：
```bash
streamlit run app.py
```

## 使用说明

1. 访问 http://localhost:8501 打开应用
2. 在侧边栏选择需要使用的功能
3. 根据界面提示进行操作

## 贡献指南

1. Fork 本仓库
2. 创建新分支：`git checkout -b feature/AmazingFeature`
3. 提交改动：`git commit -m 'Add some AmazingFeature'`
4. 推送分支：`git push origin feature/AmazingFeature`
5. 提交 Pull Request

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 联系方式

- 项目作者：Your Name
- 邮箱：your.email@example.com
- 项目链接：https://github.com/yourusername/streamlit_civilpass 