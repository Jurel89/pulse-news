# ruff: noqa: E501
from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape

from app.models import Newsletter

PULSE_NEWS_GITHUB_URL = "https://github.com/Jurel89/pulse-news"


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


def _inline_markdown_to_html(text: str) -> str:
    """Convert inline markdown patterns to HTML within a line of text.

    Handles: **bold**, *italic*, `code`, [link](url).
    """
    result = escape(text)

    result = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2" style="color:#18324a;text-decoration:underline;">\1</a>',
        result,
    )
    result = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", result)
    result = re.sub(r"\*(.+?)\*", r"<em>\1</em>", result)
    result = re.sub(
        r"`([^`]+)`",
        r'<code style="background:#f0f4f8;padding:2px 6px;border-radius:4px;font-size:14px;">\1</code>',
        result,
    )

    return result


def _markdown_body_to_html(body: str) -> str:
    """Convert markdown-like plain text into styled HTML suitable for email.

    Handles headings (** or ##), bold, italic, code, links, bullet lists,
    and blank-line paragraph breaks.
    """
    lines = body.splitlines()
    html_parts: list[str] = []
    in_list = False

    for raw_line in lines:
        stripped = raw_line.strip()

        if not stripped:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        bold_heading_match = re.match(r"^\*\*(.+?)\*\*\s*$", stripped)

        if heading_match:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            level = len(heading_match.group(1))
            size = {1: "24px", 2: "20px", 3: "17px"}[level]
            weight = {1: "700", 2: "600", 3: "600"}[level]
            margin_top = "24px" if html_parts else "0"
            heading_text = _inline_markdown_to_html(heading_match.group(2))
            html_parts.append(
                f'<h{level} style="margin:{margin_top} 0 12px;font-size:{size};'
                f'font-weight:{weight};line-height:1.3;color:#18324a;">'
                f"{heading_text}</h{level}>"
            )
        elif bold_heading_match and not re.search(r"\*\*.+\*\*.+\*\*", stripped):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            margin_top = "24px" if html_parts else "0"
            heading_text = _inline_markdown_to_html(bold_heading_match.group(1))
            html_parts.append(
                f'<h2 style="margin:{margin_top} 0 12px;font-size:20px;'
                f'font-weight:600;line-height:1.3;color:#18324a;">'
                f"{heading_text}</h2>"
            )
        elif stripped.startswith(("- ", "* ", "\u2022 ")):
            if not in_list:
                html_parts.append(
                    '<ul style="margin:0 0 16px 20px;padding:0;line-height:1.7;color:#2c3e50;">'
                )
                in_list = True
            item_text = _inline_markdown_to_html(stripped[2:])
            html_parts.append(f'<li style="margin:0 0 6px;font-size:15px;">{item_text}</li>')
        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            line_html = _inline_markdown_to_html(stripped)
            html_parts.append(
                f'<p style="margin:0 0 16px;font-size:15px;line-height:1.7;color:#2c3e50;">'
                f"{line_html}</p>"
            )

    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def render_signal_template(subject: str, preheader: str, body_html: str) -> str:
    return "\n".join(
        [
            "<!doctype html>",
            "<html>",
            "  <head>",
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            "  </head>",
            "  <body style=\"margin:0;padding:0;background:#eef3f7;font-family:'IBM Plex Sans','Segoe UI',system-ui,-apple-system,sans-serif;color:#18324a;-webkit-font-smoothing:antialiased;\">",
            '    <center style="width:100%;background:#eef3f7;">',
            '      <div style="max-width:640px;margin:0 auto;padding:32px 18px;">',
            '        <div style="background:linear-gradient(135deg,#18324a,#2f5f7a);color:#f7f5ef;border-radius:28px;padding:36px 32px;">',
            '          <p style="margin:0 0 14px;font-size:11px;letter-spacing:2.5px;text-transform:uppercase;opacity:0.75;font-weight:500;">Pulse News</p>',
            f'          <h1 style="margin:0;font-size:28px;line-height:1.2;font-weight:700;letter-spacing:-0.3px;">{escape(subject)}</h1>',
            f'          <p style="margin:14px 0 0;font-size:15px;line-height:1.5;opacity:0.88;">{escape(preheader)}</p>',
            "        </div>",
            '        <div style="background:#ffffff;border-radius:20px;padding:32px 28px;margin-top:16px;box-shadow:0 12px 40px rgba(24,50,74,0.10);">',
            f"          {body_html}",
            "        </div>",
            _build_email_footer(),
            "      </div>",
            "    </center>",
            "  </body>",
            "</html>",
        ]
    )


def render_ledger_template(subject: str, preheader: str, body_html: str) -> str:
    return "\n".join(
        [
            "<!doctype html>",
            "<html>",
            "  <head>",
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            "  </head>",
            "  <body style=\"margin:0;padding:0;background:#f5efe4;font-family:Georgia,'Times New Roman',serif;color:#40240f;-webkit-font-smoothing:antialiased;\">",
            '    <center style="width:100%;background:#f5efe4;">',
            '      <div style="max-width:680px;margin:0 auto;padding:24px 16px;">',
            '        <div style="border:1px solid #d8c0a8;background:#fffaf3;padding:32px 28px;">',
            '          <p style="margin:0 0 12px;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:#8b5e1b;font-weight:500;">Field Notes</p>',
            f'          <h1 style="margin:0;font-size:30px;line-height:1.15;font-weight:700;">{escape(subject)}</h1>',
            f'          <p style="margin:16px 0 0;font-size:16px;line-height:1.6;color:#6a4a2c;">{escape(preheader)}</p>',
            "        </div>",
            '        <div style="border-left:5px solid #8b5e1b;background:#ffffff;padding:32px 28px;margin-top:16px;">',
            f"          {body_html}",
            "        </div>",
            _build_email_footer(accent="#8b5e1b"),
            "      </div>",
            "    </center>",
            "  </body>",
            "</html>",
        ]
    )


def _build_email_footer(accent: str = "#5c7a8a") -> str:
    return (
        '<div style="text-align:center;padding:24px 18px 12px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        "<tr>"
        '<td style="padding-bottom:12px;">'
        f'<div style="height:1px;background:linear-gradient(to right,transparent,{accent},transparent);opacity:0.3;"></div>'
        "</td>"
        "</tr>"
        "<tr>"
        '<td style="padding:8px 0;">'
        f'<p style="margin:0;font-size:12px;color:{accent};opacity:0.7;line-height:1.5;">'
        f'Sent from <a href="{PULSE_NEWS_GITHUB_URL}" '
        f'style="color:{accent};text-decoration:underline;font-weight:600;">Pulse-News</a>'
        " &mdash; self-hosted newsletter operations</p>"
        "</td>"
        "</tr>"
        "</table>"
        "</div>"
    )


def render_custom_template(
    html_template: str, subject: str, preheader: str, body_html: str, newsletter_name: str
) -> str:
    result = html_template
    result = result.replace("{{subject}}", escape(subject))
    result = result.replace("{{preheader}}", escape(preheader))
    result = result.replace("{{headline}}", escape(subject))
    result = result.replace("{{content}}", body_html)
    result = result.replace("{{body_html}}", body_html)
    result = result.replace("{{newsletter_name}}", escape(newsletter_name))

    footer = _build_email_footer()
    if "{{footer}}" in html_template:
        result = result.replace("{{footer}}", footer)
    elif "</body>" in result:
        result = result.replace("</body>", f"{footer}\n</body>")
    elif "</html>" in result:
        result = result.replace("</html>", f"{footer}\n</html>")
    else:
        result += footer
    return result


def render_newsletter(newsletter: Newsletter) -> RenderedNewsletter:
    from sqlalchemy import select

    from app.deps import get_db_session
    from app.models import EmailTemplate

    subject, preheader, body = normalize_draft_content(newsletter)
    body_html = _markdown_body_to_html(body)

    template_key = newsletter.template_key or "signal"
    db = next(get_db_session())
    custom_template = db.scalar(select(EmailTemplate).where(EmailTemplate.key == template_key))

    if custom_template and custom_template.html_template:
        html = render_custom_template(
            custom_template.html_template, subject, preheader, body_html, newsletter.name
        )
    elif template_key == "signal":
        html = render_signal_template(subject, preheader, body_html)
    elif template_key == "ledger":
        html = render_ledger_template(subject, preheader, body_html)
    else:
        raise ValueError(
            f"Template '{template_key}' was not found and no built-in template matches."
        )

    plain_text_body = render_plain_text(subject, preheader, body)
    plain_text_body += f"\n\n---\nSent from Pulse-News — {PULSE_NEWS_GITHUB_URL}"

    return RenderedNewsletter(
        subject=subject,
        preheader=preheader,
        html=html,
        plain_text=plain_text_body,
        template_key=template_key,
    )
