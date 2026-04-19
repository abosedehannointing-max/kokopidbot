import asyncio
import os
import re
from datetime import datetime, timedelta
from typing import Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# ============ CONFIGURATION ============
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

if not BOT_TOKEN:
    print("❌ ERROR: TELEGRAM_BOT_TOKEN not found!")
    exit(1)

print("✅ Premium Bot Started")

# ============ STORAGE ============
active_campaigns: Dict[int, Dict] = {}

# ============ PREMIUM CONTENT TEMPLATES ============
class PremiumTemplates:
    @staticmethod
    def get_post(topic: str, day: int, post_num: int, total_posts: int) -> str:
        templates = [
            f"✨ *✨ {topic.upper()} PREMIUM ✨*\n\n"
            f"🌟 *Insight #{post_num}*\n"
            f"Here's your daily dose of {topic} wisdom. Keep growing and glowing!\n\n"
            f"📅 Day {day} • Post {post_num}/{total_posts}\n\n"
            f"#Premium{topic.replace(' ', '')} #{topic.replace(' ', '')}Daily",
            
            f"💎 *💎 {topic.upper()} MASTERCLASS 💎*\n\n"
            f"🎯 *Key Learning #{post_num}*\n"
            f"Success in {topic} comes to those who stay consistent. You got this!\n\n"
            f"📅 Day {day} • Post {post_num}/{total_posts}\n\n"
            f"#{topic.replace(' ', '')}Mastery",
            
            f"🔥 *🔥 {topic.upper()} INSIGHTS 🔥*\n\n"
            f"⚡ *Power Tip #{post_num}*\n"
            f"Transform your {topic} journey with this powerful insight!\n\n"
            f"📅 Day {day} • Post {post_num}/{total_posts}\n\n"
            f"#{topic.replace(' ', '')}Success",
            
            f"🎯 *🎯 {topic.upper()} STRATEGY 🎯*\n\n"
            f"📌 *Strategy #{post_num}*\n"
            f"Implement this today and see the difference in your {topic} results!\n\n"
            f"📅 Day {day} • Post {post_num}/{total_posts}\n\n"
            f"#{topic.replace(' ', '')}Strategy",
            
            f"💫 *💫 {topic.upper()} MOTIVATION 💫*\n\n"
            f"💪 *Daily Boost #{post_num}*\n"
            f"Remember why you started your {topic} journey. Keep pushing forward!\n\n"
            f"📅 Day {day} • Post {post_num}/{total_posts}\n\n"
            f"#{topic.replace(' ', '')}Motivation",
            
            f"⚡ *⚡ {topic.upper()} ACCELERATOR ⚡*\n\n"
            f"🚀 *Quick Win #{post_num}*\n"
            f"One small step in {topic} today leads to big results tomorrow!\n\n"
            f"📅 Day {day} • Post {post_num}/{total_posts}\n\n"
            f"#{topic.replace(' ', '')}Growth",
        ]
        return templates[post_num % len(templates)]

# ============ PREMIUM BOT ============
class PremiumBot:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
        print("✅ Premium Scheduler Active")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("📝 Quick Setup", callback_data="quick_setup")],
            [InlineKeyboardButton("📊 My Status", callback_data="check_status")],
            [InlineKeyboardButton("🛑 Stop Campaign", callback_data="stop_campaign")],
            [InlineKeyboardButton("❓ Help", callback_data="help_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🌟 *✨ PREMIUM AUTO CONTENT BOT ✨* 🌟\n\n"
            "Welcome to the ultimate auto-posting solution!\n\n"
            "🚀 *Features:*\n"
            "• ✅ Premium content templates\n"
            "• ✅ Smart scheduling (90 min intervals)\n"
            "• ✅ Real-time tracking\n"
            "• ✅ One-click management\n\n"
            "📝 *Quick Setup:*\n"
            "`@channel | topic | days`\n\n"
            "💡 *Example:*\n"
            "`@modernlovetips | Love Tips | 7 days`\n\n"
            "👇 *Or use the buttons below* 👇",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if query.data == "quick_setup":
            await query.edit_message_text(
                "📝 *Quick Setup Mode*\n\n"
                "Send your campaign in this format:\n\n"
                "`@channel | topic | days`\n\n"
                "Example:\n"
                "`@modernlovetips | Love Tips | 7 days`\n\n"
                "Make sure I'm an admin in your channel!",
                parse_mode="Markdown"
            )
        
        elif query.data == "check_status":
            await self.status_command(update, context)
        
        elif query.data == "stop_campaign":
            await self.stop_command(update, context)
        
        elif query.data == "help_menu":
            await self.help_command(update, context)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("📝 Start Setup", callback_data="quick_setup")],
            [InlineKeyboardButton("📊 Check Status", callback_data="check_status")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = "❓ *Help Center*\n\n"
        message += "*Commands:*\n"
        message += "• `/start` - Open main menu\n"
        message += "• `/setup @channel | topic | days` - Start campaign\n"
        message += "• `/status` - Check active campaign\n"
        message += "• `/stop` - Stop current campaign\n\n"
        message += "*Setup Format:*\n"
        message += "`@channel | topic | days`\n\n"
        message += "*Example:*\n"
        message += "`@modernlovetips | Love Tips | 7 days`\n\n"
        message += "*Requirements:*\n"
        message += "• Bot must be admin in your channel\n"
        message += "• Channel username must start with @\n"
        message += "• Duration: 1-30 days"
        
        if isinstance(update, Update) and update.callback_query:
            await update.callback_query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        if '|' in text:
            await self.setup_campaign(update, context, text)
        else:
            await self.start(update, context)
    
    async def setup_campaign(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        user_id = update.effective_user.id
        parts = [p.strip() for p in text.split('|')]
        
        if len(parts) != 3:
            await update.message.reply_text(
                "❌ *Invalid Format*\n\n"
                "Use: `@channel | topic | days`\n\n"
                "Example: `@modernlovetips | Love Tips | 7 days`",
                parse_mode="Markdown"
            )
            return
        
        channel = parts[0]
        topic = parts[1]
        
        days_match = re.search(r'(\d+)', parts[2])
        if not days_match:
            await update.message.reply_text("❌ Please specify days (e.g., '7 days')")
            return
        
        days = int(days_match.group(1))
        
        if days < 1 or days > 30:
            await update.message.reply_text("❌ Days must be between 1 and 30")
            return
        
        if not channel.startswith('@'):
            await update.message.reply_text("❌ Channel must start with @\nExample: `@modernlovetips`")
            return
        
        # Test post permission
        try:
            test_msg = await context.bot.send_message(
                chat_id=channel,
                text=f"🌟 *Premium Bot Active* 🌟\n\nSetting up campaign for: *{topic}*\nDuration: *{days} days*\n\n_Starting in a few seconds..._",
                parse_mode="Markdown"
            )
            await test_msg.delete()
            await update.message.reply_text(f"✅ *Access Verified!* Bot can post to {channel}")
        except Exception as e:
            await update.message.reply_text(
                f"❌ *Cannot access channel*\n\n"
                f"Error: `{str(e)[:100]}`\n\n"
                f"*Solutions:*\n"
                f"1️⃣ Make @{context.bot.username} admin in {channel}\n"
                f"2️⃣ Check channel name is correct\n"
                f"3️⃣ Channel must exist",
                parse_mode="Markdown"
            )
            return
        
        # Stop existing campaign
        if user_id in active_campaigns:
            try:
                self.scheduler.remove_job(f"premium_campaign_{user_id}")
            except:
                pass
        
        # Start new campaign
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
            id=f"premium_campaign_{user_id}",
            replace_existing=True
        )
        
        # Premium success message
        keyboard = [
            [InlineKeyboardButton("📊 Track Status", callback_data="check_status")],
            [InlineKeyboardButton("🛑 Stop Campaign", callback_data="stop_campaign")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🌟 *✨ CAMPAIGN ACTIVATED ✨* 🌟\n\n"
            f"📢 *Channel:* {channel}\n"
            f"📝 *Topic:* {topic}\n"
            f"📅 *Duration:* {days} days\n"
            f"📊 *Total Posts:* ~{total_posts}\n"
            f"⏱️ *Frequency:* Every 90 minutes\n"
            f"🎯 *Status:* 🟢 ACTIVE\n\n"
            f"✨ *First post arriving in a few seconds...*\n\n"
            f"👇 *Manage your campaign* 👇",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
        # Send first post
        await asyncio.sleep(3)
        await self.post_to_channel(user_id)
    
    async def post_to_channel(self, user_id: int):
        campaign = active_campaigns.get(user_id)
        if not campaign:
            return
        
        if datetime.now() > campaign['end_date']:
            await self.end_campaign(user_id)
            return
        
        day = (datetime.now() - campaign['start_date']).days + 1
        post_num = campaign['post_num']
        total_posts = 16
        
        post_content = PremiumTemplates.get_post(campaign['topic'], day, post_num, total_posts)
        
        try:
            await context.bot.send_message(
                chat_id=campaign['channel'],
                text=post_content,
                parse_mode="Markdown"
            )
            
            campaign['posts_made'] += 1
            campaign['post_num'] += 1
            if campaign['post_num'] > total_posts:
                campaign['post_num'] = 1
            
            print(f"✅ Premium Post #{campaign['posts_made']} → {campaign['channel']}")
            
        except Exception as e:
            print(f"❌ Post error: {e}")
            await context.bot.send_message(
                chat_id=user_id,
                text=f"⚠️ *Warning:* Could not post to {campaign['channel']}\nError: {str(e)[:100]}",
                parse_mode="Markdown"
            )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        campaign = active_campaigns.get(user_id)
        
        if not campaign:
            keyboard = [[InlineKeyboardButton("📝 Start Campaign", callback_data="quick_setup")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = "❌ *No Active Campaign*\n\n"
            message += "Start a new campaign with:\n"
            message += "`@channel | topic | days`\n\n"
            message += "Example:\n"
            message += "`@modernlovetips | Love Tips | 7 days`"
            
            if update.callback_query:
                await update.callback_query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)
            else:
                await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)
            return
        
        days_passed = (datetime.now() - campaign['start_date']).days
        days_left = (campaign['end_date'] - datetime.now()).days
        progress = (campaign['posts_made'] / campaign['total_posts']) * 100 if campaign['total_posts'] > 0 else 0
        
        # Progress bar
        bar_length = 20
        filled = int(bar_length * progress / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        keyboard = [
            [InlineKeyboardButton("🛑 Stop Campaign", callback_data="stop_campaign")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="check_status")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = f"🌟 *✨ CAMPAIGN STATUS ✨* 🌟\n\n"
        message += f"📢 *Channel:* {campaign['channel']}\n"
        message += f"📝 *Topic:* {campaign['topic']}\n\n"
        message += f"📊 *Progress:*\n"
        message += f"`{bar}` {progress:.1f}%\n\n"
        message += f"📨 *Posts Made:* {campaign['posts_made']} / {campaign['total_posts']}\n"
        message += f"📅 *Day:* {days_passed + 1} of {campaign['days']}\n"
        message += f"⏰ *Remaining:* {days_left} days\n"
        message += f"🎯 *Status:* 🟢 ACTIVE\n\n"
        message += f"⏱️ *Next Post:* ~90 minutes\n\n"
        message += f"✨ *Keep growing your channel!* ✨"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)
    
    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in active_campaigns:
            keyboard = [[InlineKeyboardButton("📝 Start Campaign", callback_data="quick_setup")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = "❌ *No Active Campaign to Stop*\n\nStart a new campaign with `/setup`"
            
            if update.callback_query:
                await update.callback_query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)
            else:
                await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)
            return
        
        campaign = active_campaigns[user_id]
        
        # Remove scheduler
        try:
            self.scheduler.remove_job(f"premium_campaign_{user_id}")
        except:
            pass
        
        # Get stats
        posts_made = campaign['posts_made']
        days_run = (datetime.now() - campaign['start_date']).days + 1
        
        # Clear from memory
        del active_campaigns[user_id]
        
        keyboard = [[InlineKeyboardButton("📝 Start New Campaign", callback_data="quick_setup")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = f"🛑 *✨ CAMPAIGN STOPPED ✨* 🛑\n\n"
        message += f"📢 *Channel:* {campaign['channel']}\n"
        message += f"📝 *Topic:* {campaign['topic']}\n"
        message += f"📨 *Total Posts:* {posts_made}\n"
        message += f"📅 *Days Run:* {days_run}\n\n"
        message += f"✅ *Campaign data cleared*\n\n"
        message += f"🌟 *Start a new campaign anytime!* 🌟"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)
    
    async def end_campaign(self, user_id: int):
        campaign = active_campaigns.get(user_id)
        if not campaign:
            return
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 *✨ CAMPAIGN COMPLETED! ✨* 🎉\n\n"
                     f"📝 *Topic:* {campaign['topic']}\n"
                     f"📨 *Total Posts:* {campaign['posts_made']}\n"
                     f"📅 *Duration:* {campaign['days']} days\n\n"
                     f"🌟 *Amazing work! Start a new campaign with /start* 🌟",
                parse_mode="Markdown"
            )
        except:
            pass
        
        if user_id in active_campaigns:
            del active_campaigns[user_id]
        try:
            self.scheduler.remove_job(f"premium_campaign_{user_id}")
        except:
            pass

# ============ MAIN ============
async def main():
    application = Application.builder().token(BOT_TOKEN).build()
    bot = PremiumBot()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("status", bot.status_command))
    application.add_handler(CommandHandler("stop", bot.stop_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CallbackQueryHandler(bot.button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Start bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print("🌟 PREMIUM BOT IS RUNNING! 🌟")
    print("✅ Status tracking active")
    print("✅ Stop command ready")
    print("✅ Premium templates loaded")
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
