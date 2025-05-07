import base64
import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from io import BytesIO

import jinja2
import matplotlib.pyplot as plt
import networkx as nx
import openai
import oss2
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import torch
from dotenv import load_dotenv
from matplotlib import font_manager
from PIL import Image
from pyvis.network import Network
from streamlit.runtime.scriptrunner import get_script_run_ctx

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


# 添加设备检测函数
def is_mobile():
    """通过浏览器 User-Agent 自动检测移动端设备"""
    try:
        ctx = get_script_run_ctx()
        if ctx is None:
            return False
        user_agent = ctx.request.headers.get("User-Agent", "").lower()
        return any(keyword in user_agent for keyword in ["mobi", "android", "iphone"])
    except Exception:
        return False  # 异常时默认返回非移动端


# 夜晚模式
def set_dark_mode(dark: bool):
    if dark:
        st.markdown(
            """
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
        """,
            unsafe_allow_html=True,
        )


# 消息气泡 UI
def chat_message(message, is_user=True):
    avatar = "🧑‍💻" if is_user else "🤖"
    alignment = "flex-end" if is_user else "flex-start"
    bg_color = "#0E76FD" if is_user else "#2E2E2E"
    text_color = "#FFFFFF" if is_user else "#DDDDDD"

    st.markdown(
        f"""
        <div style='display: flex; justify-content: {alignment}; margin: 10px 0;'>
            <div style='background-color: {bg_color}; color: {text_color}; padding: 10px 15px;
                        border-radius: 12px; max-width: 70%;'>
                <strong>{avatar}</strong> {message}
            </div>
        </div>
    """,
        unsafe_allow_html=True,
    )


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
        ".mp4": "video/mp4",
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
    """调用千问 API，要求 AI 用自然语言回答 + 追加 JSON 格式知识图谱，支持图文输入"""
    client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL)

    # 更自然的系统提示词（无 markdown / 无列表）
    system_prompt = """
你是公务员考试领域的专家，请针对用户提出的问题，像专家讲解一样，用自然、连贯的语言进行清晰解答。

要求：
1. 使用自然书面语言，逻辑通顺、语言简洁，无需使用 markdown、标题、编号或列表等格式符号。
2. 回答完毕后，请追加输出一个结构清晰的“知识图谱”数据（使用 JSON 格式）。

知识图谱数据格式如下：
```json
{
  "knowledge_graph": {
    "nodes": [
      {"id": 1, "label": "核心概念", "description": "...", "color": "#4CAF50"},
      {"id": 2, "label": "相关法规", "description": "...", "shape": "diamond"}
    ],
    "edges": [
      {"from": 1, "to": 2, "relation": "依据", "width": 2}
    ]
  }
}
请严格按照上述格式返回。 """

    # 关键词判断图形推理题，追加图形专属提示
    graphic_keywords = ["图形", "规律", "边数", "颜色", "旋转", "对称", "排列"]
    if any(kw in user_input for kw in graphic_keywords):
        system_prompt += """
    本题属于【图形推理类】，请在构建知识图谱时，考虑如下维度：

    节点应包括：图形推理、形状变化、颜色规律、位置排列、对称性 等

    边的关系建议使用：“包含”“体现”“遵循”“变化为” 等清晰语义

    所有节点尽量有说明字段（description），便于理解

    构建一个结构严谨、内容完整的图形推理知识图谱。 """

    try:
        # 构建消息结构
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": []},
        ]

        if user_input:
            messages[1]["content"].append({"type": "text", "text": user_input})
        if image_url:
            messages[1]["content"].append(
                {"type": "image_url", "image_url": {"url": image_url}}
            )

        # 调用千问模型
        completion = client.chat.completions.create(model=MODEL_NAME, messages=messages)
        return completion.choices[0].message.content

    except Exception as e:
        return f"❌ AI 解析失败: {str(e)}"


import json
import re


# 拆分回答文本 和 图谱 JSON 部分
def split_answer_and_graph(raw_output):
    pattern = r"```json(.*?)```"
    match = re.search(pattern, raw_output, re.DOTALL)

    if match:
        json_block = match.group(1).strip()
        text_part = raw_output[: match.start()].strip()
        return text_part, json_block
    else:
        return raw_output.strip(), None


# 自然语言回答展示组件（可滚动）
def show_answer_scrollable(answer):
    st.markdown(
        f"""
        <div style="max-height: 400px; overflow-y: auto; padding: 12px; border: 1px solid #ccc; background-color: #fdfdfd; border-radius: 6px;">
            <p style="line-height: 1.6; font-size: 16px;">{answer}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


import hanlp

hanlp_pipeline = hanlp.load("FINE_ELECTRA_SMALL_ZH")  # 中文 NER 模型


def extract_knowledge_graph(answer):
    """
    若是图形推理类问题，构建专属图谱；否则使用实体识别构建通用图谱。
    """

    # Step 1：尝试解析 AI 自带的知识图谱
    try:
        pattern = r"```json(.*?)```"
        match = re.search(pattern, answer, re.DOTALL)
        if match:
            kg_data = json.loads(match.group(1).strip())
            return (
                kg_data["knowledge_graph"]["nodes"],
                kg_data["knowledge_graph"]["edges"],
            )
    except Exception as e:
        pass  # 不展示 warning，交给后续自动生成

    # Step 2：判断是否是图形推理类问题
    graphic_keywords = ["图形", "推理", "变化", "颜色", "边数", "规律", "对称", "旋转", "排列"]
    if any(kw in answer for kw in graphic_keywords):
        # Step 3：构建图形推理专用知识图谱
        nodes = [
            {
                "id": 1,
                "label": "图形推理",
                "description": "通过图形规律推断结果",
                "color": "#4CAF50",
                "shape": "star",
            },
            {
                "id": 2,
                "label": "形状变化",
                "description": "边数/结构的变化模式",
                "color": "#03A9F4",
                "shape": "box",
            },
            {
                "id": 3,
                "label": "颜色规律",
                "description": "颜色轮换/重复/渐变",
                "color": "#FFC107",
                "shape": "triangle",
            },
            {
                "id": 4,
                "label": "位置排列",
                "description": "图形在空间位置的变化",
                "color": "#E91E63",
                "shape": "diamond",
            },
            {
                "id": 5,
                "label": "对称性",
                "description": "轴对称/中心对称等形式",
                "color": "#9C27B0",
                "shape": "ellipse",
            },
        ]
        edges = [
            {"from": 1, "to": 2, "relation": "包含"},
            {"from": 1, "to": 3, "relation": "包含"},
            {"from": 1, "to": 4, "relation": "包含"},
            {"from": 1, "to": 5, "relation": "包含"},
        ]
        return nodes, edges

    # Step 4：非图形推理题，回退 HanLP NER 模式
    ner_result = hanlp_pipeline(answer)
    entities = ner_result.get("ner/msra", [])
    if not entities:
        return [], []

    entity_types = {"PER": "人物", "ORG": "组织", "LOC": "地点", "TIME": "时间"}
    shape_map = {"PER": "dot", "ORG": "box", "LOC": "triangle", "TIME": "ellipse"}
    color_map = {
        "PER": "#03a9f4",
        "ORG": "#4caf50",
        "LOC": "#ff9800",
        "TIME": "#ab47bc",
    }

    nodes = []
    node_id_map = {}
    for idx, (text, ent_type, start, end) in enumerate(entities):
        node_id = idx + 1
        nodes.append(
            {
                "id": node_id,
                "label": text,
                "description": f"{entity_types.get(ent_type, '实体')}：{text}",
                "color": color_map.get(ent_type, "#9e9e9e"),
                "shape": shape_map.get(ent_type, "ellipse"),
                "group": ent_type,
                "size": 28,
            }
        )
        node_id_map[text] = node_id

    # 简单共现关系构建
    edges = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            edges.append(
                {
                    "from": nodes[i]["id"],
                    "to": nodes[j]["id"],
                    "relation": "共现",
                    "color": "#ccc",
                    "width": 1,
                }
            )

    return nodes, edges


from pyvis.network import Network


def generate_kg_html(nodes, edges):
    net = Network(height="550px", width="100%", bgcolor="#ffffff", font_color="#333")

    # 高级美化设置
    net.set_options(
        """
    {
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -2500,
          "centralGravity": 0.3,
          "springLength": 200,
          "springConstant": 0.04,
          "damping": 0.09
        }
      },
      "interaction": {
        "hover": true,
        "navigationButtons": true,
        "tooltipDelay": 200
      },
      "nodes": {
        "font": {"size": 16, "face": "arial"},
        "shadow": true
      },
      "edges": {
        "color": {"inherit": true},
        "smooth": true
      }
    }
    """
    )

    for node in nodes:
        net.add_node(
            n_id=node.get("id"),
            label=node.get("label"),
            title=node.get("description", "无详细说明"),
            color=node.get("color", "#4CAF50"),
            shape=node.get("shape", "ellipse"),
            group=node.get("group", None),
            size=node.get("size", 25),
        )

    for edge in edges:
        net.add_edge(
            edge.get("from"),
            edge.get("to"),
            title=edge.get("relation", "关联"),
            width=edge.get("width", 1),
            color=edge.get("color", "#aaa"),
            arrows="to" if edge.get("direction", False) else "",
        )

    return net.generate_html()


# 智能问答模块
def showLLMChatbot():
    st.title("📝 智能公考助手")
    st.caption("📢 输入你的问题，或批阅申论作文，AI帮你搞定！")
    st.markdown("---")

    tabs = st.tabs(["🤖 智能问答", "📝 申论批阅"])

    with tabs[0]:  # 智能问答
        show_normal_chat()

    with tabs[1]:  # 申论批阅
        show_essay_review()


def show_normal_chat():

    # 初始化会话状态
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_input" not in st.session_state:
        st.session_state.current_input = ""
    if "editing_index" not in st.session_state:
        st.session_state.editing_index = -1

    # 聊天记录容器
    chat_container = st.container()

    # 自定义响应式CSS
    st.markdown(
        """
    <style>
    /* 基础布局 */
    .main .block-container {
        padding-bottom: 180px !important;
    }

    /* 桌面端固定输入区域 */
    @media (min-width: 768px) {
        div[data-testid="stHorizontalBlock"]:has(> div:last-child:has(button[kind="primary"])) {
            position: fixed !important;
            bottom: 30px;
            left: 2rem;
            right: 2rem;
            padding: 1rem;
            box-shadow: 0 -4px 12px rgba(0,0,0,0.1);
            border-radius: 12px;
            background: white;
            z-index: 999;
            border: 1px solid #eee;
        }
    }

    /* 移动端布局优化 */
    @media (max-width: 767px) {
        /* 调整聊天消息间距 */
        .stChatMessage {
            padding: 0.5rem !important;
            margin: 0.5rem 0 !important;
        }

        /* 输入区域全宽显示 */
        div[data-testid="column"] {
            width: 100% !important;
            padding: 0 !important;
        }

        /* 按钮触控优化 */
        button {
            padding: 0.8rem !important;
            min-height: 3rem !important;
        }

        /* 文本输入框优化 */
        .stTextInput input {
            font-size: 16px !important;  /* 防止iOS缩放 */
            padding: 12px !important;
        }

        /* 文件上传器优化 */
        .stFileUploader {
            margin-top: 0.5rem !important;
        }

        /* 隐藏桌面端编辑按钮 */
        .mobile-edit-btn {
            display: block !important;
        }
        .desktop-edit-btn {
            display: none !important;
        }
    }

    /* 通用优化 */
    img {
        max-width: 100% !important;  /* 图片响应式 */
    }

    /* 复制按钮优化 */
    .stCodeBlock button {
        min-width: 36px !important;
        min-height: 36px !important;
    }
    <style>
    /* 知识图谱容器 */
    .pyvis-network {
        border: 1px solid #eee !important;
        border-radius: 10px;
        margin: 1rem 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }

    /* 节点样式 */
    .node {
        transition: all 0.3s ease !important;
    }
    .node:hover {
        filter: brightness(1.1);
        transform: scale(1.05);
    }

    /* 移动端优化 */
    @media (max-width: 767px) {
        .pyvis-network {
            height: 300px !important;
        }
        .node-label {
            font-size: 12px !important;
        }
    }

    /* 展开面板动画 */
    .streamlit-expanderContent {
        animation: kgSlideIn 0.3s ease-out;
    }

    @keyframes kgSlideIn {
        0% { opacity: 0; transform: translateY(-10px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # 显示聊天记录
    with chat_container:
        for index, message in enumerate(st.session_state.messages):
            role = message["role"]
            content = message["content"]
            image_url = message.get("image_url")

            # 响应式列布局
            cols = st.columns([0.85, 0.15])
            with cols[0]:
                with st.chat_message(role):
                    if role == "assistant":
                        text_part, kg_json_str = split_answer_and_graph(content)
                        show_answer_scrollable(text_part)

                        if kg_json_str:
                            try:
                                kg_data = json.loads(kg_json_str)
                                nodes = kg_data["knowledge_graph"]["nodes"]
                                edges = kg_data["knowledge_graph"]["edges"]
                                st.markdown("### 📊 关联知识图谱")
                                with st.expander("点击探索知识点关系", expanded=False):
                                    kg_html = generate_kg_html(nodes, edges)
                                    components.html(kg_html, height=400)
                            except Exception as e:
                                st.warning("❌ 知识图谱结构解析失败")

                    if image_url and role == "user":
                        st.image(image_url, caption="🖼 已上传图片", use_container_width=True)

            # 编辑按钮
            if role == "user":
                with cols[1]:
                    btn_style = "mobile-edit-btn" if is_mobile() else "desktop-edit-btn"
                    if st.button(
                            "✏️",
                            key=f"edit_{index}",
                            help="编辑此问题",
                            use_container_width=True,
                            type="secondary",
                    ):
                        st.session_state.current_input = content
                        st.session_state.editing_index = index

    # 输入区域容器
    input_container = st.container()
    with input_container:
        # 响应式列布局
        col1, col2 = st.columns([2, 1]) if not is_mobile() else st.columns([1])

        with col1:
            info = st.text_input(
                "✍️ 问题输入",
                placeholder="请输入您的问题...",
                value=st.session_state.current_input,
                key="user_input",
                label_visibility="visible" if not is_mobile() else "collapsed",
            )

        # 移动端独立显示上传按钮
        if is_mobile():
            with st.container():
                uploaded_file = st.file_uploader(
                    "📷 上传试题图片", type=["jpg", "png", "jpeg"], key="mobile_uploader"
                )
        else:
            with col2:
                uploaded_file = st.file_uploader(
                    "📷 上传试题图片", type=["jpg", "png", "jpeg"], key="desktop_uploader"
                )

        # 提交按钮
        submit = st.button("🚀 获取 AI 答案", use_container_width=True, type="primary")

    # 图片上传处理
    image_url = None
    if uploaded_file:
        with st.spinner("🔄 正在上传图片..."):
            image_url = upload_file_to_oss(uploaded_file, category="civilpass/images")
        if image_url:
            st.success("✅ 图片上传成功！")

    # 处理提交逻辑
    if submit:
        if not info and not image_url:
            st.warning("⚠️ 请填写问题或上传图片")
        else:
            # 处理编辑模式
            if st.session_state.editing_index != -1:
                del st.session_state.messages[st.session_state.editing_index:]
                st.session_state.editing_index = -1

            # 添加用户消息
            user_content = info if info else "（仅上传图片）"
            user_message = {
                "role": "user",
                "content": user_content,
                "image_url": image_url,
            }
            st.session_state.messages.append(user_message)

            # 获取AI响应
            with st.spinner("🤖 AI 解析中..."):
                answer = query_qwen_api(user_content, image_url)

            # 添加AI消息
            ai_message = {"role": "assistant", "content": answer}
            st.session_state.messages.append(ai_message)

            # 重置输入状态
            st.session_state.current_input = ""
            st.session_state.uploaded_file = None
            st.rerun()


# from PIL import Image
# import pdfplumber
# import docx
# from paddleocr import PaddleOCR
# import numpy as np

# # 初始化OCR（放在文件开头）
# ocr_model = PaddleOCR(
#     use_angle_cls=False,
#     lang='ch',
#     det_model_dir='./models/ch_PP-OCRv4_det_infer',  # 本地检测模型路径
#     rec_model_dir='./models/ch_PP-OCRv4_rec_infer'   # 本地识别模型路径
# )


def show_essay_review():
    st.subheader("✍️ 申论作文批阅")

    tabs = st.tabs(["🖊️ 输入文本", "📄 上传图片/文件"])

    with tabs[0]:
        essay_text = st.text_area("请输入你的申论作文", height=300, placeholder="粘贴或输入完整的作文...")

        if st.button("🚀 提交批阅", key="submit_text"):
            process_essay(essay_text)

    with tabs[1]:
        uploaded_file = st.file_uploader("上传申论作文图片或文件", type=["jpg", "jpeg", "png", "pdf", "docx"])

        if uploaded_file:
            # ✅ 新增：如果是图片，先压缩尺寸
            if uploaded_file.type.startswith("image/"):
                image = Image.open(uploaded_file)
                max_width = 1200
                if image.width > max_width:
                    ratio = max_width / image.width
                    new_size = (max_width, int(image.height * ratio))
                    image = image.resize(new_size)
                    # 把压缩后的图片存回 uploaded_file 变量
                    # 这里要用BytesIO再转成文件对象
                    from io import BytesIO
                    buffered = BytesIO()
                    image.save(buffered, format="JPEG")
                    buffered.seek(0)
                    uploaded_file = buffered  # 重新赋值！

            # 下面继续原来的提取文本流程
            file_text = extract_text_from_file(uploaded_file)

            if file_text:
                st.success("✅ 文件识别成功，可以进行批阅")
                st.text_area("📋 识别到的文本（可修改后批阅）", value=file_text, height=300, key="recognized_text")

                if st.button("🚀 提交批阅", key="submit_file"):
                    process_essay(file_text)
            else:
                st.error("❌ 文件识别失败，请上传清晰的图片或标准文档")


def extract_text_from_file(file):
    file_type = file.type

    try:
        if "image" in file_type:
            # 图片文件
            image = Image.open(file)
            result = ocr_model.ocr(np.array(image), cls=True)
            text = "\n".join([line[1][0] for line in result[0]])
            return text

        elif "pdf" in file_type:
            # PDF文件
            with pdfplumber.open(file) as pdf:
                pages = [page.extract_text() for page in pdf.pages]
            return "\n".join(pages)

        elif "officedocument" in file_type:
            # Word 文件 (docx)
            doc = docx.Document(file)
            return "\n".join([p.text for p in doc.paragraphs])

        else:
            return None
    except Exception as e:
        st.error(f"识别出错: {e}")
        return None


def process_essay(text):
    if not text.strip():
        st.warning("⚠️ 内容为空")
        return

    with st.spinner("🧠 正在批阅并优化中，请稍候..."):
        history = improve_until_pass(text, target_score=90, max_rounds=5)

    if history:
        final = history[-1]

        st.success(f"✅ 优化完成！最终得分：{final['total_score']} 分")

        st.info("🔄 以下为自动优化后的最终最优版作文：")

        st.markdown("### 📜 优化后作文")
        st.markdown(final['essay'])

        st.markdown("### 📊 得分维度（细分项）")
        if final['scores']:
            st.bar_chart(final['scores'])
        else:
            st.warning("⚠️ 最终未能成功提取每个维度得分，请检查批阅格式")

        st.markdown("### 📑 批阅反馈详情")
        st.markdown(final['feedback'])


def improve_until_pass(initial_essay, target_score=90, max_rounds=1):
    """
    只改进一次申论作文，达标或不达标都直接返回最终结果。
    """
    essay = initial_essay

    # 第一次批阅
    feedback = review_essay(essay)
    scores = extract_scores(feedback)
    total_score = sum(scores.values()) if scores else 0

    if total_score >= target_score:
        # 如果一开始就达标，直接返回
        return [{
            "round": 1,
            "essay": essay,
            "feedback": feedback,
            "scores": scores,
            "total_score": total_score,
        }]
    else:
        # 如果没达标，进行一次优化
        improved_essay = optimize_essay(essay, feedback)

        # 再次批阅优化后的作文
        feedback2 = review_essay(improved_essay)
        scores2 = extract_scores(feedback2)
        total_score2 = sum(scores2.values()) if scores2 else 0

        # 返回第一次优化后的最终结果（无论是否达标）
        return [{
            "round": 1,
            "essay": improved_essay,
            "feedback": feedback2,
            "scores": scores2,
            "total_score": total_score2,
        }]


def review_essay(essay):
    client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL)

    system_prompt = """
你是一位专业的申论考试批阅专家。

请按照以下标准（各维度细则）对考生作文进行严格打分。每个小项必须单独给出得分。
要求输出格式标准规范，方便提取。

【内容维度】（40分）：
- 切题程度（10分）
- 思想深度（15分）
- 论据质量（15分）

【结构维度】（20分）：
- 整体布局（8分）
- 段落安排（6分）
- 开头结尾（6分）

【语言维度】（30分）：
- 语言规范（10分）
- 表达流畅（10分）
- 风格得体（10分）

【书写维度】（10分）：
- 字迹工整（4分）
- 卷面整洁（3分）
- 字数符合（3分）

输出要求：
- 每个小项得分清晰列出
- 最后给出总得分（满分100分）
- 必须严格根据标准细则评判，不要随意满分。

下面是考生作文，请进行全面批阅和打分：
"""

    user_prompt = f"{essay}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            stream=True  # ✅ 开启流式输出
        )

        # Streamlit实时展示
        collected_content = ""

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_message = ""

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    partial = chunk.choices[0].delta.content
                    full_message += partial
                    message_placeholder.markdown(full_message + "▌")  # 实时动态输出

            message_placeholder.markdown(full_message)  # 最终补齐

        return full_message

    except Exception as e:
        return f"❌ 批阅失败：{str(e)}"


def optimize_essay(essay, feedback):
    client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL)

    system_prompt = """
你是一名申论写作专家，请根据批阅反馈内容，优化和提升考生作文，使其尽可能达到满分标准。

要求：
- 保持原文主题不变。
- 针对批阅反馈指出的不足（如内容深度、论据质量、结构安排、语言规范等方面）进行改进。
- 优化后的文章应更符合评分标准，避免原有问题。
- 字数保持合理，语言符合申论文风。

请只返回优化后的完整作文正文。
"""

    user_prompt = f"""
【考生原文】：
{essay}

【批阅反馈】：
{feedback}

请在以上基础上进行全面优化。
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            stream=True
        )

        collected_content = ""

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_message = ""

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    partial = chunk.choices[0].delta.content
                    full_message += partial
                    message_placeholder.markdown(full_message + "▌")

            message_placeholder.markdown(full_message)

        return full_message

    except Exception as e:
        return f"❌ 优化失败：{str(e)}"


def extract_scores(feedback_text):
    """
    从批阅反馈中提取细项得分，增强版，兼容各种小变动
    """
    import re

    small_items = [
        "切题程度", "思想深度", "论据质量",
        "整体布局", "段落安排", "开头结尾",
        "语言规范", "表达流畅", "风格得体",
        "字迹工整", "卷面整洁", "字数符合",
    ]

    extracted_scores = {}

    for item in small_items:
        # 支持得9分，也支持直接9分，支持各种冒号
        pattern = rf"{item}（\d+分）[:：]?\s*(?:得)?(\d+)"
        match = re.search(pattern, feedback_text)
        if match:
            extracted_scores[item] = int(match.group(1))

    return extracted_scores if extracted_scores else None


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
                    st.image(
                        BytesIO(file_data), caption=file_name, use_container_width=True
                    )

                st.markdown(f"[📥 下载]({file_url})")
                st.markdown("---")
                count += 1
        except Exception as e:
            st.error(f"❌ 加载失败：{e}")


# 政策资讯模块
def display_policy_news():
    st.title("📰 政策资讯")
    st.caption("📢 最新公务员政策动态与权威解读")
    st.markdown("---")

    @st.cache_data(ttl=3600, show_spinner="正在加载最新政策资讯...")
    def load_all_policy_data():
        # 配置参数（可提取到配置文件）
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
                    df = pd.read_csv(
                        BytesIO(csv_data),
                        parse_dates=["date"],
                        usecols=REQUIRED_COLUMNS,
                    )

                    # 字段校验
                    missing_cols = set(REQUIRED_COLUMNS) - set(df.columns)
                    if missing_cols:
                        raise ValueError(f"缺少必要字段：{', '.join(missing_cols)}")

                    # 添加数据源标识
                    df["data_source"] = file_path.split("/")[-1]  # 记录文件名

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
            combined_df = (
                combined_df.dropna(subset=["title", "url"])
                .drop_duplicates("url", keep="first")
                .sort_values("date", ascending=False)
                .reset_index(drop=True)
            )

            return combined_df

        except Exception as e:
            st.error(f"❌ 目录访问失败：{str(e)}")
            return pd.DataFrame()
        finally:
            # 显示加载错误信息
            if error_files:
                with st.expander("⚠️ 部分文件加载失败"):
                    for file, err in error_files:
                        st.markdown(f"`{file}`: {err}")

    df = load_all_policy_data()
    if df.empty:
        st.warning("⚠️ 当前无可用政策数据")
        return

    if "current_page" not in st.session_state:
        st.session_state.current_page = 1

    with st.expander("🔍 智能筛选", expanded=True):
        col1, col2 = st.columns([2, 3])
        with col1:
            date_range = st.date_input(
                "📅 日期范围",
                value=(df["date"].min().date(), df["date"].max().date()),
                format="YYYY/MM/DD",
            )
            sources = st.multiselect(
                "🏛️ 信息来源", options=df["source"].unique(), placeholder="全部来源"
            )
        with col2:
            keyword = st.text_input(
                "🔎 关键词搜索", placeholder="标题/内容关键词（支持空格分隔多个关键词）", help="示例：公务员 待遇 调整"
            )
            regions = st.multiselect(
                "🌍 相关地区", options=df["region"].unique(), placeholder="全国范围"
            )

    sort_col, _ = st.columns([1, 2])
    with sort_col:
        sort_option = st.selectbox(
            "排序方式", options=["最新优先", "最旧优先", "热度排序", "来源分类"], index=0
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
                filtered["title"].str.contains(pattern, case=False)
                | filtered["summary"].str.contains(pattern, case=False)
                ]
        if sort_option == "最新优先":
            return filtered.sort_values("date", ascending=False)
        elif sort_option == "最旧优先":
            return filtered.sort_values("date", ascending=True)
        elif sort_option == "热度排序":
            return filtered.sort_values("hotness", ascending=False)
        else:
            return filtered.sort_values(["source", "date"], ascending=[True, False])

    processed_df = process_data(df)

    PAGE_SIZE = 5
    total_items = len(processed_df)
    total_pages = max(1, (total_items + PAGE_SIZE - 1) // PAGE_SIZE)

    # 翻页按钮
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
            unsafe_allow_html=True,
        )

    # 页码重置逻辑
    if st.session_state.current_page > total_pages:
        st.session_state.current_page = total_pages

    start_idx = (st.session_state.current_page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    current_data = processed_df.iloc[start_idx:end_idx]

    if current_data.empty:
        st.warning("😢 未找到符合条件的资讯")
    else:
        st.markdown(
            f"""
            <div style="background: #f0f2f6; padding: 12px; border-radius: 8px; margin: 10px 0;">
                📊 找到 <strong>{len(processed_df)}</strong> 条结果 | 
                📅 时间跨度：{date_range[0]} 至 {date_range[1]} | 
                🌟 平均热度值：{processed_df['hotness'].mean():.1f}
            </div>
        """,
            unsafe_allow_html=True,
        )

        for _, row in current_data.iterrows():
            with st.container(border=True):
                # 响应式列布局
                col1, col2 = st.columns([4, 1], gap="small")

                with col1:
                    # 增强型可点击标题
                    st.markdown(
                        f"""
                        <a href="{row['url']}" target="_blank" 
                            style="text-decoration: none;
                                   color: inherit;
                                   display: block;
                                   padding: 8px 0;">
                            <h3 style="margin: 0;
                                      font-size: 1.2rem;
                                      line-height: 1.4;
                                      border-bottom: 2px solid #eee;
                                      padding-bottom: 8px;">
                                {row['title']}
                            </h3>
                        </a>
                    """,
                        unsafe_allow_html=True,
                    )

                    meta_cols = st.columns([2, 2, 2], gap="small")
                    with meta_cols[0]:
                        st.markdown(f"📅 **日期**: {row['date'].strftime('%Y/%m/%d')}")
                    with meta_cols[1]:
                        st.markdown(f"🏛️ **来源**: {row['source']}")
                    with meta_cols[2]:
                        st.markdown(f"🌍 **地区**: {row['region']}")
                    with st.expander("📝 查看摘要"):
                        st.write(row["summary"])
                with col2:
                    st.markdown(
                        f"""
                        <div class="btn-group">
                            <div class="hotness-value">
                                🔥 {row['hotness']}
                            </div>
                            <div class="btn-group-mobile">
                                <a href="{row['url']}" 
                                   target="_blank" 
                                   class="policy-btn btn-primary">
                                    🔗 查看原文
                                </a>
                                <button onclick="alert('收藏功能需登录后使用')" 
                                        class="policy-btn btn-secondary">
                                    ⭐ 收藏
                                </button>
                            </div>
                        </div>
                    """,
                        unsafe_allow_html=True,
                    )

    with st.expander("📈 数据洞察", expanded=False):
        tab1, tab2, tab3 = st.tabs(["来源分析", "时间趋势", "地区分布"])

        with tab1:
            source_counts = processed_df["source"].value_counts().head(10)
            st.bar_chart(source_counts)

        with tab2:
            time_series = processed_df.set_index("date").resample("W").size()
            st.area_chart(time_series)

        with tab3:
            region_counts = processed_df["region"].value_counts()
            fig, ax = plt.subplots(figsize=(8, 8))
            plt.rcParams["font.sans-serif"] = ["SimHei"]
            plt.rcParams["axes.unicode_minus"] = False
            region_counts.plot.pie(autopct="%1.1f%%", ax=ax)
            ax.set_ylabel("")
            st.pyplot(fig)

        st.download_button(
            label="📥 导出当前结果（CSV）",
            data=processed_df.to_csv(index=False).encode("utf-8"),
            file_name=f"policy_news_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            help="导出当前筛选条件下的所有结果",
        )

    # 移动端优化样式
    st.markdown(
        """
        <style>
            /* 通用按钮样式 */
            .policy-btn {
                display: block;
                width: 100%;
                padding: 8px;
                border-radius: 20px;
                text-decoration: none;
                text-align: center;
                transition: all 0.3s;
                margin: 6px 0;
                font-size: 0.9rem;
            }

            .hotness-value {
                font-size: 1.2rem; 
                color: #ff4b4b;
                margin: 8px 0;
                text-align: center;
            }

            /* 桌面端优化 */
            @media (min-width: 769px) {
                .btn-group {
                    display: flex;
                    flex-direction: column;
                    gap: 8px;
                }
                .policy-btn {
                    padding: 8px 16px;
                }
            }

            /* 移动端优化 */
            @media (max-width: 768px) {
                .btn-group-mobile {
                    display: flex;
                    flex-direction: column;
                    gap: 4px;
                }

                .policy-btn {
                    font-size: 0.85rem;
                    padding: 8px 12px;
                }

                .hotness-value {
                    font-size: 1rem !important;
                }

                /* 保持原有移动端优化 */
                .stContainer {
                    padding: 0 8px !important;
                }
                h3 {
                    font-size: 1.1rem !important;
                    line-height: 1.3 !important;
                }
                [data-testid="column"] {
                    padding: 4px !important;
                }
                a[target="_blank"] {
                    padding: 16px 0 !important;
                    margin: -16px 0 !important;
                    display: block !important;
                }
            }

            /* 主题配色 */
            .btn-primary {
                background: #007bff;
                color: white !important;
                border: 1px solid #007bff;
            }

            .btn-secondary {
                background: #28a745;
                color: white !important;
                border: 1px solid #28a745;
            }

            /* 交互效果 */
            .policy-btn:hover {
                opacity: 0.9;
                transform: translateY(-1px);
                box-shadow: 0 2px 6px rgba(0,0,0,0.1);
            }
            a:active, button:active {
                transform: scale(0.95) !important;
            }
        </style>
    """,
        unsafe_allow_html=True,
    )


# 高分经验模块
def display_experience():
    st.title("🌟 高分经验")
    st.caption("📢 来自高分考生的真实经验分享")
    st.markdown("---")

    # 用户上传功能区
    with st.expander("📤 上传我的学习资料", expanded=False):
        # 创建两列布局
        col_upload, col_desc = st.columns([2, 3])

        with col_upload:
            upload_type = st.radio(
                "选择上传类型", ["学习笔记", "错题集"], horizontal=True, help="请选择资料分类"
            )

            uploaded_files = st.file_uploader(
                "选择文件",
                type=["pdf", "jpg", "jpeg", "png"],
                accept_multiple_files=True,
                help="支持格式：PDF/图片",
            )

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

    # 公共显示函数
    def display_files(prefix, tab):
        try:
            file_list = []
            for obj in oss2.ObjectIterator(bucket, prefix=prefix):
                if not obj.key.endswith("/"):
                    # 解析文件名（去除时间戳）
                    raw_name = obj.key.split("/")[-1]
                    display_name = "_".join(raw_name.split("_")[1:])  # 去掉时间戳

                    file_list.append(
                        {
                            "display": display_name,
                            "raw_name": raw_name,
                            "url": f"{ENDPOINT}/{obj.key}",
                            "type": "pdf"
                            if obj.key.lower().endswith(".pdf")
                            else "image",
                        }
                    )

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
                            st.image(
                                BytesIO(img_data),
                                use_container_width=True,
                                caption=file_info["display"],
                            )
                        else:
                            # PDF显示带文件名
                            st.markdown(f"📄 **{file_info['display']}**")
                            base64_pdf = base64.b64encode(
                                bucket.get_object(obj.key).read()
                            ).decode()
                            st.markdown(
                                f"""
                                <iframe 
                                    src="data:application/pdf;base64,{base64_pdf}"
                                    width="100%" 
                                    height="300px"
                                    style="border:1px solid #eee; border-radius:5px;">
                                </iframe>
                            """,
                                unsafe_allow_html=True,
                            )

                        # 下载按钮
                        st.markdown(
                            f"""
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
                        """,
                            unsafe_allow_html=True,
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


# 考试日历模块
def display_exam_calendar():
    st.title("📅 智能考试日历")
    st.markdown(
        "⚠️ <span style='color:red;'>考试时间仅供参考，请以官方公布为准！</span>", unsafe_allow_html=True
    )
    st.markdown("---")

    # 样式注入
    st.markdown(
        """
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
    """,
        unsafe_allow_html=True,
    )

    # 缓存数据加载
    @st.cache_data(ttl=3600, show_spinner="正在加载考试日历...")
    def load_calendar_data():
        try:
            # 加载结构化考试事件数据
            event_file = bucket.get_object("考试日历/events_date.json").read()
            events = json.loads(event_file)["events"]

            # 加载图片文件索引
            images = []
            for obj in oss2.ObjectIterator(bucket, prefix="考试日历/images/"):
                if obj.key.lower().endswith((".jpg", ".jpeg", ".png")):
                    images.append(
                        {
                            "key": obj.key,
                            "name": obj.key.split("/")[-1],
                            "url": f"{ENDPOINT}/{obj.key}",
                        }
                    )

            return {"events": sorted(events, key=lambda x: x["date"]), "images": images}

        except Exception as e:
            st.error(f"❌ 数据加载失败：{str(e)}")
            return {"events": [], "images": []}

    # 加载数据
    data = load_calendar_data()
    events = data["events"]
    images = data["images"]

    # 顶部过滤栏
    with st.container():
        col1, col2, col3 = st.columns([2, 3, 2])
        with col1:
            selected_year = st.selectbox(
                "选择年份",
                options=sorted(
                    {datetime.strptime(e["date"], "%Y-%m-%d").year for e in events},
                    reverse=True,
                ),
                index=0,
            )
        with col2:
            search_query = st.text_input("🔍 搜索考试名称或地区", placeholder="输入关键词筛选...")
        with col3:
            view_mode = "🗓 月历视图"  # 强制固定视图模式
            st.markdown(
                '<div style="visibility:hidden">占位</div>', unsafe_allow_html=True
            )

    # 过滤数据
    filtered_events = [
        e
        for e in events
        if datetime.strptime(e["date"], "%Y-%m-%d").year == selected_year
           and (
                   search_query.lower() in e["name"].lower()
                   or any(search_query.lower() in r.lower() for r in e["regions"])
           )
    ]

    # 展示内容
    if view_mode == "🗓 月历视图":
        tabs = st.tabs([f"{m}月" for m in range(1, 13)])

        monthly_events = defaultdict(list)
        for event in filtered_events:
            month = datetime.strptime(event["date"], "%Y-%m-%d").month
            monthly_events[month].append(event)

        for idx, tab in enumerate(tabs):
            month_num = idx + 1
            with tab:
                # 查找该月对应图片
                month_images = [
                    img
                    for img in images
                    if f"{selected_year}-{month_num:02}" in img["name"]
                ]

                if month_images:
                    cols = st.columns(2)
                    for img_idx, img in enumerate(month_images):
                        with cols[img_idx % 2]:
                            with st.popover(f"📷 {img['name'].split('.')[0]}"):
                                img_data = get_cached_oss_object(img["key"])
                                st.image(BytesIO(img_data), use_container_width=True)
                                st.download_button(
                                    "下载原图",
                                    data=img_data,
                                    file_name=img["name"],
                                    mime="image/jpeg",
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
                            if event.get("image"):
                                st.image(f"{ENDPOINT}/{event['image']}", width=120)

    # 侧边提醒栏
    with st.sidebar:
        st.header("🔔 提醒服务")
        selected_events = st.multiselect(
            "选择要提醒的考试",
            options=[e["name"] for e in filtered_events],
            placeholder="选择考试项目",
        )

        if selected_events:
            remind_time = st.number_input("提前提醒天数", min_value=1, max_value=30, value=7)
            if st.button("设置提醒", type="primary"):
                st.toast("🎉 提醒设置成功！将在考试前{}天通知".format(remind_time))

        st.markdown("---")
        st.markdown("**📲 手机订阅**")
        st.write("扫描二维码订阅日历")

        # 获取二维码图片并展示
        try:
            qr_key = "civilpass/qrcode/exam_calendar_qrcode.png"
            qr_image_data = get_cached_oss_object(qr_key)

            if qr_image_data:
                import base64

                b64_img = base64.b64encode(qr_image_data).decode("utf-8")
                st.image(f"data:image/png;base64,{b64_img}", width=300)
            else:
                st.warning("⚠️ 未找到二维码图片")

        except Exception as e:
            st.warning(f"⚠️ 加载二维码失败：{e}")

    # 移动端适配
    st.markdown(
        """
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
    """,
        unsafe_allow_html=True,
    )


# 管理员上传模块
def admin_upload_center():
    st.title("📤 管理员上传中心")
    st.caption("⚠️ 仅限授权人员使用")
    st.markdown("---")

    password = st.text_input("🔐 输入管理员密码", type="password")
    if password != "00277":
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
    menu = st.sidebar.radio(
        "📌 功能导航", ["智能问答", "考试日历", "备考资料", "政策资讯", "高分经验", "上传资料（管理员）"]
    )

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


if __name__ == "__main__":
    main()
