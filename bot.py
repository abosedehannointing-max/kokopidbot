import asyncio
import os
import re
from datetime import datetime, timedelta
from typing import Dict

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# ============ CONFIGURATION ============
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

if not BOT_TOKEN:
    print("❌ ERROR: TELEGRAM_BOT_TOKEN not found!")
    exit(1)

print("✅ Bot started")

# ============ STORAGE ============
active_campaigns: Dict[int, Dict] = {}

# ============ BOT ============
class SimpleBot:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 *Auto Content Bot*\n\n"
            "Send: `@channel | topic | days`\n\n"
            "Example: `@modernlovetips | love tips | 7 days`\n\n"
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
                    text=f"✅ Bot is active! Will now post about: {topic}"
                )
                await update.message.reply_text(f"✅ Test passed! Bot can post to {channel}")
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Cannot post to {channel}\nError: {str(e)[:100]}\n\n"
                    f"Make sure:\n1️⃣ Bot is admin in {channel}\n2️⃣ Channel name is correct"
                )
                return
            
            # Stop existing campaign
            if user_id in active_campaigns:
                try:
                    self.scheduler.remove_job(f"job_{user_id}")
                except:
                    pass
            
            end_date = datetime.now() + timedelta(days=days)
            active_campaigns[user_id] = {
                'channel': channel,
                'topic': topic,
                'days': days,
                'start_date': datetime.now(),
                'end_date': end_date,
                'posts_made': 0,
                'post_num': 1
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
                f"⏱️ Posts every 90 minutes",
                parse_mode="Markdown"
            )
            
            # Send first post
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
        
        # Simple post template
        templates = [
            f"💖 *{campaign['topic'].upper()}* - Part {post_num}\n\nTrue love is patient and kind. Keep nurturing your relationship!\n\n📅 Day {day} of {campaign['days']}",
            f"🌹 *{campaign['topic'].upper()} TIP*\n\nCommunication is key. Listen with your heart.\n\n📅 Day {day} • Post {post_num}/16",
            f"✨ *{campaign['topic'].upper()} INSIGHT*\n\nSmall gestures make big differences in love.\n\n📅 Day {day} • Post {post_num}/16"
        ]
        
        post = templates[post_num % len(templates)]
        post += f"\n\n#{campaign['topic'].replace(' ', '')}"
        
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
            print(f"❌ Error posting: {e}")
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        campaign = active_campaigns.get(update.effective_user.id)
        if not campaign:
            await update.message.reply_text("❌ No active campaign. Send: `@channel | topic | days`")
            return
        
        days_left = (campaign['end_date'] - datetime.now()).days
        await update.message.reply_text(
            f"📊 *Campaign Status*\n\n"
            f"📢 Channel: {campaign['channel']}\n"
            f"📝 Topic: {campaign['topic']}\n"
            f"📨 Posts made: {campaign['posts_made']}\n"
            f"📅 {days_left} days remaining\n\n"
            f"Use /stop to end",
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
    
    async def end_campaign(self, user_id: int):
        if user_id in active_campaigns:
            del active_campaigns[user_id]
        try:
            self.scheduler.remove_job(f"job_{user_id}")
        except:
            pass

# ============ MAIN ============
async def main():
    application = Application.builder().token(BOT_TOKEN).build()
    bot = SimpleBot()
    
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("status", bot.status))
    application.add_handler(CommandHandler("stop", bot.stop))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Start bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print("✅ Bot is running! Send /start to your bot")
    
    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
