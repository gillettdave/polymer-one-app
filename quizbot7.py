import discord
from discord.ext import commands, tasks
from discord import app_commands
import csv
import random
import asyncio
from permissions import admin_or_role_only
import os
import time
from typing import List
from collections import defaultdict, deque
from typing import Optional
import datetime

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
active_threads = set()

GUILD_ID = 839903468750635039
guild_obj = discord.Object(id=GUILD_ID)
active_threads = {}

# ===============================
# DM Rate Limit Setup
# ===============================
dm_timestamps = deque()
DM_RATE_LIMIT = 250 / 60  # ~4.16 DMs/sec
DM_WINDOW = 1  # 1 second window

async def safe_delete_message(message):
    try:
        await message.delete()
    except discord.NotFound:
        pass
    except Exception as e:
        print(f"Failed to delete message: {e}")
        
def can_send_dm():
    now = datetime.datetime.utcnow()
    while dm_timestamps and (now - dm_timestamps[0]).total_seconds() > DM_WINDOW:
        dm_timestamps.popleft()
    return len(dm_timestamps) < DM_RATE_LIMIT

def register_dm_send():
    dm_timestamps.append(datetime.datetime.utcnow())

thread_semaphore = asyncio.Semaphore(1)  # only 1 thread-create call at a time

async def force_stop_quiz(user_id):
    """Force-stop a quiz for a user and clean up their messages."""
    session = bot.quiz_sessions.get(user_id)
    if session:
        # Cancel pending wait tasks if you store them
        if 'wait_task' in session and not session['wait_task'].done():
            session['wait_task'].cancel()
            try:
                await session['wait_task']
            except asyncio.CancelledError:
                pass

        # Delete tracked quiz messages
        for msg in session.get('messages', []):
            try:
                await msg.delete()
            except Exception:
                pass

        # Clean up session
        bot.quiz_sessions.pop(user_id, None)
        
async def force_stop_quiz(user_id):
    """Signal quiz stop without immediate session deletion."""
    session = bot.quiz_sessions.get(user_id)
    if session:
        session['stopped'] = True  # signal for quiz and buttons to stop
        
async def safe_ephemeral(inter: discord.Interaction, msg: str):
    """Send an ephemeral follow-up if token is still valid; otherwise send in the channel."""
    try:
        if inter.response.is_done():
            await inter.followup.send(msg, ephemeral=True)
        else:
            await inter.response.send_message(msg, ephemeral=True)
    except discord.HTTPException:
        # Token likely expired
        await inter.channel.send(f"{inter.user.mention} {msg}")

bot = commands.Bot(command_prefix="!", intents=intents)
bot.quiz_sessions = {}


# Define Cooldown for users
user_quiz_attempts = {}  # user_id -> timestamp
QUIZ_COOLDOWN_SECONDS = 600

# ✅ Fixes the AttributeError
bot.quiz_sessions = {}
active_threads = {}  # user.id -> thread.id

QUIZ_DATA_FILE = "questions.csv"
RESULTS_FILE = "results.csv"
MAX_PARTICIPANTS = 50

@bot.event
async def on_ready():
    print(f"✅ Bot is ready as {bot.user}")
    await bot.tree.sync(guild=guild_obj)
    if not cleanup_threads.is_running():
        cleanup_threads.start()

@tasks.loop(minutes=10)
async def cleanup_threads():
    now = datetime.datetime.utcnow()

    for guild in bot.guilds:
        for channel in guild.text_channels:
            try:
                # Skip if the bot can't see this channel
                if not channel.permissions_for(guild.me).read_messages:
                    continue

                threads = await channel.active_threads()  # ✅ This must be awaited
                for thread in threads:
                    # Only delete threads created by this bot
                    if thread.owner_id != bot.user.id:
                        continue

                    # If no activity for 1 hour
                    last = thread.last_message_at or thread.created_at
                    if (now - last).total_seconds() > 3600:
                        try:
                            await thread.delete()
                            print(f"🧹 Deleted inactive thread: {thread.name}")
                        except Exception as e:
                            print(f"❌ Failed to delete thread {thread.name}: {e}")

            except Exception as e:
                print(f"❌ Failed thread cleanup in {channel.name}: {e}")

def load_questions():
    with open(QUIZ_DATA_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)

def log_result(user, score, total, passed, required_score):
    with open(RESULTS_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([user.name, user.id, score, total, required_score, "passed" if passed else "failed"])

class QuizButton(discord.ui.Button):
    def __init__(self, label, full_label, button_letter, correct_letter, user_id, question_id, message, done_event, stop_event=None, row=None):
        safe_label = label if len(label) <= 80 else label[:77] + "..."
        super().__init__(label=safe_label, style=discord.ButtonStyle.primary, row=row)
        self.full_label = full_label
        self.button_letter = button_letter   # ✅ "a", "b", "c", or "d"
        self.correct_letter = correct_letter  # ✅ from CSV, e.g., "b"
        self.user_id = user_id
        self.question_id = question_id
        self.message = message
        self.done_event = done_event
        self.stop_event = stop_event or asyncio.Event()

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ You're not in this quiz session.", ephemeral=True)
            return

        if self.stop_event.is_set():
            await interaction.response.send_message("🛑 This quiz has been stopped.", ephemeral=True)
            return

        session = bot.quiz_sessions.get(self.user_id)
        if not session:
            await interaction.response.send_message("🛑 This quiz session has ended.", ephemeral=True)
            return

        if self.question_id in session['answered']:
            await interaction.response.send_message("⏳ You've already answered this question.", ephemeral=True)
            return

        # ✅ Correctness check
        is_correct = self.button_letter == self.correct_letter

        if is_correct:
            session['score'] += 1

        session['answered'].add(self.question_id)

        response_text = "✅ Correct!" if is_correct else "❌ Incorrect."
        await interaction.response.send_message(response_text, ephemeral=True)

        try:
            if self.message:
                await self.message.delete()
        except Exception as e:
            print(f"Could not delete question message: {e}")

        self.done_event.set()

class QuizView(discord.ui.View):
    def __init__(self, question_text, choices, correct_letter, user_id, question_id, message, done_event, stop_event=None):
        super().__init__(timeout=30)
        self.question_text = question_text
        self.choices = choices
        self.correct_letter = correct_letter.strip().lower()  # "a", "b", "c", "d"
        self.user_id = user_id
        self.question_id = question_id
        self.message = message
        self.done_event = done_event
        self.stop_event = stop_event or asyncio.Event()

        # ✅ Add buttons stacked vertically using row=idx
        for idx, choice in enumerate(choices):
            button_letter = ["a", "b", "c", "d"][idx]
            button = QuizButton(
                label=choice,
                full_label=choice,
                button_letter=button_letter,
                correct_letter=self.correct_letter,
                user_id=user_id,
                question_id=question_id,
                message=message,
                done_event=done_event,
                stop_event=self.stop_event,
                row=idx  # stack vertically
            )
            self.add_item(button)

    async def on_timeout(self):
        if not self.done_event.is_set() and not self.stop_event.is_set():
            await safe_delete_message(self.message)
            self.done_event.set()
        self.stop()

class ClearBotMessagesView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="🗑️ Clear Bot Messages", style=discord.ButtonStyle.secondary)
    async def clear_dm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This button is not for you.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        deleted_count = 0
        async for msg in interaction.channel.history(limit=200):
            if msg.author == bot.user:
                try:
                    await msg.delete()
                    deleted_count += 1
                    await asyncio.sleep(0.7)
                except Exception:
                    pass

        await interaction.followup.send(f"🗑️ Deleted {deleted_count} bot messages in this DM.", ephemeral=True)


class StartQuizButton(discord.ui.View):
    def __init__(self, user_id, questions, required_score, role_to_assign, qualifying_roles, stop_event=None):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.questions = questions
        self.required_score = required_score
        self.role_to_assign = role_to_assign
        self.qualifying_roles = qualifying_roles
        self.stop_event = stop_event or asyncio.Event()

    @discord.ui.button(label="Start Quiz", style=discord.ButtonStyle.success, row=0)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This button is not for you.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        bot.quiz_sessions[self.user_id] = {'score': 0, 'answered': set()}

        dm_channel = interaction.channel
        sent_messages = []

        for i, q in enumerate(self.questions):
            if self.stop_event.is_set():
                async with thread_semaphore:
                    msg = await dm_channel.send("🛑 Quiz has been stopped.")
                sent_messages.append(msg)
                break

            # Delete last feedback if exists
            session = bot.quiz_sessions.get(self.user_id)
            last_feedback = session.get('last_feedback') if session else None
            if last_feedback:
                try:
                    await last_feedback.delete()
                except:
                    pass

            # Countdown
            try:
                async with thread_semaphore:
                    countdown_msg = await dm_channel.send(f"⏳ Question {i+1} begins in 3...")
                sent_messages.append(countdown_msg)
                await asyncio.sleep(1)
                await countdown_msg.edit(content="2...")
                await asyncio.sleep(1)
                await countdown_msg.edit(content="1...")
                await asyncio.sleep(1)
                await countdown_msg.delete()
            except:
                return

            # Send Question
            embed = discord.Embed(title=q["question"], color=discord.Color.purple())
            choices = [q["option_a"], q["option_b"], q["option_c"], q["option_d"]]
            correct_letter = q["correct"].strip().lower()
            done_event = asyncio.Event()

            try:
                async with thread_semaphore:
                    msg = await dm_channel.send(embed=embed)
                sent_messages.append(msg)
                view = QuizView(
                    q["question"],
                    choices,
                    correct_letter,
                    self.user_id,
                    i,
                    msg,
                    done_event,
                    stop_event=self.stop_event
                )
                await msg.edit(view=view)
            except:
                continue

            # Wait with warning
            warning_msg = None
            wait_task = asyncio.create_task(done_event.wait())
            done, _ = await asyncio.wait({wait_task}, timeout=20)

            if not done_event.is_set():
                async with thread_semaphore:
                    warning_msg = await dm_channel.send("⚠️ 10 seconds left to answer...")
                sent_messages.append(warning_msg)
                done, _ = await asyncio.wait({wait_task}, timeout=10)

                if not done_event.is_set():
                    
                    async with thread_semaphore:
                        timeout_msg = await dm_channel.send("⏱️ You ran out of time!")
                    sent_messages.append(timeout_msg)
                    try:
                        await msg.delete()
                    except:
                        pass

                if warning_msg:
                    try:
                        await warning_msg.delete()
                    except:
                        pass

            if not wait_task.done():
                wait_task.cancel()
                try:
                    await wait_task
                except asyncio.CancelledError:
                    pass

        # Clean up messages after quiz ends
        for m in sent_messages:
            try:
                await m.delete()
                await asyncio.sleep(0.7)
            except:
                pass

        # Post results and Clear button
        session = bot.quiz_sessions.pop(self.user_id, {"score": 0, "answered": set()})
        score = session["score"]
        passed = score >= self.required_score
        log_result(interaction.user, score, len(self.questions), passed, self.required_score)

        try:
            guild = bot.get_guild(GUILD_ID)
            member = guild.get_member(self.user_id)
            missing_roles = [r.name for r in self.qualifying_roles if r not in (member.roles if member else [])]

            if passed:
                if member:
                    if missing_roles:
                        async with thread_semaphore:
                            msg = await dm_channel.send(
                                f"✅ You passed with {score}/{len(self.questions)}! However, you still need to complete: **{', '.join(missing_roles)}** to earn **{self.role_to_assign.name}**."
                            )
                        sent_messages.append(msg)
                    else:
                        await member.add_roles(self.role_to_assign)
                        async with thread_semaphore:
                            msg = await dm_channel.send(f"🎉 Congrats, you earned the **{self.role_to_assign.name}** role!")
                        sent_messages.append(msg)
                else:
                    async with thread_semaphore:
                        msg = await dm_channel.send("⚠️ Could not assign role because you are not currently in the server.")
                    sent_messages.append(msg)
            else:
                async with thread_semaphore:
                    msg = await dm_channel.send("❌ You did not pass. Please review and try again.")
                sent_messages.append(msg)

        except Exception as e:
            print(f"Error posting results or assigning roles: {e}")

        # Post Clear Messages Button
        try:
            clear_view = ClearBotMessagesButton(self.user_id, dm_channel, sent_messages.copy())
            async with thread_semaphore:
                msg = await dm_channel.send(
                "✅ Quiz complete. Use the button below to clear these quiz messages if you wish:",
                view=clear_view
            )
            sent_messages.append(msg)
        except Exception as e:
            print(f"Error sending clear button: {e}")

    @discord.ui.button(label="Stop Quiz", style=discord.ButtonStyle.danger, row=1)
    async def stop_quiz_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This button is not for you.", ephemeral=True)
            return

        self.stop_event.set()
        await force_stop_quiz(self.user_id)
        await interaction.response.send_message("🛑 Your quiz has been stopped and cleaned up.", ephemeral=True)

        bot.quiz_sessions.pop(self.user_id, None)
        active_threads.pop(self.user_id, None)



class ClearBotMessagesButton(discord.ui.View):
    def __init__(self, user_id, channel, sent_messages):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.channel = channel
        self.sent_messages = sent_messages

    @discord.ui.button(label="🧹 Clear Bot Messages", style=discord.ButtonStyle.blurple)
    async def clear_messages(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This button is not for you.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        deleted = 0
        for idx, m in enumerate(self.sent_messages):
            try:
                await m.delete()
                deleted += 1
                await asyncio.sleep(0.7)  # longer wait per message to reduce rate spikes
                if idx % 10 == 0 and idx != 0:
                    await asyncio.sleep(3)  # pause every 10 deletions to avoid global rate limits
            except Exception as e:
                print(f"Failed to delete message: {e}")

        await interaction.followup.send(f"🧹 Cleared {deleted} bot messages from your DM.", ephemeral=True)
        self.stop()


@bot.tree.command(guild=guild_obj, name="start_quiz_public", description="Launch a public quiz and allow users to join via reaction")
@app_commands.describe(
    num_questions="How many questions per user",
    required_score="Score needed to pass",
    role_to_assign="Role to assign to passing users",
    delay_seconds="Delay before quiz starts",
    qualifying_role="Optional role user must already have to receive reward"
)
@app_commands.choices(delay_seconds=[
    app_commands.Choice(name="30 seconds", value=30),
    app_commands.Choice(name="60 seconds", value=60),
    app_commands.Choice(name="120 seconds", value=120),
    app_commands.Choice(name="180 seconds", value=180),
    app_commands.Choice(name="300 seconds", value=300),
])
@admin_or_role_only(["mod perms"])
async def start_quiz_public(interaction: discord.Interaction,
                            num_questions: int,
                            required_score: int,
                            role_to_assign: discord.Role,
                            delay_seconds: app_commands.Choice[int],
                            qualifying_role: Optional[discord.Role] = None):

    qualifying_roles = [qualifying_role] if qualifying_role else []

    await interaction.response.defer()
    questions = load_questions()
    selected = random.sample(questions, min(num_questions, len(questions)))

    signup_msg = await interaction.channel.send(
        f"📢 A public quiz is starting in {delay_seconds.value} seconds!\n"
        f"✅ React to this message to join. Max {MAX_PARTICIPANTS} participants."
    )
    await signup_msg.add_reaction("✅")
    await asyncio.sleep(delay_seconds.value)

    signup_msg = await interaction.channel.fetch_message(signup_msg.id)
    reaction = next((r for r in signup_msg.reactions if str(r.emoji) == "✅"), None)
    if not reaction:
        await interaction.channel.send("No participants found.")
        return

    users = [u async for u in reaction.users() if not u.bot][:MAX_PARTICIPANTS]
    if not users:
        await interaction.channel.send("❌ No users signed up.")
        return

    bot.quiz_sessions = {}
    leaderboard = []

    for user in users:
        try:
            thread = await interaction.channel.create_thread(
                name=f"quiz-{user.name}",
                type=discord.ChannelType.private_thread,
                invitable=False
            )
            await thread.send(f"{user.mention} 🎯 Your quiz starts now!")
            bot.quiz_sessions[user.id] = {'score': 0, 'answered': set()}

            for i, q in enumerate(selected):
                await thread.send(f"⏳ Question {i+1} begins in 3...")
                await asyncio.sleep(1)
                await thread.send("2...")
                await asyncio.sleep(1)
                await thread.send("1...")
                await asyncio.sleep(1)

                embed = discord.Embed(title=q["question"], color=discord.Color.blue())
                choices = [q["option_a"], q["option_b"], q["option_c"], q["option_d"]]
                done_event = asyncio.Event()
                msg = await thread.send(embed=embed)
                view = QuizView(
                    question=q["question"],
                    options=[q["option_a"], q["option_b"], q["option_c"], q["option_d"]],
                    correct_answer=q["correct"].strip(),
                    user_id=self.user_id,
                    question_id=i,
                    message=msg,
                    done_event=done_event)
                await msg.edit(view=view)

                try:
                    await asyncio.wait_for(done_event.wait(), timeout=30)
                except asyncio.TimeoutError:
                    await thread.send("⏱️ You ran out of time!")
                    try:
                        await msg.delete()
                    except Exception as e:
                        print(f"Could not delete timed-out question: {e}")
                        
                # ✅ CLEANUP TASK TO AVOID "destroyed but pending" WARNINGS
                if not wait_task.done():
                    wait_task.cancel()
                    try:
                        await wait_task
                    except asyncio.CancelledError:
                        pass

            score = bot.quiz_sessions[user.id]['score']
            passed = score >= required_score
            leaderboard.append((user.name, score))

            log_result(user, score, len(selected), passed, required_score)
            missing_roles = [r.name for r in qualifying_roles if r not in user.roles]
            if passed:
                if missing_roles:
                    await thread.send(
                        f"✅ You passed with {score}/{len(selected)}! However, you have not passed the quizzes for the following roles: **{', '.join(missing_roles)}**.\n"
                        f"Please complete those chapters and retake this quiz to acquire the **{role_to_assign.name}** role."
                    )
                else:
                    await user.add_roles(role_to_assign)
                    await thread.send(f"✅ You passed with {score}/{len(selected)}! Role assigned.")
            else:
                await thread.send(f"❌ You scored {score}/{len(selected)}. Better luck next time!")

            await asyncio.sleep(5)
            await thread.delete()

        except Exception as e:
            await interaction.channel.send(f"⚠️ Could not start quiz for {user.mention}: {e}")

    leaderboard.sort(key=lambda x: x[1], reverse=True)
    leaderboard_msg = "**📊 Quiz Leaderboard:**\n"
    for i, (name, score) in enumerate(leaderboard, 1):
        leaderboard_msg += f"{i}. {name} — {score}/{len(selected)}\n"
    await interaction.channel.send(leaderboard_msg)

    try:
        history = defaultdict(list)
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                username, user_id, score, total, required, result = row
                history[username].append(int(score))

        history_scores = [(user, sum(scores), len(scores)) for user, scores in history.items()]
        history_scores.sort(key=lambda x: x[1], reverse=True)

        history_msg = "**🏆 Historical Leaderboard (All-Time):**\n"
        for i, (user, total_score, attempts) in enumerate(history_scores[:25], 1):
            avg = round(total_score / attempts, 2)
            history_msg += f"{i}. {user} — Total: {total_score} | Avg: {avg} | Attempts: {attempts}\n"

        await interaction.channel.send(history_msg)
    except Exception as e:
        await interaction.channel.send(f"⚠️ Could not load historical leaderboard: {e}")

@bot.tree.command(guild=guild_obj, name="post_quiz_button", description="Post a quiz button for users to click.")
@app_commands.describe(
    quiz_message="The message that will appear above the button",
    num_questions="Number of questions to ask",
    required_score="Number of correct answers needed to pass",
    role_to_assign="Role to assign if user passes",
    qualifying_role="Optional role user must already have to receive reward"
)
async def post_quiz_button(interaction: discord.Interaction,
                           quiz_message: str,
                           num_questions: int,
                           required_score: int,
                           role_to_assign: discord.Role,
                           qualifying_role: Optional[discord.Role] = None):

    qualifying_roles = [qualifying_role] if qualifying_role else []

    quiz_files = [f for f in os.listdir() if f.endswith(".csv") and f != "results.csv"]
    if not quiz_files:
        await interaction.response.send_message("⚠️ No quiz files found in the directory.", ephemeral=True)
        return

    class FileSelect(discord.ui.Select):
        def __init__(self, files):
            options = [discord.SelectOption(label=f, value=f) for f in files]
            super().__init__(placeholder="Choose a quiz CSV...", options=options)

        async def callback(self, select_interaction: discord.Interaction):
            try:
                await select_interaction.channel.send(
                    content=quiz_message,
                    view=QuizTriggerButtonFull(
                        quiz_file=self.values[0],
                        num_questions=num_questions,
                        required_score=required_score,
                        role_id=role_to_assign.id,
                        qualifying_roles=qualifying_roles
                    )
                )
                await select_interaction.response.defer()
            except Exception as e:
                if select_interaction.response.is_done():
                    try:
                        await select_interaction.followup.send(f"⚠️ Could not post quiz button: {e}", ephemeral=True)
                    except Exception as err:
                        print(f"Failed to send followup: {err}")
                else:
                    await select_interaction.response.send_message(f"⚠️ Could not post quiz button: {e}", ephemeral=True)

    class FileSelectView(discord.ui.View):
        def __init__(self, files):
            super().__init__(timeout=60)
            self.add_item(FileSelect(files))

    await interaction.response.send_message("📁 Select which quiz to post:", view=FileSelectView(quiz_files), ephemeral=True)

# ✅ QUIZBOT MODULE - Trigger Button for Individual Quiz
# Handles CSV loading, eligibility checks, thread creation, and Start button

class QuizTriggerButtonFull(discord.ui.View):
    def __init__(self, quiz_file: str, num_questions: int, required_score: int, role_id: int, qualifying_roles: list):
        super().__init__(timeout=None)
        self.quiz_file = quiz_file
        self.num_questions = num_questions
        self.required_score = required_score
        self.role_id = role_id
        self.qualifying_roles = qualifying_roles

    @discord.ui.button(label="Take Quiz", style=discord.ButtonStyle.primary)
    async def start_quiz(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        role_to_assign = discord.utils.get(interaction.guild.roles, id=self.role_id)

        await interaction.response.defer(ephemeral=True)

        if not can_send_dm():
            await interaction.followup.send(
                "🚦 The quiz bot is currently busy. Please try again in a few minutes.",
                ephemeral=True
            )
            return

        # Load questions
        try:
            with open(self.quiz_file, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                questions = list(reader)

            required_columns = {"question", "option_a", "option_b", "option_c", "option_d", "correct"}
            if not required_columns.issubset(reader.fieldnames):
                raise ValueError("CSV missing required columns.")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Could not start quiz: {e}", ephemeral=True)
            return

        selected = random.sample(questions, min(self.num_questions, len(questions)))

        try:
            dm_channel = await user.create_dm()
            register_dm_send()
            async with thread_semaphore:
                await dm_channel.send(
                    "✅ Your quiz is starting here in your DMs. Let’s begin!"
                )

            async with thread_semaphore:
                await dm_channel.send(
                    f"{user.mention} 🎯 Click below to begin your quiz:",
                    view=StartQuizButton(
                        user_id=user.id,
                        questions=selected,
                        required_score=self.required_score,
                        role_to_assign=role_to_assign,
                        qualifying_roles=self.qualifying_roles
                    )
                )

            await interaction.followup.send("📩 Quiz has been sent to your DMs!", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Cannot send you a DM. Please enable DMs from server members and try again.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"⚠️ Failed to send quiz: {e}", ephemeral=True)

        
@bot.tree.command(guild=guild_obj, name="clean_threads", description="Clean all threads in a channel created by this bot")
@app_commands.describe(
    target_channel="Channel to clean up threads in"
)
@admin_or_role_only(["mod perms"])
async def clean_threads(interaction: discord.Interaction, target_channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)

    try:
        threads = await target_channel.active_threads()
        deleted = 0
        skipped = 0

        for thread in threads:
            if thread.owner_id == bot.user.id:
                try:
                    await thread.delete()
                    deleted += 1
                except Exception as e:
                    print(f"❌ Failed to delete thread {thread.name}: {e}")
            else:
                skipped += 1

        await interaction.followup.send(
            f"🧹 Cleaned up threads in {target_channel.mention}.\n"
            f"✅ Deleted: `{deleted}`\n"
            f"🚫 Skipped (not bot-owned): `{skipped}`",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"⚠️ Failed to clean threads: {e}", ephemeral=True)

bot.run("MTM3MDM4MzkwMTgxMzM3OTExMg.GmqKcB.aA0ztyC__xS0YRIU1aEUwf5raguKOFBLtnLr_o")