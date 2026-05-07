import logging
import smtplib
from email.mime.text import MIMEText
from app.core.config import settings


logger = logging.getLogger(__name__)


def send_email_alert(content: str) -> bool:
    """
    发送异常报警邮件 (同步函数)
    """
    # ⚠️ 请替换为你自己的邮箱配置
    sender = settings.sender_email
    password = settings.sender_password
    # 如果没配置邮箱，直接就不发了，避免报错
    if not sender or not password:
        logger.error("未配置 SENDER_EMAIL 或 SENDER_PASSWORD，跳过发送报警邮件")
        return False

    receiver = sender  # 收件人邮箱 (可以是自己发给自己)

    # 构建邮件内容
    msg = MIMEText(content, "plain", "utf-8")
    msg["Subject"] = "🚨 SHL App 后端服务异常报警"
    msg["From"] = sender
    msg["To"] = receiver

    try:
        # 使用配置中的 SMTP 服务器和端口
        server = smtplib.SMTP_SSL(settings.smtp_server, settings.smtp_port, timeout=10)
        server.login(sender, password)
        server.sendmail(sender, [receiver], msg.as_string())
        server.quit()
        logger.info("报警邮件已发送成功: %s", receiver)
        return True
    except Exception as e:
        logger.exception("报警邮件发送失败: %s", e)
        return False
