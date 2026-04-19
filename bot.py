import asyncio
import os
import re
from datetime import datetime, timedelta
from typing import Dict
import threading

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

if not BOT_TOKEN:
    print("❌ ERROR: TELEGRAM_BOT_TOKEN not set!")
    exit(1)

print(f"✅ Bot starting...")

# Store campaigns
active_campaigns: Dict[int, Dict] = {}

# ============ POSTING LOOP ============
async def posting_loop(application):
    """Background loop that posts every 90 minutes"""
    while True:
        try:
            current_time = datetime.now()
            
            for user_id, campaign in list(active_campaigns.items()):
                # Check if campaign is still active
                if current_time > campaign['end_date']:
                    # Campaign expired
                    del active_campaigns[user_id]
                    try:
                        await application.bot.send_message(
                            chat_id=user_id,
                            text=f"✅ *Campaign Completed!*\n\nTopic: {campaign['topic']}\nTotal posts: {campaign['posts_made']}",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
                    continue
                
                # Check if it's time to post (every 90 minutes)
                time_since_last = (current_time - campaign['last_post_time']).total_seconds()
                
                if time_since_last >= 5400:  # 90 minutes in seconds
                    # Generate post
                    campaign['post_number'] += 1
                    campaign['posts_made'] += 1
                    day = (current_time - campaign['start_date']).days + 1
                    
                    # Different post templates
                    templates = [
                        f"💖 *{campaign['topic'].upper()}* 💖\n\nPost #{campaign['post_number']} • Day {day}\n\nStay consistent in love! Small gestures matter.\n\n#{campaign['topic'].replace(' ', '')}",
                        
                        f"💕 *Love Tip #{campaign['post_number']}* 💕\n\nDay {day}: True love grows when both partners feel heard and valued.\n\n#{campaign['topic'].replace(' ', '')}",
                        
                        f"✨ *{campaign['topic'].upper()} INSIGHT* ✨\n\nDay {day} • Post {campaign['post_number']}\n\nA healthy relationship needs trust, respect, and communication.\n\n#{campaign['topic'].replace(' ', '')}",
                        
                        f"🌹 *Daily Love Wisdom* 🌹\n\nDay {day}: Love isn't about finding the perfect person, but learning to see an imperfect person perfectly.\n\n#{campaign['topic'].replace(' ', '')}"
                    ]
                    
                    post_text = templates[campaign['post_number'] % len(templates)]
                    
                    try:
                        await application.bot.send_message(
                            chat_id=campaign['channel'],
                            text=post_text,
                            parse_mode="Markdown"
                        )
                        campaign['last_post_time'] = current_time
                        print(f"✅ Posted to {campaign['channel']} - Post #{campaign['posts_made']}")
                        
                    except Exception as e:
                        print(f"❌ Error posting to {campaign['channel']}: {e}")
            
        except Exception as e:
            print(f"❌ Loop error: {e}")
        
        # Check every 30 seconds
        await asyncio.sleep(30)

# ============ BOT CLASS ============
class WorkingBot:
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 *Auto Post Bot* 🤖\n\n"
            "To start a campaign, send:\n"
            "`@channel | topic | days`\n\n"
            "*Example:*\n"
            "`@modernlovetips | Love Tips | 3 days`\n\n"
            "*Commands:*\n"
            "/status - Check progress\n"
            "/stop - Stop campaign",
            parse_mode="Markdown"
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        # Check for campaign setup
        if '|' in text:
            parts = [p.strip() for p in text.split('|')]
            
            if len(parts) != 3:
                await update.message.reply_text("❌ Use: `@channel | topic | days`")
                return
            
            channel = parts[0]
            topic = parts[1]
            
            # Extract days
            days_match = re.search(r'(\d+)', parts[2])
            if not days_match:
                await update.message.reply_text("❌ Please specify days (e.g., '7 days')")
                return
            
            days = int(days_match.group(1))
            
            if not channel.startswith('@'):
                await update.message.reply_text("❌ Channel must start with @")
                return
            
            # Test if bot can post
            try:
                await context.bot.send_message(
                    chat_id=channel,
                    text=f"✅ Campaign activated! I'll post about {topic} every 90 minutes for {days} days."
                )
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Cannot post to {channel}\n"
                    f"Error: {str(e)[:100]}\n\n"
                    f"Make sure:\n"
                    f"1️⃣ Bot is admin in {channel}\n"
                    f"2️⃣ Channel name is correct"
                )
                return
            
            # Store campaign
            active_campaigns[user_id] = {
                'channel': channel,
                'topic': topic,
                'days': days,
                'start_date': datetime.now(),
                'end_date': datetime.now() + timedelta(days=days),
                'posts_made': 0,
                'post_number': 0,
                'last_post_time': datetime.now()  # Start timer now
            }
            
            await update.message.reply_text(
                f"✅ *CAMPAIGN STARTED!*\n\n"
                f"📢 Channel: {channel}\n"
                f"📝 Topic: {topic}\n"
                f"📅 Duration: {days} days\n"
                f"⏱️ Posts every: 90 minutes\n\n"
                f"First post will arrive in 90 minutes!\n"
                f"Use /status to track progress",
                parse_mode="Markdown"
            )
        else:
            await self.start(update, context)
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in active_campaigns:
            await update.message.reply_text("❌ No active campaign. Send: `@channel | topic | days`")
            return
        
        campaign = active_campaigns[user_id]
        days_passed = (datetime.now() - campaign['start_date']).days
        days_left = (campaign['end_date'] - datetime.now()).days
        time_since_last = (datetime.now() - campaign['last_post_time']).total_seconds()
        minutes_until_next = max(0, 90 - int(time_since_last / 60))
        
        # Progress bar
        total_expected = campaign['days'] * 16
        progress = (campaign['posts_made'] / total_expected) * 100 if total_expected > 0 else 0
        bar_length = 20
        filled = int(bar_length * progress / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        await update.message.reply_text(
            f"📊 *Campaign Status*\n\n"
            f"📢 Channel: {campaign['channel']}\n"
            f"📝 Topic: {campaign['topic']}\n\n"
            f"📨 Posts made: {campaign['posts_made']}\n"
            f"📊 Progress: {bar} {progress:.0f}%\n"
            f"📅 Day {days_passed + 1} of {campaign['days']}\n"
            f"⏰ {days_left} days remaining\n"
            f"⏱️ Next post in: {minutes_until_next} minutes\n\n"
            f"Use /stop to end campaign",
            parse_mode="Markdown"
        )
    
    async def stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id in active_campaigns:
            campaign = active_campaigns[user_id]
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
        else:
            await update.message.reply_text("❌ No active campaign")

# ============ MAIN ============
async def main():
    print("🚀 Starting bot...")
    
    application = Application.builder().token(BOT_TOKEN).build()
    bot = WorkingBot()
    
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("status", bot.status))
    application.add_handler(CommandHandler("stop", bot.stop))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    print("📡 Starting polling...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print("✅ Bot is LIVE!")
    print("💬 Send /start to your bot on Telegram")
    
    # Start the background posting loop
    asyncio.create_task(posting_loop(application))
    print("🔄 Posting loop started (will post every 90 minutes)")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    print("🌟 DEPLOYING...")
    asyncio.run(main())
