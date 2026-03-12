import traceback
import asyncio
from fastapi import Request
from fastapi.responses import JSONResponse
from app.utils.alert_utils import send_email_alert


async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常捕获处理函数
    """
    # 1. 提取完整的错误堆栈
    error_msg = traceback.format_exc()

    # 2. 组装报警信息
    alert_text = f"🚨 后端服务报警\n\nURL: {request.url}\nMethod: {request.method}\nError: {str(exc)}\n\nTraceback:\n{error_msg}"

    # 3. 【关键改动】使用 asyncio 将发邮件操作扔到后台线程执行！
    # 这样接口会瞬间返回，用户不用等待发邮件的这 1~2 秒钟
    asyncio.create_task(asyncio.to_thread(send_email_alert, alert_text))

    # 4. 【关键修复】必须 return 一个合法的 Response，给前端一个优雅的交代
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部开小差了，工程师已收到报警！",
            "data": None,
        },
    )
