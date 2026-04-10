# ruff: noqa: E501
from __future__ import annotations

from dataclasses import dataclass
from html import escape

from app.models import Newsletter


@dataclass
class RenderedNewsletter:
    subject: str
    preheader: str
    html: str
    plain_text: str
    template_key: str


def normalize_draft_content(newsletter: Newsletter) -> tuple[str, str, str]:
    subject = newsletter.draft_subject.strip() or newsletter.name
    preheader = (newsletter.draft_preheader or newsletter.description or "").strip()
    body = newsletter.draft_body_text.strip() or newsletter.description or ""
    return subject, preheader, body


def render_plain_text(subject: str, preheader: str, body: str) -> str:
    sections = [subject]
    if preheader:
        sections.append(preheader)
    sections.append("")
    sections.append(body)
    return "\n".join(sections).strip()


def render_signal_template(subject: str, preheader: str, body_html: str) -> str:
    return "\n".join(
        [
            "<!doctype html>",
            "<html>",
            '  <body style="margin:0;background:#eef3f7;font-family:IBM Plex Sans,Segoe UI,sans-serif;color:#18324a;">',
            '    <div style="max-width:640px;margin:0 auto;padding:32px 18px;">',
            '      <div style="background:linear-gradient(135deg,#18324a,#2f5f7a);color:#f7f5ef;border-radius:28px;padding:32px;">',
            '        <p style="margin:0 0 12px;font-size:12px;letter-spacing:2px;text-transform:uppercase;opacity:0.8;">Pulse News</p>',
            f'        <h1 style="margin:0;font-size:34px;line-height:1.05;">{escape(subject)}</h1>',
            f'        <p style="margin:16px 0 0;font-size:16px;line-height:1.5;opacity:0.92;">{escape(preheader)}</p>',
            "      </div>",
            '      <div style="background:#ffffff;border-radius:24px;padding:28px;margin-top:18px;box-shadow:0 18px 45px rgba(24,50,74,0.12);">',
            f"        {body_html}",
            "      </div>",
            "    </div>",
            "  </body>",
            "</html>",
        ]
    )


def render_ledger_template(subject: str, preheader: str, body_html: str) -> str:
    return "\n".join(
        [
            "<!doctype html>",
            "<html>",
            '  <body style="margin:0;background:#f5efe4;font-family:Georgia,Times New Roman,serif;color:#40240f;">',
            '    <div style="max-width:680px;margin:0 auto;padding:24px 16px;">',
            '      <div style="border:1px solid #d8c0a8;background:#fffaf3;padding:28px;">',
            '        <p style="margin:0 0 12px;font-size:12px;letter-spacing:3px;text-transform:uppercase;color:#8b5e1b;">Field Notes</p>',
            f'        <h1 style="margin:0;font-size:36px;line-height:1.1;">{escape(subject)}</h1>',
            f'        <p style="margin:18px 0 0;font-size:17px;line-height:1.6;color:#6a4a2c;">{escape(preheader)}</p>',
            "      </div>",
            '      <div style="border-left:6px solid #8b5e1b;background:#ffffff;padding:28px;margin-top:18px;">',
            f"        {body_html}",
            "      </div>",
            "    </div>",
            "  </body>",
            "</html>",
        ]
    )


def render_newsletter(newsletter: Newsletter) -> RenderedNewsletter:
    subject, preheader, body = normalize_draft_content(newsletter)
    body_lines = [line.strip() for line in body.splitlines()]
    body_html = "".join(
        (
            f'<p style="margin:0 0 16px;line-height:1.7;">{escape(line)}</p>'
            if line
            else '<div style="height:12px;"></div>'
        )
        for line in body_lines
    )

    template_key = newsletter.template_key or "signal"
    if template_key == "signal":
        html = render_signal_template(subject, preheader, body_html)
    elif template_key == "ledger":
        html = render_ledger_template(subject, preheader, body_html)
    else:
        raise ValueError(f"Unknown template_key '{template_key}'. Supported: signal, ledger")

    return RenderedNewsletter(
        subject=subject,
        preheader=preheader,
        html=html,
        plain_text=render_plain_text(subject, preheader, body),
        template_key=template_key,
    )
