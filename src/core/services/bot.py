from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING
import cv2
import asyncio
import numpy as np
import getpass
import html
from telegram import (
  Update,
  ReplyKeyboardMarkup,
  BotCommand,
  InlineKeyboardMarkup,
  InlineKeyboardButton,
)
from telegram.ext import (
  Application,
  CommandHandler,
  MessageHandler,
  ContextTypes,
  filters,
  CallbackQueryHandler,
)
from core.logging import get_logger
from core.services.windows_service import WindowService
from core.account.model import FarmStatus

import resources

if TYPE_CHECKING:
  from core.context import Context

logger = get_logger("sv.bot")

SALES_CHANNEL = "https://t.me/y_a_c_s_p"


class TelegramBotService:
  def __init__(self, ctx: Context):
    self.ctx = ctx
    self.app: Application = None
    self.running = False

  async def start(self):
    token = self.ctx.su.telegram_token
    if not token:
      logger.warn("Telegram token is missing. Bot service disabled.")
      return

    try:
      self.app = Application.builder().token(token).build()
      self.app.add_handler(CommandHandler("start", self._cmd_start))
      self.app.add_handler(CommandHandler("help", self._cmd_help))
      self.app.add_handler(CommandHandler("status", self._cmd_status))
      self.app.add_handler(CommandHandler("screenshot", self._cmd_screenshot))
      self.app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text)
      )

      await self.app.initialize()
      await self.app.start()

      await self._setup_commands()

      await self.app.updater.start_polling(drop_pending_updates=True)
      self.running = True
      logger.info("Telegram bot started successfully")

    except Exception as e:
      logger.error(f"Failed to start Telegram bot: {e}")

  async def stop(self):
    if self.running and self.app:
      logger.info("Stopping Telegram bot...")
      await self.app.updater.stop()
      await self.app.stop()
      await self.app.shutdown()
      self.running = False

  async def _setup_commands(self):
    """Настройка выпадающего меню команд (Help Menu)"""
    commands = [
      BotCommand("start", "Start bot and show menu"),
      BotCommand("status", "Get farm status"),
      BotCommand("screenshot", "Get screen capture"),
      BotCommand("help", "Show help message"),
    ]
    await self.app.bot.set_my_commands(commands)

  def _check_auth(self, user_id: int) -> bool:
    return str(user_id) in self.ctx.su.telegram_whitelist

  async def _send_sales_message(self, update: Update):
    keyboard = InlineKeyboardMarkup(
      [[InlineKeyboardButton("Buy Panel", url=SALES_CHANNEL)]]
    )
    await update.message.reply_text(
      "⛔ Access Denied.\n\nYou are not authorized to use this panel.\n"
      "To purchase access, please visit our channel.",
      reply_markup=keyboard,
    )

  async def _cmd_start(
    self, update: Update, context: ContextTypes.DEFAULT_TYPE
  ):
    user = update.effective_user
    if not self._check_auth(user.id):
      logger.warn(
        f"Unauthorized access attempt from {user.id} ({user.username})"
      )
      await self._send_sales_message(update)
      return

    keyboard = [["🖥 Status", "📸 Screenshot"], ["❓ Help"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
      f"👋 Hello, {user.first_name}!\nYACS Panel is online and running.",
      reply_markup=reply_markup,
    )

  async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not self._check_auth(update.effective_user.id):
      return

    help_text = (
      "<b>YACS Panel Bot Help</b>\n\n"
      "/start - Restart menu\n"
      "/status - List active running accounts\n"
      "/screenshot - Capture main window\n"
      "/help - Show this message"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

  async def _cmd_status(
    self, update: Update, context: ContextTypes.DEFAULT_TYPE
  ):
    if not self._check_auth(update.effective_user.id):
      await self._send_sales_message(update)
      return

    running_accounts = WindowService.scan_cs2_windows(
      self.ctx.accounts(), values=True
    )

    if not running_accounts:
      safe_user = html.escape(getpass.getuser())
      await update.message.reply_text(
        f"[<b>{safe_user}</b>] 💤 No accounts running.", parse_mode="HTML"
      )
      return

    msg = f"<b>Active Sessions ({len(running_accounts)})</b>:\n\n"

    for acc in running_accounts:
      lvl = acc.lock.lvl or 0
      xp = acc.lock.xp or 0
      status = acc.lock.status or "unknown"

      status_icon = "🟢"
      if status == FarmStatus.FARMED:
        status_icon = "✅"
      elif status == FarmStatus.CAN_BE_LOOTED:
        status_icon = "🎁"

      safe_login = html.escape(acc.login)

      msg += (
        f"👤 <code>{safe_login}</code>\n"
        f"├ Rank: {lvl} | XP: {xp}/5000\n"
        f"└ Status: {status_icon} {status}\n\n"
      )

    await update.message.reply_text(msg, parse_mode="HTML")

  async def _cmd_screenshot(
    self, update: Update, context: ContextTypes.DEFAULT_TYPE
  ):
    if not self._check_auth(update.effective_user.id):
      return

    chat_id = update.effective_chat.id

    placeholder = resources.load("placeholder.jpg")
    placeholder_msg = await context.bot.send_photo(
      chat_id=chat_id,
      photo=placeholder,
      caption="📸 Capturing screen...",
    )

    await asyncio.sleep(1.5)

    try:
      frame = self.ctx.screen.capture()

      if frame is None or frame.size == 0:
        await context.bot.delete_message(chat_id, placeholder_msg.message_id)
        await update.message.reply_text(
          "❌ Failed to capture screen (empty frame)."
        )
        return

      await context.bot.delete_message(chat_id, placeholder_msg.message_id)

      height, width = frame.shape[:2]
      await self.send_message(
        chat_id=chat_id, text=f"{width}x{height}", image=frame
      )

    except Exception as e:
      logger.error(f"Screenshot error: {e}")
      try:
        await context.bot.delete_message(chat_id, placeholder_msg.message_id)
      except Exception:
        pass
      await update.message.reply_text(f"❌ Error taking screenshot: {e}")

  async def _handle_text(
    self, update: Update, context: ContextTypes.DEFAULT_TYPE
  ):
    if not self._check_auth(update.effective_user.id):
      return

    text = update.message.text
    if text == "🖥 Status":
      await self._cmd_status(update, context)
    elif text == "📸 Screenshot":
      await self._cmd_screenshot(update, context)
    elif text == "❓ Help":
      await self._cmd_help(update, context)

  async def send_message(
    self,
    chat_id: int | str,
    text: str,
    image: Optional[np.ndarray] = None,
    parse_mode: str = "HTML",
    reply_markup: Optional[InlineKeyboardMarkup] = None,
  ):
    if not self.running or not self.app or not self.app.bot:
      logger.warning(
        "Bot not running or application not initialized. Cannot send message."
      )
      return

    safe_user = html.escape(getpass.getuser())
    caption = f"[<b>{safe_user}</b>]: {text}"

    try:
      if image is not None:
        image_bytes = encode_frame_to_bytes(image, "png")
        if image_bytes:
          await self.app.bot.send_photo(
            chat_id=chat_id,
            photo=image_bytes,
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
          )
          logger.debug(f"sent photo message to {chat_id}")
        else:
          logger.error("Failed to encode image for telegram")
      else:
        await self.app.bot.send_message(
          chat_id=chat_id,
          text=caption,
          parse_mode=parse_mode,
          reply_markup=reply_markup,
        )
        logger.debug(f"sent text message to {chat_id}")
    except Exception as e:
      logger.error(f"Failed to send Telegram message to {chat_id}: {e}")


def encode_frame_to_bytes(
  frame_bgra: np.ndarray, ext: str = "png"
) -> bytes | None:
  try:
    if ext.lower() == "jpeg":
      if frame_bgra.shape[2] == 4:
        frame_bgr = frame_bgra[:, :, :3]
      else:
        frame_bgr = frame_bgra

      encode_success, encoded_image = cv2.imencode(
        ".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90]
      )
    else:
      encode_success, encoded_image = cv2.imencode(".png", frame_bgra)

    if encode_success:
      return encoded_image.tobytes()
    else:
      print("Error encoding image frame.")
      return None
  except Exception as e:
    print(f"Encoding exception: {e}")
    return None
