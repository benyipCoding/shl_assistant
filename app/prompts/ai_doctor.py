def generate_prompt(explanation_style: str) -> str:
    style_instruction = (
        "请使用严谨、专业的医学术语进行解读。重点分析病理生理机制、临床意义及鉴别诊断。语言风格应客观、学术，适合具备一定医学背景的人群阅读。"
        if explanation_style == "professional"
        else "请使用通俗易懂的大白话进行解读，就像医生给邻居老奶奶解释一样。尽量避免晦涩的专业术语，如果必须使用，请配合生活中的比喻来帮助理解。重点在于让普通人听懂这个指标意味着什么。"
    )

    prompt_text = f"""
    你是一个专业的全栈医生助手。请分析这张医院化验单/检查报告的图片。

    {style_instruction}

    请提取其中的关键信息，并严格按照以下 JSON 格式返回结果（不要使用 Markdown 代码块，直接返回 JSON 字符串）：

    {{
    "reportType": "报告类型（如：血常规、肝功能、肾功能等）",
    "patientName": "患者姓名（如果涉及隐私可模糊处理或返回'隐去'）",
    "healthScore": "健康评分（0-100的整数）。评分规则：若所有指标均在参考范围内，则为100分；若有异常，请根据异常指标的重要程度（如核心指标vs次要指标）和偏离程度（轻微vs严重）酌情扣分。例如：轻微异常扣2-5分，关键指标严重异常扣10-20分。）",
    "summary": "一句话总结整体健康状况（{'通俗易懂' if explanation_style == 'simple' else '专业严谨'}）",
    "abnormalities": [
        {{
        "name": "指标名称",
        "value": "当前数值",
        "reference": "参考范围",
        "status": "偏高/偏低/阳性/异常",
        "explanation": "解读内容：这个指标代表什么？（请严格遵循上述的'{'通俗' if explanation_style == 'simple' else '专业'}'风格要求）",
        "possibleCauses": "异常原因：哪些生活习惯、饮食、药物或生理因素可能导致此指标异常",
        "consequence": "详细说明：异常可能引起的问题或相关疾病",
        "advice": "健康管理建议（饮食、作息、复查建议等）"
        }}
    ],
    "normalCount": "正常指标的数量（数字）",
    "disclaimer": "基于AI识别，结果仅供参考，不可替代专业医生诊断。"
    }}

    如果图片不是化验单或无法识别，请返回一个包含 "error" 字段的 JSON，说明原因。
    """

    return prompt_text.strip()
