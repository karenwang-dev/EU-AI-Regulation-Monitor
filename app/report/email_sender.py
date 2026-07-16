from __future__ import annotations

import html
import json
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.notification.email_sender import EmailSendError


def _escape(value) -> str:
    return html.escape(str(value or ""), quote=True)


def build_report_email_html(report: dict) -> str:
    summary = report.get("summary", {})
    period = report.get("period", {})
    key_changes = report.get("key_changes", [])

    rows = []
    for change in key_changes:
        modules = ", ".join(change.get("affected_modules", [])) or "N/A"
        actions = ", ".join(change.get("recommended_actions", [])) or "N/A"
        rows.append(
            "<tr>"
            f"<td>{_escape(change.get('title', 'N/A'))}</td>"
            f"<td>{_escape(change.get('impact_level', 'NONE'))}</td>"
            f"<td>{_escape(modules)}</td>"
            f"<td>{_escape(actions)}</td>"
            "</tr>"
        )

    if rows:
        table_body = "".join(rows)
    else:
        table_body = "<tr><td colspan='4'>No key changes</td></tr>"

    key_changes_table = (
        "<table border='1' cellpadding='6' cellspacing='0' "
        "style='border-collapse: collapse; width: 100%;'>"
        "<thead><tr>"
        "<th>Title</th><th>Impact</th><th>Modules</th><th>Actions</th>"
        "</tr></thead><tbody>"
        f"{table_body}"
        "</tbody></table>"
    )

    affected_modules = ", ".join(summary.get("affected_modules", [])) or "N/A"

    return f"""
<html>
  <body style="font-family: Arial, sans-serif; color: #222;">
    <h2>{_escape(report.get('title', 'Weekly Regulation Monitoring Report'))}</h2>
    <p><strong>Period:</strong> {_escape(period.get('start', 'N/A'))} to {_escape(period.get('end', 'N/A'))}</p>
    <p><strong>Generated at:</strong> {_escape(report.get('generated_at', 'N/A'))}</p>
    <h3>Summary</h3>
    <ul>
      <li>Total changes: {_escape(summary.get('total_changes', 0))}</li>
      <li>High risk: {_escape(summary.get('high_risk', 0))}</li>
      <li>Medium risk: {_escape(summary.get('medium_risk', 0))}</li>
      <li>Low risk: {_escape(summary.get('low_risk', 0))}</li>
      <li>Affected modules: {_escape(affected_modules)}</li>
    </ul>
    <h3>Executive Summary</h3>
    <p>{_escape(report.get('executive_summary', 'No executive summary available.'))}</p>
    <h3>Key Changes</h3>
    {key_changes_table}
    <h3>Risk Summary</h3>
    <p>{_escape(report.get('risk_summary', 'No risk summary available.'))}</p>
  </body>
</html>
""".strip()


def build_report_email_subject(report: dict) -> str:
    period = report.get("period", {})
    start = period.get("start", "")
    end = period.get("end", "")
    period_label = f"{start} to {end}".strip()
    title = report.get("title", "Weekly Regulation Monitoring Report")
    if period_label:
        return f"[Weekly Report] {title} ({period_label})"
    return f"[Weekly Report] {title}"


def send_report_email(
    report: dict,
    smtp_config: dict,
    attachment_path: Path | str | None = None,
) -> None:
    subject = build_report_email_subject(report)
    html_body = build_report_email_html(report)

    message = MIMEMultipart("mixed")
    message["Subject"] = subject
    message["From"] = smtp_config["from_address"]
    message["To"] = ", ".join(smtp_config["to_addresses"])

    alternative = MIMEMultipart("alternative")
    alternative.attach(
        MIMEText(
            "Weekly regulation monitoring report. Please view this email "
            "in an HTML-capable client.",
            "plain",
            "utf-8",
        )
    )
    alternative.attach(MIMEText(html_body, "html", "utf-8"))
    message.attach(alternative)

    if attachment_path:
        path = Path(attachment_path)
        if path.exists():
            attachment = MIMEApplication(
                path.read_bytes(),
                Name=path.name,
            )
            attachment["Content-Disposition"] = f'attachment; filename="{path.name}"'
            message.attach(attachment)

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
