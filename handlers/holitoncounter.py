from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from utils.storage import get_holiton, increment_holiton


async def hoplop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo or not update.message.caption:
        print("Ignoring /hoplop because it was not sent in a photo caption.")
        return

    if update.effective_message:
        try:
            await update.effective_message.set_reaction("👎")
        except TelegramError as exc:
            print(f"Could not set reaction: {exc}")

    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    count = increment_holiton(
        chat_id,
        user_id,
        username=update.effective_user.username,
        full_name=update.effective_user.full_name,
    )