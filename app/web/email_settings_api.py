from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.config.email_settings import (
    EmailSettingsError,
    TEST_EMAIL_BODY,
    TEST_EMAIL_SUBJECT,
    build_smtp_config,
    is_email_settings_active,
    load_email_settings_public,
    save_email_settings,
)
from app.notification.email_sender import EmailSendError, send_email
from app.web.report_email_helper import humanize_smtp_error, sanitize_log_message
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmailSettingsSaveRequest(BaseModel):
    provider: str = Field(default="gmail")
    smtp_host: str | None = None
    smtp_port: int | None = None
    username: str
    password: str | None = None
    recipients: list[str]
    use_ssl: bool = False
    use_tls: bool = True


def register_email_settings_routes(
    app: FastAPI,
    email_settings_file: Path | str | None = None,
    send_email_fn=None,
) -> None:
    settings_path = Path(email_settings_file) if email_settings_file else None
    sender = send_email_fn or send_email

    @app.get("/api/email/settings")
    def api_get_email_settings():
        return load_email_settings_public(settings_path)

    @app.put("/api/email/settings")
    def api_save_email_settings(payload: EmailSettingsSaveRequest):
        try:
            saved = save_email_settings(
                payload.model_dump(),
                settings_file=settings_path,
            )
        except EmailSettingsError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return saved

    @app.post("/api/email/settings/test")
    def api_send_email_settings_test():
        if not is_email_settings_active(settings_path):
            raise HTTPException(
                status_code=400,
                detail="Save email settings before sending a test email.",
            )

        try:
            smtp_config = build_smtp_config(settings_path)
            sender(
                smtp_config,
                TEST_EMAIL_SUBJECT,
                TEST_EMAIL_BODY,
            )
        except (EmailSettingsError, EmailSendError) as error:
            logger.exception(
                "Email settings test failed after SMTP send attempt",
            )
            technical_details = str(error)
            raise HTTPException(
                status_code=400,
                detail={
                    "message": humanize_smtp_error(error),
                    "technical_details": sanitize_log_message(technical_details),
                },
            ) from error

        return {
            "ok": True,
            "message": "Test email sent successfully.",
        }
