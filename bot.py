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

# Store campaigns - Supports multiple channels per user!
# Structure: {user_id: [campaign1, campaign2, campaign3]}
user_campaigns: Dict[int, list] = {}
campaign_counter = 0

# ============ POSTING FUNCTION ============
async def send_post(application, user_id, campaign_id, campaign):
    """Send a single post to the channel"""
    
    # Check if campaign expired
    if datetime.now() > campaign['end_date']:
        return False
    
    # Generate post content
    campaign['posts_made'] += 1
    campaign['post_number'] += 1
    day = (datetime.now() - campaign['start_date']).days + 1
    
    # Beautiful post templates based on topic
    templates = [
        f"💖 *{campaign['topic'].upper()} - Post #{campaign['post_number']}* 💖\n\n"
        f"Day {day}: Here's your daily dose of {campaign['topic']}! Stay consistent and keep growing.\n\n"
        f"#{campaign['topic'].replace(' ', '')} #DailyTips",
        
        f"💕 *{campaign['topic'].upper()} INSIGHT* 💕\n\n"
        f"Day {day}: Small daily actions lead to big results in {campaign['topic']}.\n\n"
        f"#{campaign['topic'].replace(' ', '')} #Wisdom",
        
        f"✨ *{campaign['topic'].upper()} TIP #{campaign['post_number']}* ✨\n\n"
        f"Day {day}: The key to success in {campaign['topic']} is consistency and patience.\n\n"
        f"#{campaign['topic'].replace(' ', '')} #Success",
        
        f"🌟 *MODERN {campaign['topic'].upper()}* 🌟\n\n"
        f"Day {day}: Keep pushing forward with {campaign['topic']}. Every day brings new opportunities!\n\n"
        f"#{campaign['topic'].replace(' ', '')} #Motivation"
    ]
    
    post_text = templates[campaign['post_number'] % len(templates)]
    
    try:
        await application.bot.send_message(
            chat_id=campaign['channel'],
            text=post_text,
            parse_mode="Markdown"
        )
        print(f"✅ Posted to {campaign['channel']} - {campaign['topic']} - Post #{campaign['posts_made']}")
        return True
    except Exception as e:
        print(f"❌ Error posting to {campaign['channel']}: {e}")
        return False

# ============ SCHEDULER FUNCTION ============
async def schedule_posts(application, user_id, campaign_id, interval_minutes):
    """Schedule posts at regular intervals for a specific campaign"""
    while True:
        # Check if user exists
        if user_id not in user_campaigns:
            break
        
        # Find the specific campaign
        campaign = None
        for camp in user_campaigns[user_id]:
            if camp['id'] == campaign_id:
                campaign = camp
                break
        
        # If campaign not found or expired, stop
        if not campaign or datetime.now() > campaign['end_date']:
            break
        
        # Wait for the interval
        await asyncio.sleep(interval_minutes * 60)
        
        # Double check campaign still exists
        if user_id not in user_campaigns:
            break
        
        # Send the post
        await send_post(application, user_id, campaign_id, campaign)

# ============ BOT CLASS ============
class MultiChannelBot:
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 *Multi-Channel Auto Post Bot* 🤖\n\n"
            "I can handle MULTIPLE channels at once!\n\n"
            "*To start a campaign:*\n"
            "`@channel | topic | days`\n\n"
            "*Example:*\n"
            "`@modernlovetips | Love Tips | 7 days`\n\n"
            "*Commands:*\n"
            "/campaigns - List all your campaigns\n"
            "/status [number] - Check specific campaign\n"
            "/stop [number] - Stop specific campaign\n"
            "/stopall - Stop ALL campaigns\n\n"
            "*You can run multiple campaigns simultaneously!*",
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
            
            # Create campaign
            global campaign_counter
            campaign_counter += 1
            
            campaign = {
                'id': campaign_counter,
                'channel': channel,
                'topic': topic,
                'days': days,
                'start_date': datetime.now(),
                'end_date': datetime.now() + timedelta(days=days),
                'posts_made': 0,
                'post_number': 0
            }
            
            # Add to user's campaigns
            if user_id not in user_campaigns:
                user_campaigns[user_id] = []
            user_campaigns[user_id].append(campaign)
            
            await update.message.reply_text(
                f"✅ *CAMPAIGN #{campaign['id']} STARTED!*\n\n"
                f"📢 Channel: {channel}\n"
                f"📝 Topic: {topic}\n"
                f"📅 Duration: {days} days\n"
                f"⏱️ Posts every: 90 minutes\n\n"
                f"📨 First post arriving in 5 seconds...\n"
                f"Use /campaigns to see all your campaigns",
                parse_mode="Markdown"
            )
            
            # Test if bot can post
            try:
                await context.bot.send_message(
                    chat_id=channel,
                    text=f"✅ Campaign #{campaign['id']} activated! I'll post about {topic} every 90 minutes for {days} days."
                )
            except Exception as e:
                await update.message.reply_text(f"⚠️ Warning: Could not send test message. Make sure I'm admin in {channel}")
            
            # Wait 5 seconds then send first post
            await asyncio.sleep(5)
            
            # Send first post
            success = await send_post(context.application, user_id, campaign['id'], campaign)
            
            if success:
                await update.message.reply_text(f"✅ First post sent to {channel}!")
                
                # Start the scheduled posts in background
                asyncio.create_task(schedule_posts(context.application, user_id, campaign['id'], 90))
            else:
                await update.message.reply_text(f"❌ Failed to post to {channel}. Make sure I'm admin")
        
        else:
            await self.start(update, context)
    
    async def list_campaigns(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in user_campaigns or not user_campaigns[user_id]:
            await update.message.reply_text("❌ No active campaigns. Start one with `@channel | topic | days`")
            return
        
        message = "📋 *YOUR ACTIVE CAMPAIGNS*\n\n"
        for i, campaign in enumerate(user_campaigns[user_id], 1):
            days_left = (campaign['end_date'] - datetime.now()).days
            message += f"*{i}.* Campaign #{campaign['id']}\n"
            message += f"   📢 {campaign['channel']}\n"
            message += f"   📝 {campaign['topic']}\n"
            message += f"   📨 {campaign['posts_made']} posts\n"
            message += f"   ⏰ {days_left} days left\n\n"
        
        message += f"Use `/status 1` to see details about campaign 1\n"
        message += f"Use `/stop 1` to stop campaign 1\n"
        message += f"Use `/stopall` to stop all campaigns"
        
        await update.message.reply_text(message, parse_mode="Markdown")
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # Get campaign number from command
        args = context.args
        campaign_num = 1
        if args and args[0].isdigit():
            campaign_num = int(args[0]) - 1
        
        if user_id not in user_campaigns or not user_campaigns[user_id]:
            await update.message.reply_text("❌ No active campaigns.")
            return
        
        if campaign_num >= len(user_campaigns[user_id]):
            await update.message.reply_text(f"❌ Campaign #{campaign_num + 1} not found. Use /campaigns to see your campaigns.")
            return
        
        campaign = user_campaigns[user_id][campaign_num]
        days_passed = (datetime.now() - campaign['start_date']).days
        days_left = (campaign['end_date'] - datetime.now()).days
        
        total_expected = campaign['days'] * 16
        progress = (campaign['posts_made'] / total_expected) * 100 if total_expected > 0 else 0
        
        # Progress bar
        bar_length = 20
        filled = int(bar_length * progress / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        await update.message.reply_text(
            f"📊 *Campaign #{campaign['id']} Status*\n\n"
            f"📢 Channel: {campaign['channel']}\n"
            f"📝 Topic: {campaign['topic']}\n\n"
            f"📨 Posts made: {campaign['posts_made']}\n"
            f"📊 Progress: {bar} {progress:.0f}%\n"
            f"📅 Day {days_passed + 1} of {campaign['days']}\n"
            f"⏰ {days_left} days remaining\n\n"
            f"Use `/stop {campaign_num + 1}` to stop this campaign",
            parse_mode="Markdown"
        )
    
    async def stop_campaign(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # Get campaign number from command
        args = context.args
        if not args or not args[0].isdigit():
            await update.message.reply_text("❌ Use: `/stop 1` to stop campaign 1\nUse /campaigns to see your campaigns")
            return
        
        campaign_num = int(args[0]) - 1
        
        if user_id not in user_campaigns or not user_campaigns[user_id]:
            await update.message.reply_text("❌ No active campaigns.")
            return
        
        if campaign_num >= len(user_campaigns[user_id]):
            await update.message.reply_text(f"❌ Campaign #{campaign_num + 1} not found.")
            return
        
        campaign = user_campaigns[user_id][campaign_num]
        posts_made = campaign['posts_made']
        topic = campaign['topic']
        channel = campaign['channel']
        
        # Remove campaign
        user_campaigns[user_id].pop(campaign_num)
        
        await update.message.reply_text(
            f"🛑 *Campaign #{campaign['id']} Stopped*\n\n"
            f"📢 Channel: {channel}\n"
            f"📝 Topic: {topic}\n"
            f"📨 Total posts: {posts_made}\n\n"
            f"Use /campaigns to see remaining campaigns",
            parse_mode="Markdown"
        )
    
    async def stop_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in user_campaigns or not user_campaigns[user_id]:
            await update.message.reply_text("❌ No active campaigns.")
            return
        
        count = len(user_campaigns[user_id])
        del user_campaigns[user_id]
        
        await update.message.reply_text(
            f"🛑 *ALL CAMPAIGNS STOPPED*\n\n"
            f"Stopped {count} campaign(s).\n\n"
            f"Start new campaigns with `@channel | topic | days`",
            parse_mode="Markdown"
        )

# ============ MAIN ============
async def main():
    print("🚀 Starting Multi-Channel Bot...")
    
    application = Application.builder().token(BOT_TOKEN).build()
    bot = MultiChannelBot()
    
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("campaigns", bot.list_campaigns))
    application.add_handler(CommandHandler("status", bot.status))
    application.add_handler(CommandHandler("stop", bot.stop_campaign))
    application.add_handler(CommandHandler("stopall", bot.stop_all))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    print("📡 Starting polling...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print("✅ Multi-Channel Bot is LIVE!")
    print("💬 Can handle MULTIPLE channels per user!")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    print("🌟 DEPLOYING MULTI-CHANNEL BOT...")
    asyncio.run(main())
