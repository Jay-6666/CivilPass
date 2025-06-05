import streamlit as st
import openai
from src.config.settings import API_KEY, MODEL_NAME, BASE_URL
from src.utils.ui import is_mobile, chat_message
from src.utils.oss import upload_file_to_oss
from src.config.scoring_criteria import get_scoring_criteria, SCORING_RULES

def get_system_prompt(question_text, mode="general"):
    """根据模式和题型生成系统提示词"""
    if mode == "general":
        return """
        你是公务员考试领域的专家，请针对用户提出的问题，像专家讲解一样，用自然、连贯的语言进行清晰解答。
        """
    
    # 题型分析模式
    criteria = get_scoring_criteria(question_text)
    question_type = criteria["题型"]
    
    if question_type == "未知题型":
        return """
        抱歉，无法识别题型。我将作为公务员考试专家，为您提供通用的解答和建议。
        """
    
    # 构建评分要点提示
    scoring_points = []
    for dimension, details in criteria["评分维度"].items():
        points = []
        for key, value in details.items():
            points.append(f"- {key}：{value['说明']}")
        scoring_points.extend(points)
    
    scoring_tips = "\n".join(scoring_points)
    
    return f"""
    你是公务员考试{question_type}领域的专家。我将按照以下格式进行解答：
    
    1. 题型判定：这是一道{question_type}
    2. 评分要点：
    {scoring_tips}
    
    3. 解题思路：
    - 仔细分析题干要求
    - 按照评分要点逐一展开
    - 注意避免常见扣分点
    
    4. 答案示范：
    将按照评分标准提供规范答案
    
    5. 得分技巧：
    总结答题要领和注意事项
    """

def query_qwen_api(user_input, mode="general", image_url=None):
    """调用千问 API"""
    client = openai.OpenAI(api_key=API_KEY, base_url=BASE_URL)
    system_prompt = get_system_prompt(user_input, mode)

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": []}
        ]

        if user_input:
            messages[1]["content"].append({"type": "text", "text": user_input})
        if image_url:
            messages[1]["content"].append({"type": "image_url", "image_url": {"url": image_url}})

        completion = client.chat.completions.create(model=MODEL_NAME, messages=messages)
        return completion.choices[0].message.content

    except Exception as e:
        return f"❌ AI 解析失败: {str(e)}"

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
        with st.expander("📚 支持的题型", expanded=False):
            for qtype, rules in SCORING_RULES.items():
                st.markdown(f"### {qtype}")
                st.markdown("**关键词示例：**")
                st.markdown(", ".join(rules["问法关键词"][:5]) + "...")
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
            user_input = st.text_input(
                "✍️ 问题输入",
                placeholder="请输入您的问题...",
                value=st.session_state.current_input,
                key="user_input",
                label_visibility="collapsed"
            )

        if is_mobile():
            uploaded_file = st.file_uploader(
                "📷 上传试题图片",
                type=["jpg", "png", "jpeg"],
                key="mobile_uploader"
            )
        else:
            with col2:
                uploaded_file = st.file_uploader(
                    "📷 上传试题图片",
                    type=["jpg", "png", "jpeg"],
                    key="desktop_uploader"
                )

        # 在题型分析模式下显示识别到的题型
        if st.session_state.chat_mode == "analysis" and user_input:
            criteria = get_scoring_criteria(user_input)
            if criteria["题型"] != "未知题型":
                st.info(f"📝 已识别题型：{criteria['题型']}")

        submit = st.button("🚀 获取 AI 答案", use_container_width=True, type="primary")

    # 处理提交
    if submit:
        if not user_input and not uploaded_file:
            st.warning("⚠️ 请填写问题或上传图片")
            return

        image_url = None
        if uploaded_file:
            image_url = upload_file_to_oss(uploaded_file, category="civilpass/images")

        # 添加用户消息
        user_message = {
            "role": "user",
            "content": user_input if user_input else "（仅上传图片）",
            "image_url": image_url
        }
        st.session_state.messages.append(user_message)

        # 获取AI响应
        with st.spinner("🤖 AI 解析中..."):
            answer = query_qwen_api(user_input, st.session_state.chat_mode, image_url)

        # 添加AI消息
        ai_message = {"role": "assistant", "content": answer}
        st.session_state.messages.append(ai_message)

        # 重置输入状态
        st.session_state.current_input = ""
        st.rerun() 