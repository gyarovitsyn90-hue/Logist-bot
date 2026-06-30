import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === HTTP Health-check сервер (обязательно для Bohost) ===
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


# === Telegram бота ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для логистики.\n"
        "Используй команды:\n"
        "/cars — список машин\n"
        "/addcar — добавить машину"
    )


def main():
    # Запуск HTTP health-check сервера
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    # Запуск Telegram бота
    application = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    application.add_handler(CommandHandler("start", start))

    print("[INFO] Бот запущен в режиме Long Polling")
    application.run_polling()


if __name__ == "__main__":
    main()
