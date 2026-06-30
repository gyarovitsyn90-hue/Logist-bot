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

# === Состояния для машин ===
(
    NUMBER, MODEL, VOLUME, PALLETS, 
    WEIGHT, BODY_TYPE, OVERSIZED, RESTRICTIONS
) = range(8)

# === Состояния для заказов ===
(
    ORDER_NUMBER, ORDER_ADDRESS, ORDER_DATE, 
    ORDER_VEHICLE, ORDER_COMMENT
) = range(10, 15)


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


# === Основные команды ===
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


# === Разговорное добавление машины ===
async def addcar_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите гос. номер машины:")
    return NUMBER


async def addcar_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["number"] = update.message.text
    await update.message.reply_text("Введите модель машины:")
    return MODEL


async def addcar_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["model"] = update.message.text
    await update.message.reply_text("Введите объём кузова в м³:")
    return VOLUME


async def addcar_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["volume"] = float(update.message.text)
    await update.message.reply_text("Сколько паллет вмещает?")
    return PALLETS


async def addcar_pallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pallets"] = int(update.message.text)
    await update.message.reply_text("Максимальная грузоподъёмность (кг):")
    return WEIGHT


async def addcar_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["weight"] = int(update.message.text)
    await update.message.reply_text("Тип кузова (тент / будка / фургон):")
    return BODY_TYPE


async def addcar_body_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["body_type"] = update.message.text
    await update.message.reply_text("Можно возить негабарит? (да / нет):")
    return OVERSIZED


async def addcar_oversized(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["oversized"] = 1 if update.message.text.lower() in ["да", "yes", "1"] else 0
    await update.message.reply_text("Ограничения по маршрутам (или напиши - ):")
    return RESTRICTIONS


async def addcar_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["restrictions"] = update.message.text if update.message.text != "-" else None

    data = context.user_data
    success = add_vehicle(
        data["number"], data["model"], data["volume"],
        data["pallets"], data["weight"], data["body_type"],
        data["oversized"], data["restrictions"]
    )

    if success:
        await update.message.reply_text(f"Машина {data['number']} успешно добавлена!")
    else:
        await update.message.reply_text(f"Ошибка: машина {data['number']} уже существует.")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операция отменена.")
    context.user_data.clear()
    return ConversationHandler.END


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
