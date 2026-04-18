import asyncio
import os
import random
import re
from datetime import datetime, timedelta
from typing import Dict, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

# ============ CONFIGURATION ============
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
PORT = int(os.environ.get("PORT", 8080))

# Validate token
if not BOT_TOKEN:
    print("=" * 50)
    print("❌ ERROR: TELEGRAM_BOT_TOKEN not found!")
    print("=" * 50)
    print("Please add environment variable in Render:")
    print("1. Go to your Render dashboard")
    print("2. Click on your web service")
    print("3. Click 'Environment'")
    print("4. Add: TELEGRAM_BOT_TOKEN = your_bot_token")
    print("=" * 50)
    exit(1)

print(f"✅ Bot token loaded (length: {len(BOT_TOKEN)} characters)")
print(f"✅ Port: {PORT}")

# ============ IN-MEMORY STORAGE (No Database) ============
active_campaigns: Dict[int, Dict] = {}
user_sessions: Dict[int, Dict] = {}
post_history: Dict[int, List[str]] = {}

# ============ CONTENT GENERATOR ============
class ContentGenerator:
    """Generates unique posts without any API"""
    
    POST_TEMPLATES = [
        lambda t, d, p: f"📚 **{t.upper()} INSIGHTS**\n\n"
                        f"Here's what you need to know about {t} today. "
                        f"Stay informed and ahead of the curve!\n\n"
                        f"#{t.replace(' ', '')} #{t.replace(' ', '')}Daily",
        
        lambda t, d, p: f"🤔 **LET'S DISCUSS {t.upper()}**\n\n"
                        f"What's your biggest question about {t}? "
                        f"Drop it in the comments! 👇\n\n"
                        f"#{t.replace(' ', '')}Community",
        
        lambda t, d, p: f"💡 **{t.upper()} TIP OF THE DAY**\n\n"
                        f"Mastering {t} takes time. Here's a key insight: "
                        f"consistency is everything! 🚀\n\n"
                        f"#{t.replace(' ', '')}Tips",
        
        lambda t, d, p: f"📢 **TRENDING: {t.upper()}**\n\n"
                        f"The {t} landscape is evolving rapidly. "
                        f"Stay tuned for daily updates!\n\n"
                        f"#{t.replace(' ', '')}News",
        
        lambda t, d, p: f"🔥 **{t.upper()} MOTIVATION**\n\n"
                        f"Success in {t} doesn't happen overnight. "
                        f"Keep pushing, keep growing! 💪\n\n"
                        f"#{t.replace(' ', '')}Motivation",
        
        lambda t, d, p: f"⚡ **{t.upper()} FACT**\n\n"
                        f"There's always something new to learn about {t}. "
                        f"Follow for daily insights!\n\n"
                        f"#{t.replace(' ', '')}Facts",
        
        lambda t, d, p: f"🎯 **{t.upper()} RESOURCES**\n\n"
                        f"Looking to level up your {t} game? "
                        f"You're in the right place! Daily value guaranteed.\n\n"
                        f"#{t.replace(' ', '')}Resources",
        
        lambda t, d, p: f"💬 **{t.upper()} DISCUSSION**\n\n"
                        f"What's working for you? What challenges are you facing? "
                        f"Let's learn from each other! 👇\n\n"
                        f"#{t.replace(' ', '')}Discussion",
        
        lambda t, d, p: f"✨ **QUICK {t.upper()} TIP**\n\n"
                        f"Small actions, big results. Here's something you can "
                        f"apply today to improve your {t} journey!\n\n"
                        f"#{t.replace(' ', '')}Tips",
        
        lambda t, d, p: f"📊 **{t.upper()} POLL**\n\n"
                        f"What's your biggest challenge with {t}?\n"
                        f"1️⃣ Learning curve\n"
                        f"2️⃣ Finding resources\n"
                        f"3️⃣ Staying consistent\n"
                        f"4️⃣ Other (comment below)\n\n"
                        f"#{t.replace(' ', '')}Community"
    ]
    
    @staticmethod
    def generate_post(topic: str, day: int, post_number: int, total_posts_per_day: int = 16) -> str:
        """Generate a unique post about the topic"""
        
        template_index = (post_number - 1) % len(ContentGenerator.POST_TEMPLATES)
        post = ContentGenerator.POST_TEMPLATES[template_index](topic, day, post_number)
        
        post += f"\n\n📅 Day {day} • Post {post_number}/{total_posts_per_day}"
        
        if post_number % 5 == 0:
            post += f"\n\n🔔 Turn on notifications so you don't miss updates!"
        elif post_number % 7 == 0:
            post += f"\n\n💎 Share this with someone who needs to see it!"
        elif post_number % 3 == 0:
            post += f"\n\n✨ Follow for more {topic} content daily!"
        
        if post_number % 2 == 0:
            emojis = ["🌟", "💎", "🎯", "🚀", "💪", "🔥", "✨", "⭐"]
            post = random.choice(emojis) + " " + post
        
        return post


# ============ MAIN BOT ============
class AutoPostBot:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
        print("✅ Scheduler started (in-memory, no database)")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        await update.message.reply_text(
            "🤖 *Auto Content Bot*\n\n"
            "I automatically create and post content about ANY topic to your channel!\n\n"
            "*Quick Setup (One line):*\n"
            "`@channel | topic | days`\n\n"
            "*Example:*\n"
            "`@my_channel | Crypto Trading | 7 days`\n\n"
            "*Or use:* /setup for step-by-step\n"
            "*Commands:* /help, /status, /stop",
            parse_mode="Markdown"
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command"""
        await update.message.reply_text(
            "📚 *Commands*\n\n"
            "/start - Start the bot\n"
            "/setup - Interactive setup\n"
            "/status - Check campaign status\n"
            "/stop - Stop current campaign\n"
            "/cancel - Cancel setup\n"
            "/help - Show this\n\n"
            "*Quick Format:*\n"
            "`@channel | topic | days`\n\n"
            "*Example:*\n"
            "`@tech_news | AI Technology | 5 days`\n\n"
            "*Requirements:*\n"
            "• Add me as admin to your channel\n"
            "• Channel can be public or private\n"
            "• Posts every 90 minutes (~16/day)",
            parse_mode="Markdown"
        )
    
    async def setup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Interactive setup"""
        user_id = update.effective_user.id
        
        user_sessions[user_id] = {'step': 'channel'}
        
        await update.message.reply_text(
            "📋 *Campaign Setup (Step 1/3)*\n\n"
            "Send your channel username:\n"
            "Example: `@my_cool_channel`\n\n"
            "⚠️ Make sure I'm an admin in your channel first!",
            parse_mode="Markdown"
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all text messages"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        if '|' in text:
            await self.parse_direct_input(update, context, text)
            return
        
        if user_id in user_sessions:
            await self.handle_setup(update, context, text)
            return
        
        await self.help_command(update, context)
    
    async def handle_setup(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle interactive setup steps"""
        user_id = update.effective_user.id
        session = user_sessions.get(user_id, {})
        step = session.get('step')
        
        if step == 'channel':
            if not text.startswith('@') and not text.startswith('-100'):
                await update.message.reply_text(
                    "❌ Please send a valid channel username starting with @\n"
                    "Example: `@my_channel`"
                )
                return
            
            session['channel'] = text
            session['step'] = 'topic'
            user_sessions[user_id] = session
            
            await update.message.reply_text(
                f"✅ Channel: {text}\n\n"
                f"*Step 2/3:* What topic should I post about?\n"
                f"Example: `Artificial Intelligence`, `Fitness Tips`, `Stock Market`",
                parse_mode="Markdown"
            )
        
        elif step == 'topic':
            session['topic'] = text
            session['step'] = 'days'
            user_sessions[user_id] = session
            
            await update.message.reply_text(
                f"✅ Topic: {text}\n\n"
                f"*Step 3/3:* How many days? (1-30)\n"
                f"Example: `7` or `7 days`",
                parse_mode="Markdown"
            )
        
        elif step == 'days':
            try:
                days_match = re.search(r'(\d+)', text)
                if not days_match:
                    raise ValueError
                
                days = int(days_match.group(1))
                if days < 1 or days > 30:
                    raise ValueError
                
                session['days'] = days
                
                total_posts = days * 16
                
                keyboard = [
                    [InlineKeyboardButton("✅ Yes, Start!", callback_data="confirm_start")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
                ]
                
                await update.message.reply_text(
                    f"📋 *Campaign Summary*\n\n"
                    f"📢 Channel: {session['channel']}\n"
                    f"📝 Topic: {session['topic']}\n"
                    f"📅 Duration: {days} days\n"
                    f"📊 Posts per day: ~16\n"
                    f"📈 Total posts: ~{total_posts}\n"
                    f"⏱️ Interval: 90 minutes\n\n"
                    f"Start campaign?",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
                session['step'] = 'confirm'
                user_sessions[user_id] = session
                
            except:
                await update.message.reply_text(
                    "❌ Please send a valid number of days (1-30)\n"
                    "Example: `7` or `10 days`"
                )
    
    async def parse_direct_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Parse direct format: channel | topic | days"""
        parts = [p.strip() for p in text.split('|')]
        
        if len(parts) != 3:
            await update.message.reply_text(
                "❌ Invalid format!\n"
                "Use: `@channel | topic | days`\n"
                "Example: `@my_channel | Crypto News | 7 days`"
            )
            return
        
        channel = parts[0]
        topic = parts[1]
        
        if not channel.startswith('@') and not channel.startswith('-100'):
            await update.message.reply_text(
                "❌ Channel must start with @\n"
                "Example: `@my_channel`"
            )
            return
        
        days_match = re.search(r'(\d+)', parts[2])
        if not days_match:
            await update.message.reply_text("❌ Please specify days (e.g., '7 days')")
            return
        
        days = int(days_match.group(1))
        
        if days < 1 or days > 30:
            await update.message.reply_text("❌ Days must be between 1 and 30")
            return
        
        user_id = update.effective_user.id
        user_sessions[user_id] = {
            'channel': channel,
            'topic': topic,
            'days': days,
            'step': 'confirm'
        }
        
        total_posts = days * 16
        
        keyboard = [
            [InlineKeyboardButton("✅ Start Campaign", callback_data="confirm_start")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ]
        
        await update.message.reply_text(
            f"📋 *Campaign Ready*\n\n"
            f"📢 Channel: {channel}\n"
            f"📝 Topic: {topic}\n"
            f"📅 Duration: {days} days\n"
            f"📊 ~16 posts per day\n"
            f"📈 Total: ~{total_posts} posts\n\n"
            f"Start campaign?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button clicks"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data == "confirm_start":
            session = user_sessions.get(user_id, {})
            channel = session.get('channel')
            topic = session.get('topic')
            days = session.get('days')
            
            if not all([channel, topic, days]):
                await query.edit_message_text("❌ Setup incomplete. Use /setup to start over.")
                return
            
            if user_id in active_campaigns:
                await query.edit_message_text(
                    "❌ You already have an active campaign!\n"
                    "Use /stop to stop it first, then start a new one."
                )
                return
            
            end_date = datetime.now() + timedelta(days=days)
            
            active_campaigns[user_id] = {
                'channel': channel,
                'topic': topic,
                'days': days,
                'start_date': datetime.now(),
                'end_date': end_date,
                'posts_made': 0,
                'current_post_number': 1,
                'current_day': 1,
                'last_post_time': None
            }
            
            post_history[user_id] = []
            
            self.scheduler.add_job(
                self.post_to_channel,
                trigger=IntervalTrigger(minutes=90),
                args=[user_id],
                id=f"campaign_{user_id}",
                replace_existing=True
            )
            
            self.scheduler.add_job(
                self.end_campaign,
                trigger='date',
                run_date=end_date,
                args=[user_id],
                id=f"end_{user_id}"
            )
            
            if user_id in user_sessions:
                del user_sessions[user_id]
            
            await query.edit_message_text(
                f"🚀 *CAMPAIGN STARTED!*\n\n"
                f"📢 Channel: {channel}\n"
                f"📝 Topic: {topic}\n"
                f"📅 Duration: {days} days\n"
                f"⏱️ Posting every 90 minutes\n"
                f"📊 ~16 posts per day\n"
                f"🎯 Ends: {end_date.strftime('%Y-%m-%d %H:%M')}\n\n"
                f"First post coming in a few seconds...\n\n"
                f"📊 Use /status to track progress\n"
                f"🛑 Use /stop to end early",
                parse_mode="Markdown"
            )
            
            await asyncio.sleep(3)
            await self.post_to_channel(user_id)
        
        elif data == "cancel":
            user_id = query.from_user.id
            if user_id in user_sessions:
                del user_sessions[user_id]
            
            await query.edit_message_text("❌ Campaign cancelled. Use /setup to start over.")
    
    async def post_to_channel(self, user_id: int):
        """Generate and post content to channel"""
        campaign = active_campaigns.get(user_id)
        if not campaign:
            return
        
        if datetime.now() > campaign['end_date']:
            await self.end_campaign(user_id)
            return
        
        days_running = (datetime.now() - campaign['start_date']).days + 1
        posts_per_day = 16
        current_post = campaign['current_post_number']
        
        post_content = ContentGenerator.generate_post(
            campaign['topic'],
            days_running,
            current_post,
            posts_per_day
        )
        
        try:
            await context.bot.send_message(
                chat_id=campaign['channel'],
                text=post_content,
                parse_mode="Markdown"
            )
            
            campaign['posts_made'] += 1
            campaign['current_post_number'] += 1
            campaign['last_post_time'] = datetime.now()
            
            if campaign['current_post_number'] > posts_per_day:
                campaign['current_post_number'] = 1
                campaign['current_day'] = days_running + 1
            
            post_history.setdefault(user_id, []).append(post_content[:100])
            if len(post_history[user_id]) > 100:
                post_history[user_id] = post_history[user_id][-100:]
            
            print(f"✅ [User {user_id}] Posted to {campaign['channel']} - Post #{campaign['posts_made']}")
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ [User {user_id}] Error: {error_msg}")
            
            if "chat not found" in error_msg.lower() or "chat_id is empty" in error_msg.lower():
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ *Error: Cannot post to {campaign['channel']}*\n\n"
                         f"Please make sure:\n"
                         f"1️⃣ I'm an admin in that channel\n"
                         f"2️⃣ The channel username is correct\n"
                         f"3️⃣ The channel exists\n\n"
                         f"Campaign has been stopped.",
                    parse_mode="Markdown"
                )
                await self.end_campaign(user_id)
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show campaign status"""
        user_id = update.effective_user.id
        campaign = active_campaigns.get(user_id)
        
        if not campaign:
            await update.message.reply_text(
                "❌ *No active campaign*\n\n"
                "Start one with:\n"
                "• `/setup` for interactive setup\n"
                "• Or send: `@channel | topic | days`\n\n"
                "Example: `@my_channel | Crypto | 7 days`",
                parse_mode="Markdown"
            )
            return
        
        days_passed = (datetime.now() - campaign['start_date']).days
        days_remaining = (campaign['end_date'] - datetime.now()).days
        posts_per_day = 16
        
        total_expected = campaign['days'] * posts_per_day
        progress_percent = (campaign['posts_made'] / total_expected) * 100 if total_expected > 0 else 0
        
        bar_length = 20
        filled = int(bar_length * progress_percent / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        await update.message.reply_text(
            f"📊 *Campaign Status*\n\n"
            f"📝 Topic: `{campaign['topic']}`\n"
            f"📢 Channel: {campaign['channel']}\n\n"
            f"📅 Day {days_passed + 1} of {campaign['days']}\n"
            f"⏰ {days_remaining} days remaining\n\n"
            f"📨 Posts made: {campaign['posts_made']}\n"
            f"📊 Progress: {bar} {progress_percent:.1f}%\n\n"
            f"⏱️ Last post: {campaign['last_post_time'].strftime('%H:%M') if campaign['last_post_time'] else 'Not yet'}\n"
            f"🔄 Next post: ~90 minutes\n\n"
            f"🛑 Use /stop to end campaign",
            parse_mode="Markdown"
        )
    
    async def stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop campaign and clear memory"""
        user_id = update.effective_user.id
        
        if user_id not in active_campaigns:
            await update.message.reply_text("❌ No active campaign to stop.")
            return
        
        campaign = active_campaigns[user_id]
        
        try:
            self.scheduler.remove_job(f"campaign_{user_id}")
            self.scheduler.remove_job(f"end_{user_id}")
        except Exception as e:
            print(f"Job removal error: {e}")
        
        posts_made = campaign['posts_made']
        topic = campaign['topic']
        days_run = (datetime.now() - campaign['start_date']).days + 1
        
        del active_campaigns[user_id]
        if user_id in post_history:
            del post_history[user_id]
        if user_id in user_sessions:
            del user_sessions[user_id]
        
        await update.message.reply_text(
            f"🛑 *Campaign Stopped*\n\n"
            f"📝 Topic: {topic}\n"
            f"📨 Total posts made: {posts_made}\n"
            f"📅 Days run: {days_run}\n\n"
            f"✅ Memory cleared for this campaign.\n\n"
            f"Start a new campaign with /setup",
            parse_mode="Markdown"
        )
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current setup"""
        user_id = update.effective_user.id
        
        if user_id in user_sessions:
            del user_sessions[user_id]
            await update.message.reply_text("✅ Setup cancelled. Use /setup to start over.")
        else:
            await update.message.reply_text("❌ No active setup to cancel.")
    
    async def end_campaign(self, user_id: int):
        """End campaign and cleanup memory"""
        campaign = active_campaigns.get(user_id)
        if not campaign:
            return
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ *Campaign Completed!*\n\n"
                     f"📝 Topic: {campaign['topic']}\n"
                     f"📨 Total posts: {campaign['posts_made']}\n"
                     f"📅 Duration: {campaign['days']} days\n\n"
                     f"🎯 Campaign goal achieved!\n\n"
                     f"Start a new campaign with /setup",
                parse_mode="Markdown"
            )
        except:
            pass
        
        if user_id in active_campaigns:
            del active_campaigns[user_id]
        if user_id in post_history:
            del post_history[user_id]
        if user_id in user_sessions:
            del user_sessions[user_id]
        
        try:
            self.scheduler.remove_job(f"campaign_{user_id}")
            self.scheduler.remove_job(f"end_{user_id}")
        except:
            pass
        
        print(f"✅ Campaign ended for user {user_id}, memory cleared")


# ============ RUN BOT ============
import logging
logging.basicConfig(level=logging.INFO)

async def main():
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Store bot instance in application for access in methods
    global context
    context = application
    
    # Create bot instance
    bot = AutoPostBot()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("setup", bot.setup))
    application.add_handler(CommandHandler("status", bot.status))
    application.add_handler(CommandHandler("stop", bot.stop))
    application.add_handler(CommandHandler("cancel", bot.cancel))
    application.add_handler(CallbackQueryHandler(bot.handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    print("🤖 Bot is running with in-memory storage (no database)!")
    print(f"Active campaigns: {len(active_campaigns)}")
    
    # Start bot with polling (simpler and more compatible)
    print("🔄 Starting bot with long polling...")
    
    # Initialize and start polling
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print(f"✅ Bot is running and listening for messages!")
    print(f"💡 Send /start to your bot on Telegram to begin")
    
    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
