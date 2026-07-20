from __future__ import annotations

import json
import re
from pathlib import Path

from app.config.email_secrets import decrypt_secret, encrypt_secret

EMAIL_SETTINGS_FILE = Path("data/email_settings.json")
EMAIL_ADDRESS_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MASK = "********"


def resolve_email_settings_path(
    settings_file: Path | str | None = None,
) -> Path:
    if settings_file is not None:
        return Path(settings_file)
    return EMAIL_SETTINGS_FILE


def should_prefer_email_settings(
    settings_file: Path | str | None = None,
) -> bool:
    path = resolve_email_settings_path(settings_file)
    if not path.exists():
        return False

    try:
        _load_raw_settings(path)
    except EmailSettingsError:
        return False
    return True

PROVIDER_PRESETS = {
    "gmail": {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "use_ssl": False,
        "use_tls": True,
    },
    "outlook": {
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "use_ssl": False,
        "use_tls": True,
    },
    "hisense": {
        "smtp_host": "mail.hisense.com",
        "smtp_port": 465,
        "use_ssl": True,
        "use_tls": False,
    },
}

TEST_EMAIL_SUBJECT = "AI Regulation Monitor"
TEST_EMAIL_BODY = "This is a successful SMTP configuration test."


class EmailSettingsError(ValueError):
    pass


def _normalize_provider(provider: str) -> str:
    normalized = str(provider or "gmail").strip().lower()
    if normalized not in {"gmail", "outlook", "hisense", "custom"}:
        raise EmailSettingsError(
            "SMTP provider must be gmail, outlook, hisense, or custom."
        )
    return normalized


def _normalize_recipients(recipients) -> list[str]:
    if not isinstance(recipients, list):
        return []

    cleaned: list[str] = []
    seen: set[str] = set()
    for recipient in recipients:
        address = str(recipient or "").strip().lower()
        if not address:
            continue
        if address in seen:
            raise EmailSettingsError(f"Duplicate recipient: {address}")
        if not EMAIL_ADDRESS_PATTERN.match(address):
            raise EmailSettingsError(f"Invalid recipient email address: {address}")
        seen.add(address)
        cleaned.append(address)
    return cleaned


def _validate_username(username: str) -> str:
    address = str(username or "").strip().lower()
    if not address:
        raise EmailSettingsError("Email address is required.")
    if not EMAIL_ADDRESS_PATTERN.match(address):
        raise EmailSettingsError("Email address format is invalid.")
    return address


def _validate_port(smtp_port) -> int:
    try:
        port = int(smtp_port)
    except (TypeError, ValueError) as error:
        raise EmailSettingsError("SMTP port must be an integer.") from error

    if port < 1 or port > 65535:
        raise EmailSettingsError("SMTP port must be between 1 and 65535.")
    return port


def _validate_security_modes(use_ssl: bool, use_tls: bool) -> None:
    if use_ssl and use_tls:
        raise EmailSettingsError("SSL and STARTTLS cannot both be enabled.")


def _resolve_security_from_payload(payload: dict, preset: dict | None = None) -> tuple[bool, bool]:
    preset = preset or {}
    use_ssl = bool(payload.get("use_ssl", preset.get("use_ssl", False)))
    use_tls = bool(payload.get("use_tls", preset.get("use_tls", True)))
    _validate_security_modes(use_ssl, use_tls)
    return use_ssl, use_tls


def _resolve_provider_fields(provider: str, payload: dict) -> dict:
    normalized_provider = _normalize_provider(provider)
    preset = PROVIDER_PRESETS.get(normalized_provider, {})

    if normalized_provider in PROVIDER_PRESETS:
        use_ssl, use_tls = _resolve_security_from_payload({}, preset)
        return {
            "provider": normalized_provider,
            "smtp_host": preset["smtp_host"],
            "smtp_port": _validate_port(preset["smtp_port"]),
            "use_ssl": use_ssl,
            "use_tls": use_tls,
        }

    smtp_host = str(payload.get("smtp_host") or "").strip()
    if not smtp_host:
        raise EmailSettingsError("SMTP host is required for custom SMTP.")

    smtp_port = payload.get("smtp_port")
    if smtp_port in (None, ""):
        raise EmailSettingsError("SMTP port is required for custom SMTP.")

    use_ssl, use_tls = _resolve_security_from_payload(payload, preset)
    return {
        "provider": normalized_provider,
        "smtp_host": smtp_host,
        "smtp_port": _validate_port(smtp_port),
        "use_ssl": use_ssl,
        "use_tls": use_tls,
    }


def _resolve_provider_fields_from_raw(raw: dict) -> dict:
    normalized_provider = _normalize_provider(raw.get("provider", "gmail"))
    preset = PROVIDER_PRESETS.get(normalized_provider, {})
    payload = {
        "smtp_host": raw.get("smtp_host"),
        "smtp_port": raw.get("smtp_port"),
        "use_ssl": raw.get("use_ssl", preset.get("use_ssl", False)),
        "use_tls": raw.get("use_tls", preset.get("use_tls", True)),
    }

    if normalized_provider in PROVIDER_PRESETS:
        smtp_host = str(raw.get("smtp_host") or preset.get("smtp_host", "")).strip()
        smtp_port = raw.get("smtp_port", preset.get("smtp_port"))
        use_ssl = bool(raw.get("use_ssl", preset.get("use_ssl", False)))
        use_tls = bool(raw.get("use_tls", preset.get("use_tls", True)))
        _validate_security_modes(use_ssl, use_tls)
        return {
            "provider": normalized_provider,
            "smtp_host": smtp_host or preset["smtp_host"],
            "smtp_port": _validate_port(smtp_port),
            "use_ssl": use_ssl,
            "use_tls": use_tls,
        }

    return _resolve_provider_fields(normalized_provider, payload)


def _load_raw_settings(settings_file: Path) -> dict | None:
    if not settings_file.exists():
        return None

    try:
        data = json.loads(settings_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise EmailSettingsError("Email settings file is invalid JSON.") from error

    if not isinstance(data, dict):
        raise EmailSettingsError("Email settings must be a JSON object.")
    return data


def load_email_settings(
    settings_file: Path | str | None = None,
    *,
    key_file: Path | None = None,
) -> dict | None:
    path = Path(settings_file) if settings_file is not None else EMAIL_SETTINGS_FILE
    raw = _load_raw_settings(path)
    if raw is None:
        return None

    provider_fields = _resolve_provider_fields_from_raw(raw)
    if not provider_fields["smtp_host"]:
        raise EmailSettingsError("SMTP host is required.")

    username = _validate_username(raw.get("username", ""))
    recipients = _normalize_recipients(raw.get("recipients", []))
    stored_password = str(raw.get("password", "")).strip()
    password = decrypt_secret(
        stored_password,
        key_file=key_file or Path("data/.email_settings_key"),
    )

    return {
        **provider_fields,
        "username": username,
        "password": password,
        "password_encrypted": stored_password,
        "recipients": recipients,
    }


def load_email_settings_public(
    settings_file: Path | str | None = None,
    *,
    key_file: Path | None = None,
) -> dict:
    path = Path(settings_file) if settings_file is not None else EMAIL_SETTINGS_FILE
    settings = load_email_settings(path, key_file=key_file)
    if settings is None:
        gmail = PROVIDER_PRESETS["gmail"]
        return {
            "configured": False,
            "provider": "gmail",
            "smtp_host": gmail["smtp_host"],
            "smtp_port": gmail["smtp_port"],
            "username": "",
            "password_configured": False,
            "recipients": [],
            "recipient_count": 0,
            "use_ssl": gmail["use_ssl"],
            "use_tls": gmail["use_tls"],
        }

    return {
        "configured": bool(settings.get("recipients")) and bool(
            settings.get("password_encrypted")
        ),
        "provider": settings["provider"],
        "smtp_host": settings["smtp_host"],
        "smtp_port": settings["smtp_port"],
        "username": settings["username"],
        "password_configured": bool(settings.get("password_encrypted")),
        "recipients": settings["recipients"],
        "recipient_count": len(settings["recipients"]),
        "use_ssl": settings.get("use_ssl", False),
        "use_tls": settings.get("use_tls", True),
    }


def save_email_settings(
    payload: dict,
    *,
    settings_file: Path | str | None = None,
    key_file: Path | None = None,
) -> dict:
    path = Path(settings_file) if settings_file is not None else EMAIL_SETTINGS_FILE
    existing = load_email_settings(path, key_file=key_file)

    provider_fields = _resolve_provider_fields(
        payload.get("provider", existing.get("provider", "gmail") if existing else "gmail"),
        payload,
    )
    username = _validate_username(payload.get("username", ""))
    recipients = _normalize_recipients(payload.get("recipients", []))

    password_input = payload.get("password")
    if password_input is None:
        password_input = ""
    password_input = str(password_input).strip()

    if password_input and password_input != PASSWORD_MASK:
        encrypted_password = encrypt_secret(
            password_input,
            key_file=key_file or Path("data/.email_settings_key"),
        )
    elif existing and existing.get("password_encrypted"):
        encrypted_password = existing["password_encrypted"]
    else:
        raise EmailSettingsError("App password is required.")

    stored = {
        **provider_fields,
        "username": username,
        "password": encrypted_password,
        "recipients": recipients,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(stored, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return load_email_settings_public(path, key_file=key_file)


def is_email_settings_active(settings_file: Path | str | None = None) -> bool:
    path = Path(settings_file) if settings_file is not None else EMAIL_SETTINGS_FILE
    if not path.exists():
        return False

    try:
        settings = load_email_settings(path)
    except EmailSettingsError:
        return False

    return bool(
        settings
        and settings.get("recipients")
        and settings.get("password_encrypted")
        and settings.get("smtp_host")
    )


def build_smtp_config(
    settings_file: Path | str | None = None,
    *,
    key_file: Path | None = None,
) -> dict:
    path = Path(settings_file) if settings_file is not None else EMAIL_SETTINGS_FILE
    settings = load_email_settings(path, key_file=key_file)
    if settings is None:
        raise EmailSettingsError("Email settings are not configured.")

    if not settings.get("password"):
        raise EmailSettingsError("SMTP password is not configured.")

    recipients = settings.get("recipients", [])
    if not recipients:
        raise EmailSettingsError("No report email recipients configured.")

    return {
        "enabled": True,
        "provider": settings.get("provider", "custom"),
        "from_address": settings["username"],
        "to_addresses": recipients,
        "smtp_host": settings["smtp_host"],
        "smtp_port": settings["smtp_port"],
        "smtp_username": settings["username"],
        "smtp_password": settings["password"],
        "use_ssl": settings.get("use_ssl", False),
        "use_tls": settings.get("use_tls", True),
    }


def security_mode_label(use_ssl: bool, use_tls: bool) -> str:
    if use_ssl:
        return "SSL / SMTPS"
    if use_tls:
        return "STARTTLS"
    return "None"


def contains_stored_password(text: str, settings_file: Path | str | None = None) -> bool:
    path = Path(settings_file) if settings_file is not None else EMAIL_SETTINGS_FILE
    if not path.exists():
        return False

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False

    stored_password = str(raw.get("password", "")).strip()
    if not stored_password:
        return False

    if stored_password in text:
        return True

    try:
        settings = load_email_settings(path)
    except EmailSettingsError:
        return False

    password = settings.get("password", "")
    return bool(password and password in text)
