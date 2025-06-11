import streamlit as st
import openai
from src.config.settings import API_KEY, MODEL_NAME, BASE_URL
from src.utils.ui import is_mobile, chat_message
from src.utils.oss import upload_file_to_oss
from src.config.scoring_criteria import get_scoring_criteria, SCORING_RULES
import os
import mimetypes
from typing import List, Tuple, Dict
import plotly.graph_objects as go
import re
import json

def get_system_prompt(question_text, mode="general", file_content=None):
    """根据模式和题型生成系统提示词"""
    if mode == "general":
        if file_content:
            return """
            你是公务员考试领域的专家，请针对用户提供的文件内容进行专业分析和点评。
            请注意以下几点：
            1. 仔细阅读文件内容，识别题型和要求
            2. 根据评分标准进行逐项分析
            3. 提供具体的修改建议和提分技巧
            4. 给出整体评价和分数预估
            """
        return """
        你是公务员考试领域的专家，请针对用户提出的问题，像专家讲解一样，用自然、连贯的语言进行清晰解答。
        """
    
    # 题型分析模式
    criteria = get_scoring_criteria(question_text if question_text else file_content)
    question_type = criteria["题型"]
    
    if question_type == "未知题型":
        if file_content:
            return """
            抱歉，无法直接识别文件中的题型。我将作为公务员考试专家，为您提供以下分析：
            1. 文件内容概述
            2. 可能的题型判断
            3. 通用评分要点
            4. 改进建议
            5. 得分技巧
            """
        return """
        抱歉，无法识别题型。我将作为公务员考试专家，为您提供通用的解答和建议。
        """
    
    # 构建评分要点提示
    scoring_points = []
    for dimension, details in criteria["评分维度"].items():
        points = []
        for key, value in details.items():
            points.append(f"- {key}：{value['说明']} | 扣分规则：{value['扣分规则']} | 建议：{value['建议']}")
        scoring_points.extend(points)
    
    scoring_tips = "\n".join(scoring_points)
    
    # 获取分档说明
    grading_levels = ""
    if "分档说明" in criteria:
        levels = []
        for level, desc in criteria["分档说明"].items():
            levels.append(f"- {level}：{desc}")
        grading_levels = "\n".join(levels)
    
    # 根据是否有文件内容决定分析方式
    if file_content:
        return f"""
        你是公务员考试{question_type}领域的资深阅卷专家。请按照以下步骤进行分析：

        第一步：题型分析
        1. 明确指出这是一道{question_type}
        2. 详细说明本题型的特征和考查重点
        3. 解释该题型的答题要求和关键评分点

        第二步：内容批阅
        1. 内容要点提取
        2. 按以下维度进行评分和分析：
        {scoring_tips}

        3. 分数档位参考：
        {grading_levels}

        4. 具体分析：
        - 优点分析
        - 不足之处
        - 修改建议
        - 分数预估（请明确给出每个维度的具体分数，格式为"维度名称：得分X分"）

        5. 提分建议：
        - 针对性改进建议
        - 答题技巧指导
        - 易错点提醒

        请用专业、清晰的语言进行分析，注重实用性和可操作性。
        """
    else:
        return f"""
        你是公务员考试{question_type}领域的资深阅卷专家。请按照以下步骤进行分析：

        第一步：题型分析
        1. 明确指出这是一道{question_type}
        2. 详细说明本题型的特征和考查重点
        3. 解释该题型的答题要求和关键评分点

        第二步：答题指导
        1. 评分维度说明：
        {scoring_tips}

        2. 分数档位说明：
        {grading_levels}

        3. 答题思路指导：
        - 如何准确理解题目要求
        - 答题框架构建方法
        - 关键词和句式示例
        - 常见错误提醒

        4. 得分技巧：
        - 高分答题要领
        - 重点注意事项
        - 提分建议

        请用专业、清晰的语言进行解答，注重实用性和可操作性。
        """

def extract_scores(response_text: str, criteria: Dict) -> Dict[str, float]:
    """从AI响应中提取各维度的分数"""
    scores = {}
    
    # 获取所有评分维度
    dimensions = criteria.get("评分维度", {}).keys()
    for dimension in dimensions:
        # 初始化维度分数为0
        scores[dimension] = 0
        # 在响应文本中查找与该维度相关的分数
        pattern = f"{dimension}[：:](.*?)(\d+)分"
        matches = re.findall(pattern, response_text)
        if matches:
            # 如果找到分数，取最后一个匹配的分数
            scores[dimension] = float(matches[-1][1])
    
    return scores

def create_score_chart(scores: Dict[str, float], max_scores: Dict[str, float]) -> go.Figure:
    """创建得分柱状图"""
    dimensions = list(scores.keys())
    score_values = list(scores.values())
    max_values = [max_scores.get(dim, 100) for dim in dimensions]
    
    # 计算得分率
    score_percentages = [score / max_score * 100 for score, max_score in zip(score_values, max_values)]
    
    # 创建柱状图
    fig = go.Figure()
    
    # 添加得分柱
    fig.add_trace(go.Bar(
        name='得分',
        x=dimensions,
        y=score_values,
        text=[f"{score:.1f}分" for score in score_values],
        textposition='auto',
        marker_color='rgb(26, 118, 255)'
    ))
    
    # 更新布局
    fig.update_layout(
        title={
            'text': '各维度得分分析',
            'y':0.9,
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top'
        },
        yaxis_title="分数",
        yaxis=dict(
            tickmode='linear',
            tick0=0,
            dtick=5,
            range=[0, max(max_values) + 5]
        ),
        showlegend=False,
        height=400,
        margin=dict(l=50, r=50, t=80, b=50)
    )
    
    # 添加得分率标签
    for i, (score, percentage) in enumerate(zip(score_values, score_percentages)):
        fig.add_annotation(
            x=dimensions[i],
            y=score,
            text=f"{percentage:.1f}%",
            yshift=10,
            showarrow=False
        )
    
    return fig

def get_max_scores(criteria: Dict) -> Dict[str, float]:
    """获取各维度的满分值"""
    max_scores = {}
    for dimension, details in criteria.get("评分维度", {}).items():
        # 计算该维度下所有子项的总分
        dimension_max = 0
        for key, value in details.items():
            # 从扣分规则中提取分值
            score_pattern = r"扣(\d+)分"
            matches = re.findall(score_pattern, value.get("扣分规则", ""))
            if matches:
                dimension_max += sum(int(score) for score in matches)
        max_scores[dimension] = float(dimension_max)
    
    return max_scores

def query_qwen_api(user_input, mode="general", image_url=None, file_url=None, file_content=None):
    """调用千问 API"""
    client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL)
    system_prompt = get_system_prompt(user_input, mode, file_content)

    try:
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # 构建用户消息
        if file_content:
            user_content = f"""
            我收到了一份需要评阅的文件，内容如下：

            {file_content}

            请根据上述内容，按照评分标准进行专业点评。
            在回答中，请为每个评分维度明确给出具体分数，格式为"维度名称：得分X分"。
            """
        else:
            user_content = user_input if user_input else "请分析这道题目"

        messages.append({"role": "user", "content": user_content})

        # 创建流式响应
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            stream=True
        )
        
        # 创建一个占位符用于显示流式响应
        placeholder = st.empty()
        # 用于累积完整的响应
        full_response = ""
        
        # 逐步显示响应
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                full_response += chunk.choices[0].delta.content
                # 使用markdown格式显示，支持格式化文本
                placeholder.markdown(full_response + "▌")
        
        # 最后一次更新，移除光标
        placeholder.markdown(full_response)
        
        return full_response

    except Exception as e:
        return f"❌ AI 解析失败: {str(e)}"

def get_file_type(filename: str) -> str:
    """获取文件类型"""
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type:
        if mime_type.startswith('image/'):
            return '图片'
        elif mime_type.startswith('application/pdf'):
            return 'PDF'
        elif 'word' in mime_type:
            return 'Word文档'
        elif mime_type.startswith('text/'):
            return '文本文件'
    return '未知类型'

def validate_file(uploaded_file) -> Tuple[bool, str]:
    """验证上传的文件"""
    if uploaded_file is None:
        return True, ""
    
    # 检查文件大小（限制为50MB）
    MAX_SIZE = 50 * 1024 * 1024  # 50MB
    if uploaded_file.size > MAX_SIZE:
        return False, f"文件大小超过限制（最大50MB），当前大小：{uploaded_file.size / 1024 / 1024:.1f}MB"
    
    # 检查文件类型
    ALLOWED_TYPES = {
        '.pdf': 'PDF文件',
        '.doc': 'Word文档',
        '.docx': 'Word文档',
        '.txt': '文本文件',
        '.jpg': '图片',
        '.jpeg': '图片',
        '.png': '图片'
    }
    
    file_ext = os.path.splitext(uploaded_file.name)[1].lower()
    if file_ext not in ALLOWED_TYPES:
        return False, f"不支持的文件类型：{file_ext}。支持的类型：{', '.join(ALLOWED_TYPES.values())}"
    
    return True, ""

def show_chatbot():
    """显示聊天机器人界面"""
    st.title("📝 智能公考助手")
    st.caption("📢 输入你的问题，或批阅申论作文，AI帮你搞定！")
    st.markdown("---")

    # 初始化会话状态
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_input" not in st.session_state:
        st.session_state.current_input = ""
    if "chat_mode" not in st.session_state:
        st.session_state.chat_mode = "general"

    # 模式选择
    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            "💬 普通问答模式",
            type="primary" if st.session_state.chat_mode == "general" else "secondary",
            use_container_width=True
        ):
            st.session_state.chat_mode = "general"
            st.session_state.messages = []
            st.rerun()
    
    with col2:
        if st.button(
            "📝 题型分析模式",
            type="primary" if st.session_state.chat_mode == "analysis" else "secondary",
            use_container_width=True
        ):
            st.session_state.chat_mode = "analysis"
            st.session_state.messages = []
            st.rerun()

    # 显示当前模式说明
    if st.session_state.chat_mode == "analysis":
        st.info("📋 题型分析模式：上传或输入题目，AI将自动识别题型并提供专业解答")
        
        # 显示支持的题型信息
        with st.expander("📚 支持的题型与评分标准", expanded=False):
            for qtype, rules in SCORING_RULES.items():
                st.markdown(f"### 📝 {qtype}")
                st.markdown("**常见问法：**")
                st.markdown("、".join(rules["问法关键词"][:5]) + "...")
                
                if "评分维度" in rules:
                    st.markdown("**评分维度：**")
                    for dim, details in rules["评分维度"].items():
                        st.markdown(f"- {dim}:")
                        for key, value in details.items():
                            st.markdown(f"  - {key}: {value['说明']}")
                
                if "分档说明" in rules:
                    st.markdown("**分数档位：**")
                    for level, desc in rules["分档说明"].items():
                        st.markdown(f"- {level}：{desc}")
                st.markdown("---")
    else:
        st.info("💡 普通问答模式：可以问我任何公考相关的问题")

    # 聊天记录容器
    chat_container = st.container()

    # 显示聊天记录
    with chat_container:
        for message in st.session_state.messages:
            role = message["role"]
            content = message["content"]
            image_url = message.get("image_url")

            with st.chat_message(role):
                if image_url and role == "user":
                    st.image(image_url, caption="🖼 已上传图片", use_column_width=True)
                st.write(content)

    # 输入区域
    with st.container():
        col1, col2 = st.columns([2, 1]) if not is_mobile() else st.columns([1])

        with col1:
            # 添加自定义样式
            st.markdown("""
                <style>
                    .stTextArea textarea {
                        min-height: 100px;
                        max-height: 400px;
                        font-size: 16px;
                        line-height: 1.5;
                        resize: vertical;
                    }
                    .upload-prompt {
                        font-size: 14px;
                        color: #666;
                        margin-top: 5px;
                    }
                    .file-info {
                        padding: 10px;
                        border-radius: 5px;
                        background-color: #f0f2f6;
                        margin-top: 10px;
                    }
                </style>
                """, unsafe_allow_html=True)
            
            user_input = st.text_area(
                "✍️ 问题输入",
                placeholder="请输入您的问题...\n支持多行输入，输入框会自动调整高度",
                value=st.session_state.current_input,
                key="user_input",
                label_visibility="collapsed",
                height=None
            )

        if is_mobile():
            st.markdown('<p class="upload-prompt">📎 支持上传PDF、Word、文本文件和图片（最大50MB）</p>', unsafe_allow_html=True)
            uploaded_file = st.file_uploader(
                "上传文件",
                type=["pdf", "doc", "docx", "txt", "jpg", "jpeg", "png"],
                key="mobile_uploader",
                help="支持PDF、Word、文本文件和图片，大小不超过50MB"
            )
        else:
            with col2:
                st.markdown('<p class="upload-prompt">📎 支持上传PDF、Word、文本文件和图片（最大50MB）</p>', unsafe_allow_html=True)
                uploaded_file = st.file_uploader(
                    "上传文件",
                    type=["pdf", "doc", "docx", "txt", "jpg", "jpeg", "png"],
                    key="desktop_uploader",
                    help="支持PDF、Word、文本文件和图片，大小不超过50MB"
                )

        # 显示文件信息
        if uploaded_file is not None:
            is_valid, error_msg = validate_file(uploaded_file)
            if not is_valid:
                st.error(error_msg)
            else:
                file_type = get_file_type(uploaded_file.name)
                file_size = uploaded_file.size / 1024  # 转换为KB
                st.markdown(f"""
                <div class="file-info">
                    📄 文件名：{uploaded_file.name}<br>
                    📝 类型：{file_type}<br>
                    📊 大小：{file_size:.1f} KB
                </div>
                """, unsafe_allow_html=True)

        # 在题型分析模式下显示识别到的题型和评分要点
        if st.session_state.chat_mode == "analysis" and user_input:
            criteria = get_scoring_criteria(user_input)
            if criteria["题型"] != "未知题型":
                with st.expander(f"📝 已识别题型：{criteria['题型']} - 点击查看评分要点", expanded=True):
                    for dim, details in criteria["评分维度"].items():
                        st.markdown(f"### {dim}")
                        for key, value in details.items():
                            st.markdown(f"- **{key}**")
                            st.markdown(f"  - 说明：{value['说明']}")
                            st.markdown(f"  - 扣分规则：{value['扣分规则']}")
                            st.markdown(f"  - 建议：{value['建议']}")

        submit = st.button("🚀 获取 AI 答案", use_container_width=True, type="primary")

    # 处理提交
    if submit:
        if not user_input and not uploaded_file:
            st.warning("⚠️ 请填写问题或上传文件")
            return

        image_url = None
        file_url = None
        file_content = None
        
        # 添加用户消息
        user_message = {
            "role": "user",
            "content": user_input if user_input else "（已上传文件）",
            "image_url": None,
            "file_url": None,
            "file_content": None
        }
        
        if uploaded_file:
            is_valid, error_msg = validate_file(uploaded_file)
            if not is_valid:
                st.error(error_msg)
                return
            
            # 读取文件内容
            file_type = get_file_type(uploaded_file.name)
            if file_type in ['文本文件', 'Word文档']:
                try:
                    # 对于文本文件，直接读取内容
                    if file_type == '文本文件':
                        file_content = uploaded_file.getvalue().decode('utf-8')
                    # 对于Word文档，需要使用python-docx处理
                    elif file_type == 'Word文档':
                        import docx
                        doc = docx.Document(uploaded_file)
                        file_content = '\n'.join([paragraph.text for paragraph in doc.paragraphs])
                except Exception as e:
                    st.error(f"文件读取失败：{str(e)}")
                    return
            
            # 上传文件到OSS
            if file_type == '图片':
                image_url = upload_file_to_oss(uploaded_file, category="civilpass/images")
            else:
                file_url = upload_file_to_oss(uploaded_file, category=f"civilpass/{file_type.lower()}")
            
            # 更新用户消息
            user_message.update({
                "image_url": image_url,
                "file_url": file_url,
                "file_content": file_content
            })

        # 添加用户消息到会话状态
        st.session_state.messages.append(user_message)

        # 显示用户消息
        with st.chat_message("user"):
            if image_url:
                st.image(image_url, caption="🖼 已上传图片", use_column_width=True)
            st.write(user_message["content"])

        # 显示AI响应（使用流式输出）
        with st.chat_message("assistant"):
            answer = query_qwen_api(user_input, st.session_state.chat_mode, image_url, file_url, file_content)
            
            # 如果是题型分析模式且有文件内容，显示评分图表
            if st.session_state.chat_mode == "analysis" and file_content:
                # 获取评分标准
                criteria = get_scoring_criteria(file_content)
                if criteria["题型"] != "未知题型":
                    # 提取分数
                    scores = extract_scores(answer, criteria)
                    if scores:
                        # 获取满分值
                        max_scores = get_max_scores(criteria)
                        # 创建并显示图表
                        fig = create_score_chart(scores, max_scores)
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # 显示总分和评级
                        total_score = sum(scores.values())
                        max_total = sum(max_scores.values())
                        st.info(f"📊 总分：{total_score:.1f}/{max_total:.1f} ({(total_score/max_total*100):.1f}%)")
                        
                        # 显示分档说明
                        if "分档说明" in criteria:
                            st.markdown("### 📝 分档说明")
                            for level, desc in criteria["分档说明"].items():
                                st.markdown(f"- **{level}**：{desc}")
            
            # 将完整响应保存到会话状态
            ai_message = {"role": "assistant", "content": answer}
            st.session_state.messages.append(ai_message)

        # 重置输入状态
        st.session_state.current_input = ""
        st.rerun() 