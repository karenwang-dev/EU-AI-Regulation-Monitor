from __future__ import annotations

import html
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.notification.email_sender import EmailSendError, send_smtp_message

IMPACT_EMAIL_BADGE = {
    "HIGH": ("#fee2e2", "#b42318", "High"),
    "MEDIUM": ("#fef3c7", "#a16207", "Medium"),
    "LOW": ("#dcfce7", "#15803d", "Low"),
    "NONE": ("#f1f5f9", "#64748b", "None"),
    "UNASSESSED": ("#e2e8f0", "#475569", "Unassessed"),
}

CELL_STYLE = "padding:10px;border-bottom:1px solid #e2e8f0;vertical-align:top;"


def _escape(value) -> str:
    return html.escape(str(value or ""), quote=True)


def _normalize_impact(level) -> str:
    normalized = str(level or "NONE").strip().upper()
    return normalized if normalized in IMPACT_EMAIL_BADGE else "NONE"


def _impact_badge_html(level) -> str:
    normalized = _normalize_impact(level)
    background, color, label = IMPACT_EMAIL_BADGE[normalized]
    return (
        "<span style='display:inline-block;padding:3px 10px;border-radius:999px;"
        f"font-size:12px;font-weight:600;background:{background};color:{color};'>"
        f"{_escape(label)}</span>"
    )


def _format_action_list(actions) -> str:
    if not actions:
        return "N/A"
    items = "".join(
        f"<li style='margin:0 0 4px;'>{_escape(action)}</li>"
        for action in actions
        if str(action).strip()
    )
    if not items:
        return "N/A"
    return (
        f"<ul style='margin:0;padding-left:18px;line-height:1.45;'>{items}</ul>"
    )


def _format_module_list(modules) -> str:
    if not modules:
        return "N/A"
    badges = "".join(
        "<span style='display:inline-block;margin:0 6px 6px 0;padding:2px 8px;"
        "border-radius:999px;background:#f8fafc;border:1px solid #e2e8f0;"
        f"font-size:12px;'>{_escape(module)}</span>"
        for module in modules
        if str(module).strip()
    )
    return badges or "N/A"


def _format_title_cell(change: dict) -> str:
    title = _escape(change.get("title", "N/A"))
    source_url = str(change.get("source_url", "")).strip()
    if not source_url:
        return title
    return (
        f"{title}<br><a href='{_escape(source_url)}' "
        "style='color:#1d4ed8;font-size:12px;text-decoration:none;'>View source</a>"
    )


def _build_key_change_row(change: dict) -> str:
    modules = change.get("affected_modules", [])
    actions = change.get("recommended_actions", [])
    return (
        "<tr>"
        f"<td style='{CELL_STYLE}'>{_format_title_cell(change)}</td>"
        f"<td style='{CELL_STYLE}'>{_impact_badge_html(change.get('impact_level', 'NONE'))}</td>"
        f"<td style='{CELL_STYLE}'>{_format_module_list(modules)}</td>"
        f"<td style='{CELL_STYLE}'>{_format_action_list(actions)}</td>"
        "</tr>"
    )


def _summary_stat_cell(value, label: str, *, accent: str | None = None) -> str:
    value_style = f"color:{accent};" if accent else ""
    return (
        "<td style='width:25%;padding:12px;background:#f8fafc;"
        "border:1px solid #e2e8f0;text-align:center;'>"
        f"<strong style='font-size:20px;{value_style}'>{_escape(value)}</strong><br>"
        f"<span style='font-size:12px;color:#52627a;'>{_escape(label)}</span>"
        "</td>"
    )


def build_report_email_html(report: dict) -> str:
    summary = report.get("summary", {})
    period = report.get("period", {})
    key_changes = report.get("key_changes", [])

    if key_changes:
        table_body = "".join(_build_key_change_row(change) for change in key_changes)
    else:
        table_body = (
            "<tr><td colspan='4' style='padding:16px;color:#64748b;text-align:center;'>"
            "No key changes this period.</td></tr>"
        )

    key_changes_table = (
        "<table role='presentation' cellpadding='0' cellspacing='0' "
        "style='border-collapse:collapse;width:100%;font-size:14px;'>"
        "<thead><tr>"
        f"<th style='{CELL_STYLE}text-align:left;background:#f1f5f9;'>Title</th>"
        f"<th style='{CELL_STYLE}text-align:left;background:#f1f5f9;'>Impact</th>"
        f"<th style='{CELL_STYLE}text-align:left;background:#f1f5f9;'>Modules</th>"
        f"<th style='{CELL_STYLE}text-align:left;background:#f1f5f9;'>Recommended actions</th>"
        "</tr></thead><tbody>"
        f"{table_body}"
        "</tbody></table>"
    )

    affected_modules = _format_module_list(summary.get("affected_modules", []))
    executive_summary = report.get("executive_summary") or "No executive summary available."
    risk_summary = report.get("risk_summary") or "No risk summary available."

    stats_row = "".join(
        [
            _summary_stat_cell(summary.get("total_changes", 0), "Total changes"),
            _summary_stat_cell(
                summary.get("high_risk", 0),
                "High risk",
                accent="#b42318",
            ),
            _summary_stat_cell(
                summary.get("medium_risk", 0),
                "Medium risk",
                accent="#a16207",
            ),
            _summary_stat_cell(summary.get("low_risk", 0), "Low risk", accent="#15803d"),
        ]
    )

    return f"""
<html><body style="margin:0;padding:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#172033;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 12px;"><tr><td align="center">
    <table role="presentation" width="680" cellpadding="0" cellspacing="0" style="max-width:680px;width:100%;background:#ffffff;border-radius:10px;overflow:hidden;">
      <tr><td style="padding:28px 32px;background:#123b68;color:#ffffff;">
        <div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;opacity:.8;">AI Regulation Monitor</div>
        <h1 style="margin:8px 0 0;font-size:24px;line-height:1.25;">{_escape(report.get('title', 'Weekly Regulation Monitoring Report'))}</h1>
      </td></tr>
      <tr><td style="padding:28px 32px;">
        <p style="margin:0 0 20px;color:#52627a;font-size:14px;"><strong>Reporting period:</strong> {_escape(period.get('start', 'N/A'))} to {_escape(period.get('end', 'N/A'))}<br><strong>Generated:</strong> {_escape(report.get('generated_at', 'N/A'))}</p>
        <h2 style="font-size:18px;margin:0 0 12px;">At a glance</h2>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{stats_row}</tr></table>
        <p style="font-size:14px;color:#52627a;margin:16px 0 0;"><strong>Affected modules:</strong> {affected_modules}</p>
        <h2 style="font-size:18px;margin:24px 0 8px;">Executive Summary</h2>
        <p style="margin:0;line-height:1.6;">{_escape(executive_summary)}</p>
        <h2 style="font-size:18px;margin:24px 0 8px;">Key Changes</h2>
        {key_changes_table}
        <h2 style="font-size:18px;margin:24px 0 8px;">Risk Summary</h2>
        <p style="margin:0;line-height:1.6;">{_escape(risk_summary)}</p>
      </td></tr>
      <tr><td style="padding:18px 32px;background:#f8fafc;color:#64748b;font-size:12px;">This automated summary supports compliance review. The attached JSON contains the complete report record.</td></tr>
    </table>
  </td></tr></table>
</body></html>
""".strip()


def build_report_email_plain_text(report: dict) -> str:
    summary = report.get("summary", {})
    period = report.get("period", {})
    lines = [
        report.get("title", "Weekly Regulation Monitoring Report"),
        "",
        f"Reporting period: {period.get('start', 'N/A')} to {period.get('end', 'N/A')}",
        f"Generated: {report.get('generated_at', 'N/A')}",
        "",
        "At a glance",
        f"- Total changes: {summary.get('total_changes', 0)}",
        f"- High risk: {summary.get('high_risk', 0)}",
        f"- Medium risk: {summary.get('medium_risk', 0)}",
        f"- Low risk: {summary.get('low_risk', 0)}",
        f"- Affected modules: {', '.join(summary.get('affected_modules', [])) or 'N/A'}",
        "",
        "Executive Summary",
        report.get("executive_summary") or "No executive summary available.",
        "",
        "Key Changes",
    ]

    key_changes = report.get("key_changes", [])
    if not key_changes:
        lines.append("- No key changes this period.")
    else:
        for index, change in enumerate(key_changes, start=1):
            modules = ", ".join(change.get("affected_modules", [])) or "N/A"
            actions = "; ".join(change.get("recommended_actions", [])) or "N/A"
            lines.extend(
                [
                    f"{index}. {change.get('title', 'N/A')} "
                    f"[{change.get('impact_level', 'NONE')}]",
                    f"   Modules: {modules}",
                    f"   Actions: {actions}",
                ]
            )
            source_url = str(change.get("source_url", "")).strip()
            if source_url:
                lines.append(f"   Source: {source_url}")

    lines.extend(
        [
            "",
            "Risk Summary",
            report.get("risk_summary") or "No risk summary available.",
            "",
            "The attached JSON contains the complete report record.",
        ]
    )
    return "\n".join(lines)


def build_report_email_subject(report: dict) -> str:
    period = report.get("period", {})
    start = period.get("start", "")
    end = period.get("end", "")
    period_label = f"{start} to {end}".strip()
    title = report.get("title", "Weekly Regulation Monitoring Report")

    summary = report.get("summary", {})
    high_risk = int(summary.get("high_risk", 0) or 0)
    medium_risk = int(summary.get("medium_risk", 0) or 0)
    if high_risk > 0:
        prefix = f"[High Risk x{high_risk}]"
    elif medium_risk > 0:
        prefix = f"[Medium Risk x{medium_risk}]"
    else:
        prefix = "[Weekly Report]"

    if period_label:
        return f"{prefix} {title} ({period_label})"
    return f"{prefix} {title}"


def send_report_email(
    report: dict,
    smtp_config: dict,
    attachment_path: Path | str | None = None,
) -> None:
    subject = build_report_email_subject(report)
    html_body = build_report_email_html(report)
    plain_body = build_report_email_plain_text(report)

    message = MIMEMultipart("mixed")
    message["Subject"] = subject
    message["From"] = smtp_config["from_address"]
    message["To"] = ", ".join(smtp_config["to_addresses"])

    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(plain_body, "plain", "utf-8"))
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

    try:
        send_smtp_message(
            smtp_config,
            from_address=smtp_config["from_address"],
            to_addresses=smtp_config["to_addresses"],
            message_content=message.as_string(),
        )
    except EmailSendError as error:
        raise EmailSendError(str(error)) from error
