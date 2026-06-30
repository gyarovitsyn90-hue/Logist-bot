import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler
)
import openpyxl

from database import init_db, add_vehicle, bulk_add_vehicles, get_all_vehicles

# Состояния для машин
(
    NUMBER, MODEL, VOLUME, PALLETS, 
    WEIGHT, BODY_TYPE, OVERSIZED, RESTRICTIONS
) = range(8)

# Состояния для заказов
(
    ORDER_NUMBER, ORDER_ADDRESS, ORDER_DATE, 
    ORDER_VEHICLE, ORDER_COMMENT
) = range(5, 10)


# === HTTP Health-check ===
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"[INFO] Health-check сервер запущен на порту {port}")
    server.serve_forever()


# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот логистики\n\n"
        "Команды:\n"
        "/cars — список машин\n"
        "/addcar — добавить машину\n"
        "/addorder — добавить заказ\n"
        "/importcars — загрузить машины из Excel"
    )


async def cars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vehicles = get_all_vehicles()
    if not vehicles:
        await update.message.reply_text("Машин пока нет.")
        return

    text = "Список машин:\n\n"
    for v in vehicles:
        text += f"ID {v[0]} | {v[1]} | {v[2]} | {v[3]}м³ | {v[4]} паллет\n"
    await update.message.reply_text(text)


# === Разговорное добавление заказа ===
async def addorder_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите номер заказа или название клиента:")
    return ORDER_NUMBER


async def addorder_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order_number"] = update.message.text
    await update.message.reply_text("Введите адрес доставки:")
    return ORDER_ADDRESS


async def addorder_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = update.message.text
    await update.message.reply_text("Дата доставки? (сегодня / завтра)")
    return ORDER_DATE


async def addorder_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "сегодня" in text:
        context.user_data["delivery_date"] = datetime.now().strftime("%Y-%m-%d")
    elif "завтра" in text:
        context.user_data["delivery_date"] = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        context.user_data["delivery_date"] = text

    # Показываем список машин
    vehicles = get_all_vehicles()
    text = "Выберите машину (введите ID):\n\n"
    for v in vehicles:
        text += f"ID {v[0]} — {v[1]} ({v[2]})\n"
    await update.message.reply_text(text)
    return ORDER_VEHICLE


async def addorder_vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        vehicle_id = int(update.message.text)
    except:
        await update.message.reply_text("Пожалуйста, введите ID машины цифрами.")
        return ORDER_VEHICLE

    context.user_data["vehicle_id"] = vehicle_id
    await update.message.reply_text("Комментарий к заказу (или напиши - ):")
    return ORDER_COMMENT


async def addorder_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    comment = update.message.text if update.message.text != "-" else None
    context.user_data["comment"] = comment

    data = context.user_data

    # Здесь позже добавим сохранение в базу
    await update.message.reply_text(
        f"Заказ создан!\n\n"
        f"Номер: {data['order_number']}\n"
        f"Адрес: {data['address']}\n"
        f"Дата: {data['delivery_date']}\n"
        f"Машина ID: {data['vehicle_id']}\n"
        f"Комментарий: {data.get('comment', '-')}"
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операция отменена.")
    context.user_data.clear()
    return ConversationHandler.END


def main():
    init_db()

    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    application = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    # Разговорное добавление машины
    addcar_conv = ConversationHandler(
        entry_points=[CommandHandler("addcar", addcar_start)],
        states={
            NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, addcar_number)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, addcar_model)],
            VOLUME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addcar_volume)],
            PALLETS: [MessageHandler(filters.TEXT & ~filters.COMMAND, addcar_pallets)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, addcar_weight)],
            BODY_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addcar_body_type)],
            OVERSIZED: [MessageHandler(filters.TEXT & ~filters.COMMAND, addcar_oversized)],
            RESTRICTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, addcar_finish)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Разговорное добавление заказа
    addorder_conv = ConversationHandler(
        entry_points=[CommandHandler("addorder", addorder_start)],
        states={
            ORDER_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, addorder_number)],
            ORDER_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, addorder_address)],
            ORDER_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addorder_date)],
            ORDER_VEHICLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addorder_vehicle)],
            ORDER_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, addorder_comment)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cars", cars))
    application.add_handler(addcar_conv)
    application.add_handler(addorder_conv)

    print("[INFO] Бот запущен")
    application.run_polling()


if __name__ == "__main__":
    main()
