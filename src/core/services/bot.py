from __future__ import annotations
from typing import List, TYPE_CHECKING
import asyncio
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
      "*YACS Panel Bot Help*\n\n"
      "/start - Restart menu\n"
      "/status - List active accounts\n"
      "/screenshot - Capture main window\n"
      "/help - Show this message"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

  async def _cmd_status(
    self, update: Update, context: ContextTypes.DEFAULT_TYPE
  ):
    if not self._check_auth(update.effective_user.id):
      await self._send_sales_message(update)
      return

    accounts = self.ctx.accounts()

    # TODO: reply running accounts
    msg = f"**Running Status ({len(accounts)})**:\n\n"
    for acc in accounts[:10]:
      msg += f"- `{acc.login}`: [lvl={acc.lock.lvl}; xp={acc.lock.xp}]\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

  async def _cmd_screenshot(
    self, update: Update, context: ContextTypes.DEFAULT_TYPE
  ):
    if not self._check_auth(update.effective_user.id):
      return

    await update.message.reply_text(
      "Screenshot functionality is not implemented yet."
    )

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
