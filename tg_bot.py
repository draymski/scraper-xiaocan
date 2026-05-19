import os
import signal
import subprocess
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    raise ValueError("请在 .env 文件中设置正确的 TELEGRAM_BOT_TOKEN")

class ScraperBot:
    def __init__(self):
        self.process = None

    def check_auth(self, update: Update) -> bool:
        if not CHAT_ID or CHAT_ID == "YOUR_CHAT_ID_HERE":
            return True # 如果没有配置，就不做权限验证
        if str(update.effective_chat.id) != str(CHAT_ID):
            logging.warning(f"检测到未授权的访问尝试。Chat ID: {update.effective_chat.id}")
            return False
        return True

    async def start_scraper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.check_auth(update):
            return
        
        if self.process and self.process.poll() is None:
            await update.message.reply_text("抓包脚本已经在运行中了！")
            return

        await update.message.reply_text("正在启动抓包脚本...\n请在手机上配置代理并打开目标App。")
        
        # 确保使用虚拟环境中的 mitmdump
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 启动前清理旧的 csv 文件，防止未采集到数据时复用历史记录
        csv_path = os.path.join(current_dir, "today_results.csv")
        if os.path.exists(csv_path):
            try:
                os.remove(csv_path)
            except OSError:
                pass
                
        mitmdump_path = os.path.join(current_dir, ".venv", "bin", "mitmdump")
        script_path = os.path.join(current_dir, "xiaocan_semiauto.py")

        try:
            # 移除 stdout=PIPE 和 stderr=PIPE。
            # 因为 mitmdump 会输出大量日志，如果存入 PIPE 又不读取，缓冲区(64KB)很快会满，导致 mitmdump 卡死或异常崩溃退出。
            # 让它保持默认，输出直接混入 tg_bot 的运行日志中即可。
            self.process = subprocess.Popen(
                [mitmdump_path, "-s", script_path],
                cwd=current_dir
            )
            await update.message.reply_text("✅ 抓包脚本已启动。准备就绪后请发送 /xiaocan_end 终止并获取结果。")
        except Exception as e:
            await update.message.reply_text(f"启动失败: {e}")

    async def end_scraper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.check_auth(update):
            return

        if not self.process or self.process.poll() is not None:
            await update.message.reply_text("当前没有正在运行的抓包脚本。")
            return

        await update.message.reply_text("正在终止抓包脚本，生成结果中...")
        
        # 发送 SIGINT (等同于 Ctrl+C) 触发 mitmproxy 的 done() 钩子
        self.process.send_signal(signal.SIGINT)
        
        # 等待进程退出
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            await update.message.reply_text("⚠️ 脚本响应超时，已强制终止。")

        self.process = None
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(current_dir, "today_results.csv")

        if os.path.exists(csv_path):
            await update.message.reply_document(document=open(csv_path, 'rb'), caption="本次采集的原始CSV")
        else:
            await update.message.reply_text("本次没有采集到任何数据，未生成结果文件。")

    async def get_chat_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """用于获取当前聊天的 Chat ID"""
        chat_id = update.effective_chat.id
        await update.message.reply_text(f"当前的 Chat ID 是: `{chat_id}`\n请把它填入 .env 文件的 TELEGRAM_CHAT_ID 中以增加安全性。", parse_mode='Markdown')

def main():
    bot = ScraperBot()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("xiaocan_bgn", bot.start_scraper))
    application.add_handler(CommandHandler("xiaocan_end", bot.end_scraper))
    application.add_handler(CommandHandler("chatid", bot.get_chat_id))

    logging.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
