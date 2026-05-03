import logging
import smtplib
from email.message import EmailMessage

from flask import Blueprint, jsonify, request

import config

contact_bp = Blueprint("contact", __name__)
logger = logging.getLogger(__name__)


@contact_bp.route("/contact", methods=["POST"])
def contact():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    subject = (data.get("subject") or "").strip()
    message = (data.get("message") or "").strip()

    if not name or not email or not subject or not message:
        return jsonify({"error": "Name, email, subject, and message are required."}), 400

    logger.info(
        "Contact form: name=%r email=%r subject=%r message=%r",
        name,
        email,
        subject,
        message[:500] + ("…" if len(message) > 500 else ""),
    )

    if (
        config.CONTACT_SMTP_HOST
        and config.CONTACT_SMTP_USER
        and config.CONTACT_SMTP_PASSWORD
        and config.CONTACT_MAIL_TO
    ):
        try:
            msg = EmailMessage()
            msg["Subject"] = f"[AgriTech — Smart Crop Detective] {subject}"
            msg["From"] = config.CONTACT_SMTP_USER
            msg["To"] = config.CONTACT_MAIL_TO
            msg.set_content(f"From: {name} <{email}>\n\n{message}")
            with smtplib.SMTP(
                config.CONTACT_SMTP_HOST, config.CONTACT_SMTP_PORT, timeout=15
            ) as smtp:
                smtp.starttls()
                smtp.login(config.CONTACT_SMTP_USER, config.CONTACT_SMTP_PASSWORD)
                smtp.send_message(msg)
        except Exception as e:
            logger.exception("Contact email failed: %s", e)
            return jsonify({"error": "Could not send message. Please try again later."}), 502

    return jsonify({"status": "received"}), 200
