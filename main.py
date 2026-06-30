import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO
from datetime import datetime, timedelta

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler
)
import openpyxl

from database import (
    init_db, add_vehicle, bulk_add_vehicles, bulk_add_orders, 
    get_all_vehicles, get_orders_by_date, delete_order, update_order_vehicle
)

# === Состояния ===
(
    NUMBER, MODEL, VOLUME, PALLETS, 
    WEIGHT, BODY_TYPE, OVERSIZED, RESTRICTIONS
) = range(8)

(
    ORDER_NUMBER, ORDER_ADDRESS, ORDER_DATE, 
    ORDER_VEHICLE, ORDER_COMMENT
) = range(10, 15)


# === Главное меню с смайликами ===
def get_main_menu():
    keyboard = [
        [KeyboardButton("🚚 Машины"), KeyboardButton("📦 Заказы")],
        [KeyboardButton("➕ Добавить машину"), KeyboardButton("➕ Добавить заказ")],
        [KeyboardButton("🗑️ Удалить заказ"), KeyboardButton("🔄 Сменить машину")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


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
        "Добро пожаловать в бот логистики!",
        reply_markup=get_main_menu()
    )


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Главное меню:",
        reply_markup=get_main_menu()
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


async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    orders_today = get_orders_by_date(today)
    orders_tomorrow = get_orders_by_date(tomorrow)

    text = "📅 **Заказы на сегодня:**\n\n"
    if orders_today:
        for o in orders_today:
            text += f"• {o[1]} | {o[3]} | Машина: {o[7] or 'не назначена'}\n"
    else:
        text += "Заказов нет\n"

    text += "\n📅 **Заказы на завтра:**\n\n"
    if orders_tomorrow:
        for o in orders_tomorrow:
            text += f"• {o[1]} | {o[3]} | Машина: {o[7] or 'не назначена'}\n"
    else:
        text += "Заказов нет\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def deleteorder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Использование: /deleteorder <ID заказа>")
        return

    try:
        order_id = int(args[0])
    except:
        await update.message.reply_text("ID должен быть числом.")
        return

    success = delete_order(order_id)
    if success:
        await update.message.reply_text(f"Заказ №{order_id} удалён.")
    else:
        await update.message.reply_text("Заказ не найден.")


async def changevehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Использование: /changevehicle <ID заказа> <ID машины>")
        return

    try:
        order_id = int(args[0])
        vehicle_id = int(args[1])
    except:
        await update.message.reply_text("ID должны быть числами.")
        return

    success = update_order_vehicle(order_id, vehicle_id)
    if success:
        await update.message.reply_text(f"У заказа №{order_id} изменена машина.")
    else:
        await update.message.reply_text("Заказ не найден.")


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
        await update.message.reply_text(f"Машина {data['number']} добавлена!")
    else:
        await update.message.reply_text(f"Ошибка: машина {data['number']} уже существует.")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.")
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
        context.user_data["vehicle_id"] = int(update.message.text)
    except:
        await update.message.reply_text("Введите ID машины цифрами.")
        return ORDER_VEHICLE

    await update.message.reply_text("Комментарий (или - ):")
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
        f"Машина ID: {data['vehicle_id']}"
    )

    context.user_data.clear()
    return ConversationHandler.END


async def importcars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Пришли Excel-файл с машинами.")
    context.user_data["awaiting_file"] = True


async def importorders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Пришли Excel-файл с заказами.")
    context.user_data["awaiting_order_file"] = True


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_file"):
        document = update.message.document
        if not document.file_name.endswith((".xlsx", ".xls")):
            await update.message.reply_text("Нужно прислать Excel-файл (.xlsx)")
            return

        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        workbook = openpyxl.load_workbook(BytesIO(file_bytes))
        sheet = workbook.active

        vehicles = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if row[0]:
                vehicles.append((
                    row[0], row[1], row[2] or 0, row[3] or 0,
                    row[4] or 0, row[7],
                    1 if "Негабарит: Да" in str(row[7]) else 0,
                    row[5]
                ))

        added, skipped = bulk_add_vehicles(vehicles)
        await update.message.reply_text(
            f"Импорт машин завершён!\nДобавлено: {added} | Пропущено: {skipped}"
        )
        context.user_data["awaiting_file"] = False
        return

    if context.user_data.get("awaiting_order_file"):
        document = update.message.document
        if not document.file_name.endswith((".xlsx", ".xls")):
            await update.message.reply_text("Нужно прислать Excel-файл (.xlsx)")
            return

        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        workbook = openpyxl.load_workbook(BytesIO(file_bytes))
        sheet = workbook.active

        orders = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if row[0]:
                orders.append((
                    row[0], row[1], row[2], row[3], row[4]
                ))

        added, skipped = bulk_add_orders(orders)
        await update.message.reply_text(
            f"Импорт заказов завершён!\nДобавлено: {added} | Пропущено: {skipped}"
        )
        context.user_data["awaiting_order_file"] = False
        return


def main():
    init_db()

    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    application = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

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
    application.add_handler(CommandHandler("menu", show_menu))
    application.add_handler(CommandHandler("cars", cars))
    application.add_handler(CommandHandler("orders", orders))
    application.add_handler(CommandHandler("deleteorder", deleteorder))
    application.add_handler(CommandHandler("changevehicle", changevehicle))
    application.add_handler(addcar_conv)
    application.add_handler(addorder_conv)
    application.add_handler(CommandHandler("importcars", importcars))
    application.add_handler(CommandHandler("importorders", importorders))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Обработка кнопок меню
    application.add_handler(MessageHandler(filters.Regex("^🚚 Машины$"), cars))
    application.add_handler(MessageHandler(filters.Regex("^📦 Заказы$"), orders))
    application.add_handler(MessageHandler(filters.Regex("^➕ Добавить машину$"), addcar_start))
    application.add_handler(MessageHandler(filters.Regex("^➕ Добавить заказ$"), addorder_start))
    application.add_handler(MessageHandler(filters.Regex("^🗑️ Удалить заказ$"), deleteorder))
    application.add_handler(MessageHandler(filters.Regex("^🔄 Сменить машину$"), changevehicle))

    print("[INFO] Бот запущен")
    application.run_polling()


if __name__ == "__main__":
    main()
