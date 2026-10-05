from html import escape

from pyrogram.types import InputRichMessage


def rich_button(text, callback_data=None, url=None, style="primary"):
    """Build a Telegram Rich Message button using the Bot API 10.3 HTML format."""
    button_type = "url" if url else "callback_data"
    data = url if url else callback_data

    if not data:
        raise ValueError("Rich button requires callback_data or url")

    safe_text = escape(str(text))
    safe_data = escape(str(data), quote=True)
    safe_style = escape(str(style or "primary"), quote=True)

    return (
        f'<tg-button type="{button_type}" '
        f'style="{safe_style}" data="{safe_data}">'
        f"{safe_text}</tg-button>"
    )


def rich_button_row(buttons, align="center"):
    """Build one Rich Message button row."""
    if not buttons:
        return ""

    safe_align = escape(str(align), quote=True)
    return (
        f'<tg-button-row align="{safe_align}">'
        + "".join(buttons)
        + "</tg-button-row>"
    )


def rich_message(html, buttons=None):
    """Build a Rich Message from trusted/escaped HTML plus Rich Message buttons."""
    content = str(html)
    for row in buttons or []:
        content += rich_button_row(row)
    return InputRichMessage(html=content)


def rich_card(title, body, buttons=None):
    """Build a Rich Message using the same HTML button pattern as RonovaUB."""
    html = (
        f"<h2>{escape(str(title))}</h2>"
        f"<p>{escape(str(body)).replace(chr(10), '<br>')}</p>"
    )

    for row in buttons or []:
        html += rich_button_row(row)

    return InputRichMessage(html=html)


async def send_rich_card(client, chat_id, title, body, buttons=None, fallback=None):
    try:
        return await client.send_rich_message(
            chat_id=chat_id,
            rich_message=rich_card(title, body, buttons),
        )
    except Exception:
        if fallback is None:
            fallback = f"<b>{title}</b>\n\n{body}"
        return await client.send_message(chat_id=chat_id, text=fallback)
