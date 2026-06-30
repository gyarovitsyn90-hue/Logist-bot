import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from io import BytesIO

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler
)
import openpyxl

from database import init_db, add_vehicle, bulk_add_vehicles, get_all_vehicles

# Состояния для разговорного добавления машины
(
    NUMBER, MODEL, VOLUME, PALLETS, 
    WEIGHT, BODY_TYPE, OVERSIZED, RESTRICTIONS
) = range(8)


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
        "Основные команды:\n"
        "/cars — список машин\n"
        "/addcar — добавить машину (по шагам)\n"
        "/importcars — загрузить машины из Excel"
    )


async def cars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vehicles = get_all_vehicles()
    if not vehicles:
        await update.message.reply_text("Машин пока нет.")
        return

    text = "Список машин:\n\n"
    for v in vehicles:
        text += (
            f"🚚 {v[1]} ({v[2]})\n"
            f"   Объём: {v[3]} м³ | Паллет: {v[4]} | Вес: {v[5]} кг\n"
            f"   Тип: {v[6] or '-'}\n\n"
        )
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
    await update.message.reply_text("Добавление отменено.")
    context.user_data.clear()
    return ConversationHandler.END


async def importcars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Пришли Excel-файл (.xlsx) со списком машин.\n\n"
        "Название файла и листа может быть любым."
    )
    context.user_data["awaiting_file"] = True


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_file"):
        return

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
        f"Импорт завершён!\n\n"
        f"Добавлено: {added}\n"
        f"Пропущено (дубликаты): {skipped}"
    )
    context.user_data["awaiting_file"] = False


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

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cars", cars))
    application.add_handler(addcar_conv)
    application.add_handler(CommandHandler("importcars", importcars))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("[INFO] Бот запущен")
    application.run_polling()


if __name__ == "__main__":
    main()
