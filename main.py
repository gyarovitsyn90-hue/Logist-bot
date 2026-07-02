import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO
from datetime import datetime, timedelta
from collections import defaultdict

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
import pandas as pd

from database import init_db, replace_all_vehicles, get_active_vehicles

# ==================== МЕНЮ ====================

def get_main_menu():
    keyboard = [
        [KeyboardButton("🚚 Машины"), KeyboardButton("📦 Заказы")],
        [KeyboardButton("📊 Сформировать план на завтра")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_machines_menu():
    keyboard = [
        [InlineKeyboardButton("➕ Добавить машину", callback_data="machine_add")],
        [InlineKeyboardButton("✏️ Редактировать машину", callback_data="machine_edit")],
        [InlineKeyboardButton("🗑️ Удалить машину", callback_data="machine_delete")],
        [InlineKeyboardButton("📥 Импорт машин (Excel)", callback_data="machine_import")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_orders_menu():
    keyboard = [
        [InlineKeyboardButton("➕ Добавить заказ", callback_data="order_add")],
        [InlineKeyboardButton("📥 Импорт заказов (Excel)", callback_data="order_import")],
        [InlineKeyboardButton("📊 Сформировать план на завтра", callback_data="auto_plan")],
        [InlineKeyboardButton("📋 Посмотреть заказы", callback_data="view_orders")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ==================== ОСНОВНЫЕ КОМАНДЫ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добро пожаловать в бот логистики!",
        reply_markup=get_main_menu()
    )


async def show_machines_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Управление машинами:", reply_markup=get_machines_menu())


async def show_orders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Управление заказами:", reply_markup=get_orders_menu())


# ==================== CALLBACK МЕНЮ ====================

async def machines_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "machine_add":
        await query.edit_message_text("Функция добавления машины будет добавлена позже.")
    elif query.data == "machine_edit":
        await query.edit_message_text("Функция редактирования будет добавлена позже.")
    elif query.data == "machine_delete":
        await query.edit_message_text("Функция удаления будет добавлена позже.")
    elif query.data == "machine_import":
        await query.edit_message_text(
            "Пришлите Excel-файл с машинами.\n\n"
            "⚠️ Внимание: импорт полностью заменит текущий список машин!"
        )
        context.user_data["awaiting_machine_import"] = True


async def orders_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "order_add":
        await query.edit_message_text("Функция добавления заказа будет добавлена позже.")
    elif query.data == "order_import":
        await query.edit_message_text("Пришлите Excel-файл с заказами.")
        context.user_data["awaiting_order_import"] = True
    elif query.data == "auto_plan":
        await query.edit_message_text("Функция автоматического плана в активной разработке.")
    elif query.data == "view_orders":
        await query.edit_message_text("Функция просмотра заказов будет добавлена позже.")


# ==================== ИМПОРТ ====================

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document

    # Импорт машин
    if context.user_data.get("awaiting_machine_import"):
        if not document.file_name.endswith((".xlsx", ".xls")):
            await update.message.reply_text("Нужно прислать Excel-файл (.xlsx или .xls)")
            return

        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()

        try:
            df = pd.read_excel(BytesIO(file_bytes))
            df.columns = [str(col).lower().strip() for col in df.columns]

            vehicles = []
            for _, row in df.iterrows():
                try:
                    number = str(row.iloc[0]).strip()
                    if not number:
                        continue

                    model = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else None
                    volume = float(row.iloc[2]) if pd.notna(row.iloc[2]) else 0
                    pallets = int(row.iloc[3]) if pd.notna(row.iloc[3]) else 0
                    weight = int(row.iloc[4]) if pd.notna(row.iloc[4]) else 0
                    restrictions = str(row.iloc[7]).strip() if pd.notna(row.iloc[7]) else None

                    vehicles.append((number, model, volume, pallets, weight, None, 0, None, None, restrictions, 1))
                except:
                    continue

            if vehicles:
                added = replace_all_vehicles(vehicles)
                await update.message.reply_text(f"Импорт машин завершён!\nДобавлено: {added} машин")
            else:
                await update.message.reply_text("Не удалось найти подходящие данные для импорта.")

        except Exception as e:
            await update.message.reply_text(f"Ошибка при чтении файла: {str(e)}")

        context.user_data["awaiting_machine_import"] = False
        return

    # Импорт заказов
    if context.user_data.get("awaiting_order_import"):
        await update.message.reply_text("Импорт заказов принят. Полная обработка будет добавлена в следующей версии.")
        context.user_data["awaiting_order_import"] = False
        return


# ==================== ЗАПУСК ====================

def main():
    init_db()

    application = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^🚚 Машины$"), show_machines_menu))
    application.add_handler(MessageHandler(filters.Regex("^📦 Заказы$"), show_orders_menu))

    application.add_handler(CallbackQueryHandler(machines_menu_handler, pattern="^machine_"))
    application.add_handler(CallbackQueryHandler(orders_menu_handler, pattern="^order_|^auto_plan|^view_orders"))

    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("[INFO] Бот запущен (новая версия)")
    application.run_polling()


if __name__ == "__main__":
    main()
