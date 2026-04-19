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

# ============ POSTING FUNCTION ============
async def send_post(application, user_id):
    """Send a single post to the channel"""
    campaign = active_campaigns.get(user_id)
    if not campaign:
        return False
    
    # Check if campaign expired
    if datetime.now() > campaign['end_date']:
        del active_campaigns[user_id]
        return False
    
    # Generate post content
    campaign['posts_made'] += 1
    campaign['post_number'] += 1
    day = (datetime.now() - campaign['start_date']).days + 1
    
    # Beautiful post templates
    templates = [
        f"💖 *LOVE TIPS - Post #{campaign['post_number']}* 💖\n\n"
        f"Day {day}: True love isn't about perfection. It's about accepting each other's flaws and growing together.\n\n"
        f"#{campaign['topic'].replace(' ', '')} #LoveTips",
        
        f"💕 *RELATIONSHIP ADVICE* 💕\n\n"
        f"Day {day}: The best relationships have partners who communicate openly and listen without judgment.\n\n"
        f"#{campaign['topic'].replace(' ', '')} #RelationshipGoals",
        
        f"✨ *LOVE INSIGHT #{campaign['post_number']}* ✨\n\n"
        f"Day {day}: Love grows when you appreciate the small things - a kind word, a warm hug, a listening ear.\n\n"
        f"#{campaign['topic'].replace(' ', '')} #DailyLove",
        
        f"🌹 *MODERN LOVE TIP* 🌹\n\n"
        f"Day {day}: Don't chase love. Attract it by being the best version of yourself.\n\n"
        f"#{campaign['topic'].replace(' ', '')} #ModernLove"
    ]
    
    post_text = templates[campaign['post_number'] % len(templates)]
    
    try:
        await application.bot.send_message(
            chat_id=campaign['channel'],
            text=post_text,
            parse_mode="Markdown"
        )
        print(f"✅ Posted to {campaign['channel']} - Post #{campaign['posts_made']}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# ============ SCHEDULER FUNCTION ============
async def schedule_posts(application, user_id, interval_minutes):
    """Schedule posts at regular intervals"""
    while user_id in active_campaigns:
        # Wait for the interval
        await asyncio.sleep(interval_minutes * 60)
        
        # Check if campaign still exists
        if user_id not in active_campaigns:
            break
        
        # Send the post
        await send_post(application, user_id)

# ============ BOT CLASS ============
class WorkingBot:
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 *Auto Post Bot* 🤖\n\n"
            "To start, send:\n"
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
            
            # Check if already has campaign
            if user_id in active_campaigns:
                await update.message.reply_text("❌ You already have an active campaign. Use /stop first.")
                return
            
            # Store campaign
            active_campaigns[user_id] = {
                'channel': channel,
                'topic': topic,
                'days': days,
                'start_date': datetime.now(),
                'end_date': datetime.now() + timedelta(days=days),
                'posts_made': 0,
                'post_number': 0
            }
            
            await update.message.reply_text(
                f"✅ *CAMPAIGN STARTED!*\n\n"
                f"📢 Channel: {channel}\n"
                f"📝 Topic: {topic}\n"
                f"📅 Duration: {days} days\n"
                f"⏱️ Posts every: 90 minutes\n\n"
                f"📨 First post arriving in 5 seconds...\n"
                f"Use /status to track progress",
                parse_mode="Markdown"
            )
            
            # Wait 5 seconds then send first post
            await asyncio.sleep(5)
            
            # Send first post
            success = await send_post(context.application, user_id)
            
            if success:
                await update.message.reply_text(f"✅ First post sent to {channel}!")
                
                # Start the scheduled posts in background
                asyncio.create_task(schedule_posts(context.application, user_id, 90))
            else:
                await update.message.reply_text(f"❌ Failed to post. Make sure I'm admin in {channel}")
                del active_campaigns[user_id]
        
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
        
        total_expected = campaign['days'] * 16
        progress = (campaign['posts_made'] / total_expected) * 100 if total_expected > 0 else 0
        
        # Progress bar
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
            f"⏰ {days_left} days remaining\n\n"
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
                f"📨 Total posts: {posts_made}\n\n"
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
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    print("🌟 DEPLOYING...")
    asyncio.run(main())
