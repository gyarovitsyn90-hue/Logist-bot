import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from database import init_db, add_vehicle, get_all_vehicles


# === HTTP Health-check ===
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass

def run_health_server():
    port = int(os.getenv("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"[INFO] Health-check сервер запущен на порту {port}")
    server.serve_forever()


# === Команды бота ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Бот для логистики.\n\n"
        "Команды:\n"
        "/cars — список машин\n"
        "/addcar — добавить машину"
    )


async def cars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vehicles = get_all_vehicles()
    if not vehicles:
        await update.message.reply_text("Машин пока нет. Добавь первую командой /addcar")
        return

    text = "Список машин:\n\n"
    for v in vehicles:
        text += f"ID: {v[0]} | {v[1]} | {v[2] or '-'} | Вместимость: {v[3]}\n"
    await update.message.reply_text(text)


async def addcar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 1:
        await update.message.reply_text(
            "Использование: /addcar <номер> [модель] [вместимость]\n\n"
            "Пример: /addcar A123BC 50"
        )
        return

    number = args[0]
    model = args[1] if len(args) > 1 else None
    capacity = int(args[2]) if len(args) > 2 else 0

    success = add_vehicle(number, model, capacity)
    if success:
        await update.message.reply_text(f"Машина {number} успешно добавлена!")
    else:
        await update.message.reply_text(f"Ошибка: машина с номером {number} уже существует.")


def main():
    init_db()

    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    application = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cars", cars))
    application.add_handler(CommandHandler("addcar", addcar))

    print("[INFO] Бот запущен")
    application.run_polling()


if __name__ == "__main__":
    main()
