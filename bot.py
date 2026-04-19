import asyncio
import os
import random
import re
from datetime import datetime, timedelta
from typing import Dict
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# ============ CONFIGURATION ============
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
PORT = int(os.environ.get("PORT", 8080))

if not BOT_TOKEN:
    print("❌ ERROR: TELEGRAM_BOT_TOKEN not found!")
    exit(1)

print(f"✅ Bot token loaded")
print(f"✅ Port: {PORT}")

# ============ SIMPLE HTTP SERVER FOR HEALTH CHECK ============
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Bot is running')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress HTTP server logs

def run_health_server():
    server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
    server.serve_forever()

# ============ STORAGE ============
active_campaigns: Dict[int, Dict] = {}

# ============ CONTENT GENERATOR ============
def generate_post(topic: str, day: int, post_number: int) -> str:
    templates = [
        f"📚 **{topic.upper()} INSIGHTS**\n\nHere's what you need to know about {topic} today!\n\n#{topic.replace(' ', '')}",
        f"🤔 **LET'S DISCUSS {topic.upper()}**\n\nWhat's your experience with {topic}? Share below! 👇",
        f"💡 **{topic.upper()} TIP**\n\nStay consistent with {topic} and you'll see results! 🚀",
        f"📢 **{topic.upper()} UPDATE**\n\nThe {topic} world is evolving fast. Stay tuned!",
        f"🔥 **{topic.upper()} MOTIVATION**\n\nKeep pushing forward with {topic}! 💪"
    ]
    template = templates[post_number % len(templates)]
    return f"{template}\n\n📅 Day {day} • Post {post_number}/16"

# ============ BOT ============
class SimpleBot:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 *Auto Content Bot*\n\n"
            "Send: `@channel | topic | days`\n\n"
            "Example: `@AIToolsDail | AI Tools | 7 days`\n\n"
            "Commands: /status, /stop",
            parse_mode="Markdown"
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        if '|' in text:
            parts = [p.strip() for p in text.split('|')]
            if len(parts) != 3:
                await update.message.reply_text("❌ Use: `@channel | topic | days`")
                return
            
            channel, topic = parts[0], parts[1]
            days_match = re.search(r'(\d+)', parts[2])
            if not days_match:
                await update.message.reply_text("❌ Specify days: `7 days`")
                return
            
            days = int(days_match.group(1))
            
            if not channel.startswith('@'):
                await update.message.reply_text("❌ Channel must start with @")
                return
            
            if user_id in active_campaigns:
                try:
                    self.scheduler.remove_job(f"job_{user_id}")
                except:
                    pass
            
            end_date = datetime.now() + timedelta(days=days)
            active_campaigns[user_id] = {
                'channel': channel, 'topic': topic, 'days': days,
                'start_date': datetime.now(), 'end_date': end_date,
                'posts_made': 0, 'post_num': 1
            }
            
            self.scheduler.add_job(
                self.post_to_channel,
                trigger=IntervalTrigger(minutes=90),
                args=[user_id],
                id=f"job_{user_id}"
            )
            
            await update.message.reply_text(
                f"✅ *Campaign Started!*\n\n📢 {channel}\n📝 {topic}\n📅 {days} days\n⏱️ Posts every 90 minutes",
                parse_mode="Markdown"
            )
            await asyncio.sleep(2)
            await self.post_to_channel(user_id)
        else:
            await self.start(update, context)
    
    async def post_to_channel(self, user_id: int):
        campaign = active_campaigns.get(user_id)
        if not campaign or datetime.now() > campaign['end_date']:
            return
        
        day = (datetime.now() - campaign['start_date']).days + 1
        post = generate_post(campaign['topic'], day, campaign['post_num'])
        
        try:
            await context.bot.send_message(
                chat_id=campaign['channel'],
                text=post,
                parse_mode="Markdown"
            )
            campaign['posts_made'] += 1
            campaign['post_num'] += 1
            if campaign['post_num'] > 16:
                campaign['post_num'] = 1
            print(f"✅ Posted to {campaign['channel']} - #{campaign['posts_made']}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        campaign = active_campaigns.get(update.effective_user.id)
        if not campaign:
            await update.message.reply_text("❌ No active campaign")
            return
        days_left = (campaign['end_date'] - datetime.now()).days
        await update.message.reply_text(
            f"📊 *Status*\n\n📢 {campaign['channel']}\n📝 {campaign['topic']}\n📨 Posts: {campaign['posts_made']}\n📅 {days_left} days left",
            parse_mode="Markdown"
        )
    
    async def stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in active_campaigns:
            try:
                self.scheduler.remove_job(f"job_{user_id}")
            except:
                pass
            del active_campaigns[user_id]
            await update.message.reply_text("✅ Campaign stopped")
        else:
            await update.message.reply_text("❌ No active campaign")

# ============ MAIN ============
async def main():
    application = Application.builder().token(BOT_TOKEN).build()
    bot = SimpleBot()
    
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("status", bot.status))
    application.add_handler(CommandHandler("stop", bot.stop))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Start bot polling
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print(f"✅ Bot is running! Send /start to your bot")
    
    # Start health check server in a separate thread
    import threading
    thread = threading.Thread(target=run_health_server, daemon=True)
    thread.start()
    print(f"✅ Health check server running on port {PORT}")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
