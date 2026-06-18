import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


def _smtp_config() -> dict:
    return {
        "host": os.environ.get("EMAIL_SMTP_HOST", ""),
        "port": int(os.environ.get("EMAIL_SMTP_PORT", "587")),
        "user": os.environ.get("EMAIL_SMTP_USER", ""),
        "password": os.environ.get("EMAIL_SMTP_PASS", ""),
    }


def is_email_configured() -> bool:
    cfg = _smtp_config()
    return bool(cfg["host"] and cfg["user"] and cfg["password"])


def send_application_email(
    to_email: str,
    applicant_name: str,
    applicant_email: str,
    job_title: str,
    company: str,
    cover_letter: str,
    resume_path: str = None,
) -> dict:
    """Send a job application email with cover letter and optional resume attachment."""
    cfg = _smtp_config()

    if not cfg["host"]:
        return {"success": False, "error": "SMTP not configured. Add EMAIL_SMTP_HOST, EMAIL_SMTP_USER, EMAIL_SMTP_PASS to your secrets."}
    if not cfg["user"] or not cfg["password"]:
        return {"success": False, "error": "SMTP credentials missing. Add EMAIL_SMTP_USER and EMAIL_SMTP_PASS to your secrets."}

    msg = MIMEMultipart("mixed")
    msg["From"] = f"{applicant_name} <{cfg['user']}>"
    msg["To"] = to_email
    msg["Reply-To"] = applicant_email or cfg["user"]
    msg["Subject"] = f"Application for {job_title} at {company} — {applicant_name}"

    # Build HTML + plain text body
    plain_body = f"Dear Hiring Team at {company},\n\n{cover_letter}\n\nBest regards,\n{applicant_name}\n{applicant_email}"
    paragraphs = "".join(
        f"<p>{para.strip()}</p>"
        for para in cover_letter.split("\n\n")
        if para.strip()
    )
    html_body = (
        f'<html><body style="font-family: Arial, sans-serif; max-width: 600px;'
        f' line-height: 1.6; color: #333;">'
        f"<p>Dear Hiring Team at <strong>{company}</strong>,</p>"
        f"{paragraphs}"
        f"<p>Best regards,<br><strong>{applicant_name}</strong><br>"
        f"{applicant_email}</p>"
        f"</body></html>"
    )

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(plain_body, "plain"))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)

    # Attach resume if provided
    if resume_path and os.path.exists(resume_path):
        try:
            with open(resume_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            filename = os.path.basename(resume_path)
            part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
            msg.attach(part)
        except Exception as e:
            print(f"Warning: could not attach resume: {e}")

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["user"], to_email, msg.as_string())
        return {"success": True, "to": to_email, "subject": msg["Subject"]}
    except smtplib.SMTPAuthenticationError:
        return {"success": False, "error": "SMTP authentication failed. Check EMAIL_SMTP_USER and EMAIL_SMTP_PASS."}
    except smtplib.SMTPException as e:
        return {"success": False, "error": f"SMTP error: {e}"}
    except Exception as e:
        return {"success": False, "error": f"Failed to send: {e}"}


def send_password_reset_email(to_email: str, reset_url: str, user_name: str = "") -> dict:
    """Send a password reset link to the user."""
    cfg = _smtp_config()

    if not (cfg["host"] and cfg["user"] and cfg["password"]):
        return {"success": False, "error": "smtp_not_configured"}

    name_str = user_name or to_email.split("@")[0]
    plain = (
        f"Hi {name_str},\n\n"
        f"You requested a password reset for your JobBlitz account.\n\n"
        f"Click this link to reset your password (expires in 1 hour):\n{reset_url}\n\n"
        f"If you didn't request this, you can safely ignore this email.\n\n"
        f"— JobBlitz"
    )
    html = (
        f'<html><body style="font-family:Arial,sans-serif;max-width:520px;line-height:1.6;color:#333;">'
        f"<h2 style='color:#7c3aed;'>Reset your password</h2>"
        f"<p>Hi <strong>{name_str}</strong>,</p>"
        f"<p>You requested a password reset for your JobBlitz account.</p>"
        f'<p><a href="{reset_url}" style="display:inline-block;background:#7c3aed;color:#fff;'
        f'padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">Reset Password</a></p>'
        f"<p style='color:#888;font-size:13px;'>This link expires in 1 hour. "
        f"If you didn't request this, you can safely ignore this email.</p>"
        f"</body></html>"
    )

    msg = MIMEMultipart("alternative")
    msg["From"] = f"JobBlitz <{cfg['user']}>"
    msg["To"] = to_email
    msg["Subject"] = "Reset your JobBlitz password"
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["user"], to_email, msg.as_string())
        return {"success": True}
    except smtplib.SMTPAuthenticationError:
        return {"success": False, "error": "SMTP authentication failed."}
    except Exception as e:
        return {"success": False, "error": str(e)}
