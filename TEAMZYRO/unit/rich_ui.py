from pyrogram import enums
from pyrogram.types import InputRichMessage, InputRichBlockParagraph, InputRichBlockSectionHeading, InputRichBlockButtons, RichMessageButton


def rich_button(text, callback_data=None, url=None, style=None):
    # Kurigram exposes the Bot API button style enum as ButtonStyle.
    # Keep string styles accepted by callers while avoiding import-time crashes
    # when the enum name differs between Kurigram releases.
    if style is None:
        style = enums.ButtonStyle.PRIMARY
    elif isinstance(style, str):
        style = getattr(enums.ButtonStyle, style.upper(), style)

    return RichMessageButton(text=text, callback_data=callback_data, url=url, style=style)


def rich_card(title, body, buttons=None):
    blocks = [
        InputRichBlockSectionHeading(text=title, size=2),
        InputRichBlockParagraph(text=body),
    ]
    for row in buttons or []:
        blocks.append(InputRichBlockButtons(buttons=row, align=enums.BlockAlignment.CENTER))
    return InputRichMessage(blocks=blocks)


async def send_rich_card(client, chat_id, title, body, buttons=None, fallback=None):
    try:
        return await client.send_rich_message(chat_id=chat_id, rich_text=rich_card(title, body, buttons))
    except Exception:
        if fallback is None:
            fallback = f"<b>{title}</b>\\n\\n{body}"
        return await client.send_message(chat_id=chat_id, text=fallback)
