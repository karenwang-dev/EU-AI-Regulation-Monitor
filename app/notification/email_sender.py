import os
import smtplib
from email.mime.text import MIMEText


class EmailSendError(RuntimeError):
    pass


def send_email(
    smtp_config: dict,
    subject: str,
    body: str,
) -> None:
    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = smtp_config["from_address"]
    message["To"] = ", ".join(smtp_config["to_addresses"])

    password_env = smtp_config.get("smtp_password_env", "SMTP_PASSWORD")
    password = os.getenv(password_env, "")

    try:
        with smtplib.SMTP(
            smtp_config["smtp_host"],
            smtp_config["smtp_port"],
            timeout=30,
        ) as server:
            if smtp_config.get("use_tls", True):
                server.starttls()

            username = smtp_config.get("smtp_username", "")
            if username or password:
                server.login(username, password)

            server.sendmail(
                smtp_config["from_address"],
                smtp_config["to_addresses"],
                message.as_string(),
            )
    except Exception as error:
        raise EmailSendError(str(error)) from error
