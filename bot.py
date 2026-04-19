import asyncio
import os
import re
from datetime import datetime, timedelta
from typing import Dict

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# ============ CONFIGURATION ============
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

if not BOT_TOKEN:
    print("❌ ERROR: TELEGRAM_BOT_TOKEN not found!")
    exit(1)

print("🤖 Bot Starting...")
print(f"✅ Token loaded: {BOT_TOKEN[:10]}...")

# ============ STORAGE ============
active_campaigns: Dict[int, Dict] = {}

# ============ SIMPLE BOT ============
class SimpleBot:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
        print("✅ Scheduler started")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 *Auto Post Bot*\n\n"
            "Send: `@channel | topic | days`\n\n"
            "Example: `@modernlovetips | Love Tips | 7 days`\n\n"
            "Commands:\n"
            "/status - Check campaign\n"
            "/stop - Stop campaign",
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
            
            channel = parts[0]
            topic = parts[1]
            
            days_match = re.search(r'(\d+)', parts[2])
            if not days_match:
                await update.message.reply_text("❌ Specify days: `7 days`")
                return
            
            days = int(days_match.group(1))
            
            if not channel.startswith('@'):
                await update.message.reply_text("❌ Channel must start with @")
                return
            
            # Test if bot can post
            try:
                await context.bot.send_message(
                    chat_id=channel,
                    text=f"✅ Bot is active! Campaign starting for: {topic}"
                )
                await update.message.reply_text(f"✅ Bot can post to {channel}")
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Cannot post to {channel}\nError: {str(e)[:100]}\n\n"
                    f"Make sure bot is admin in {channel}"
                )
                return
            
            # Stop existing campaign
            if user_id in active_campaigns:
                try:
                    self.scheduler.remove_job(f"job_{user_id}")
                except:
                    pass
            
            end_date = datetime.now() + timedelta(days=days)
            total_posts = days * 16
            
            active_campaigns[user_id] = {
                'channel': channel,
                'topic': topic,
                'days': days,
                'start_date': datetime.now(),
                'end_date': end_date,
                'posts_made': 0,
                'post_num': 1,
                'total_posts': total_posts
            }
            
            # Schedule posts every 90 minutes
            self.scheduler.add_job(
                self.post_to_channel,
                trigger=IntervalTrigger(minutes=90),
                args=[user_id],
                id=f"job_{user_id}"
            )
            
            await update.message.reply_text(
                f"✅ *Campaign Started!*\n\n"
                f"📢 {channel}\n"
                f"📝 {topic}\n"
                f"📅 {days} days\n"
                f"⏱️ Posts every 90 minutes\n\n"
                f"First post coming soon...",
                parse_mode="Markdown"
            )
            
            await asyncio.sleep(2)
            await self.post_to_channel(user_id)
        
        else:
            await self.start(update, context)
    
    async def post_to_channel(self, user_id: int):
        campaign = active_campaigns.get(user_id)
        if not campaign:
            return
        
        if datetime.now() > campaign['end_date']:
            await self.end_campaign(user_id)
            return
        
        day = (datetime.now() - campaign['start_date']).days + 1
        post_num = campaign['post_num']
        
        # Simple post
        post = f"💖 *{campaign['topic'].upper()}* 💖\n\n"
        post += f"Post #{post_num} • Day {day} of {campaign['days']}\n\n"
        post += f"Stay tuned for more {campaign['topic']} content!\n\n"
        post += f"#{campaign['topic'].replace(' ', '')}"
        
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
            
            print(f"✅ Posted to {campaign['channel']} - Post #{campaign['posts_made']}")
            
        except Exception as e:
            print(f"❌ Error posting: {e}")
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        campaign = active_campaigns.get(user_id)
        
        if not campaign:
            await update.message.reply_text("❌ No active campaign. Send: `@channel | topic | days`")
            return
        
        days_passed = (datetime.now() - campaign['start_date']).days
        days_left = (campaign['end_date'] - datetime.now()).days
        progress = (campaign['posts_made'] / campaign['total_posts']) * 100 if campaign['total_posts'] > 0 else 0
        
        # Progress bar
        bar_length = 15
        filled = int(bar_length * progress / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        await update.message.reply_text(
            f"📊 *Campaign Status*\n\n"
            f"📢 Channel: {campaign['channel']}\n"
            f"📝 Topic: {campaign['topic']}\n\n"
            f"📨 Posts: {campaign['posts_made']} / {campaign['total_posts']}\n"
            f"📅 Day {days_passed + 1} of {campaign['days']}\n"
            f"⏰ {days_left} days left\n"
            f"📊 Progress: {bar} {progress:.0f}%\n\n"
            f"Use /stop to end campaign",
            parse_mode="Markdown"
        )
    
    async def stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in active_campaigns:
            await update.message.reply_text("❌ No active campaign")
            return
        
        campaign = active_campaigns[user_id]
        
        try:
            self.scheduler.remove_job(f"job_{user_id}")
        except:
            pass
        
        posts_made = campaign['posts_made']
        topic = campaign['topic']
        
        del active_campaigns[user_id]
        
        await update.message.reply_text(
            f"🛑 *Campaign Stopped*\n\n"
            f"📝 Topic: {topic}\n"
            f"📨 Posts made: {posts_made}\n\n"
            f"Start a new campaign with /start",
            parse_mode="Markdown"
        )
    
    async def end_campaign(self, user_id: int):
        if user_id in active_campaigns:
            campaign = active_campaigns[user_id]
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ *Campaign Complete!*\n\n"
                         f"Topic: {campaign['topic']}\n"
                         f"Total posts: {campaign['posts_made']}\n\n"
                         f"Start a new campaign with /start"
                )
            except:
                pass
            del active_campaigns[user_id]
        
        try:
            self.scheduler.remove_job(f"job_{user_id}")
        except:
            pass

# ============ MAIN ============
async def main():
    print("🚀 Initializing bot...")
    
    application = Application.builder().token(BOT_TOKEN).build()
    bot = SimpleBot()
    
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("status", bot.status))
    application.add_handler(CommandHandler("stop", bot.stop))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    print("📡 Starting polling...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print("✅ Bot is LIVE and running!")
    print("💬 Send /start to your bot on Telegram")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    print("=" * 50)
    print("🌟 PREMIUM BOT DEPLOYING 🌟")
    print("=" * 50)
    asyncio.run(main())
