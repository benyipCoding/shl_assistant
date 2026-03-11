import base64
import os
import uuid
from datetime import datetime
from pathlib import Path

# 定义静态文件存储的基础目录
STATIC_DIR = Path("static")
UPLOAD_DIR = STATIC_DIR / "uploads" / "shl_images"


def save_base64_image(base64_data: str, mime_type: str) -> str:
    """
    将Base64图片数据保存为静态文件，并返回访问URL

    Args:
        base64_data: base64编码的图片数据 (可能包含也可能不包含 `data:image/...;base64,` 前缀)
        mime_type: 图片的 MIME 类型，如 "image/png", "image/jpeg"

    Returns:
        str: 图片的相对访问路径，例如 "/static/uploads/shl_images/xxx.png"
    """
    # 确保存储目录存在
    if not UPLOAD_DIR.exists():
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 处理 base64 数据，去掉可能存在的前缀
    if "," in base64_data:
        base64_data = base64_data.split(",")[1]

    # 根据 mime_type 确定文件扩展名
    extension = ".png"  # 默认
    if mime_type == "image/jpeg":
        extension = ".jpg"
    elif mime_type == "image/png":
        extension = ".png"
    elif mime_type == "image/gif":
        extension = ".gif"
    elif mime_type == "image/webp":
        extension = ".webp"

    # 生成唯一文件名
    # 使用 日期_UUID 的格式，方便按时间排序且不重复
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    filename = f"{timestamp}_{unique_id}{extension}"

    file_path = UPLOAD_DIR / filename

    # 解码并写入文件
    try:
        image_data = base64.b64decode(base64_data)
        with open(file_path, "wb") as f:
            f.write(image_data)

        # 返回相对访问路径 (注意：这里返回的是 URL 路径，不是文件系统路径)
        # 路径分隔符统一使用 /
        return f"/static/uploads/shl_images/{filename}"

    except Exception as e:
        print(f"Error saving image: {e}")
        # 如果保存失败，视具体需求抛出异常或返回 None，这里简单抛出
        raise e
