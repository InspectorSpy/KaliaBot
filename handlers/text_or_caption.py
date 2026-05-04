import re

from telegram import Update
from telegram.ext import ContextTypes

from handlers.count import count_command
from handlers.counter import kalia_command
from handlers.pyhacounter import pyha_command
from handlers.holitoncounter import hoplop_command
from handlers.scoreboard import scoreboard_command
from handlers.messages import handle_response
from utils.storage import is_photo_used, mark_photo_used

DRINK_COMMANDS = {"/kalia", "/pyha", "/hoplop"}

async def handle_text_or_caption_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    caption = (update.message.caption or "").strip()
    if not caption:
        return

    commands = {
        match.split("@", maxsplit=1)[0]
        for match in re.findall(r"/[\w@]+", caption.lower())
    }
    print("caption:", caption)
    print("commands:", commands)

    # Duplicate image check
    if commands & DRINK_COMMANDS:
        if update.message.photo:
            file_unique_id = update.message.photo[-1].file_unique_id
            chat_id = str(update.message.chat_id)
            user_id = str(update.message.from_user.id)

        if is_photo_used(chat_id, file_unique_id):
            await update.message.reply_text("Tää kuva on jo käytetty!")
            return

        mark_photo_used(chat_id, file_unique_id, user_id)

    if "/kalia" in commands:
        await kalia_command(update, context)
    elif "/pyha" in commands:
        await pyha_command(update, context)
    elif "/hoplop" in commands:
        await hoplop_command(update, context)
    elif "/kaliacount" in commands:
        await count_command(update, context)
    elif commands.intersection({"/scoreboard", "/kaliatop"}):
        await scoreboard_command(update, context)
    else:
        response = await handle_response(caption)
        if response:
            await update.message.reply_text(response)