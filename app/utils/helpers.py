import base64


def base64_to_bytes(b64: str) -> bytes:
    # 如果有 data:image/...;base64, 前缀，先去掉
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    return base64.b64decode(b64)
