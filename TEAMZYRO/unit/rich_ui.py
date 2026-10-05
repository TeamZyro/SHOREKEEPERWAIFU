from pyrogram import enums
from pyrogram.types import InputRichMessage, InputRichBlockParagraph, InputRichBlockSectionHeading, InputRichBlockButtons, RichMessageButton


def rich_button(text, callback_data=None, url=None, style=enums.RichButtonStyle.PRIMARY):
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
        return await client.send_rich_message(chat_id=chat_id, rich_message=rich_card(title, body, buttons))
    except Exception:
        if fallback is None:
            fallback = f"<b>{title}</b>\\n\\n{body}"
        return await client.send_message(chat_id=chat_id, text=fallback)
