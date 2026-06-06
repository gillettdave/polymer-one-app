"""
Turkey Man Code - Discord Submissions & Review Workflow Bot
Main bot entry point.
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
import sys
from datetime import datetime, timedelta
from typing import Optional

from config import Config
from storage import Storage
from review import ReviewHandler
from permissions import check_reviewer_permission, check_admin_permission
from utils import generate_submission_id, format_timestamp, get_attachment_info, validate_url

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SubmissionBot(commands.Bot):
    """Main bot class."""
    
    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(command_prefix="!", intents=intents)
        
        self.config = config
        self.storage = Storage(config.data_dir)
        self.review_handler = ReviewHandler(self, self.storage, self.config)
    
    async def setup_hook(self):
        """Called when the bot is starting up."""
        # Sync commands to the configured guild
        if self.config.guild_id:
            try:
                guild = discord.Object(id=self.config.guild_id)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                logger.info(f"Synced commands to guild {self.config.guild_id}")
            except Exception as e:
                logger.error(f"Error syncing commands: {e}")
    
    async def on_ready(self):
        """Called when the bot is ready."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")
        
        # Store review handler on bot instance for modal access
        self.review_handler = ReviewHandler(self, self.storage, self.config)
    
    async def on_guild_join(self, guild: discord.Guild):
        """Called when the bot joins a guild."""
        logger.info(f"Joined guild: {guild.name} (ID: {guild.id})")
    
    async def on_guild_remove(self, guild: discord.Guild):
        """Called when the bot leaves a guild."""
        logger.info(f"Left guild: {guild.name} (ID: {guild.id})")


# Initialize bot
config = Config()
is_valid, error = config.validate()
if not is_valid:
    logger.error(f"Configuration error: {error}")
    sys.exit(1)

bot = SubmissionBot(config)


# ==================== USER COMMANDS ====================

@bot.tree.command(name="submit", description="Submit a new submission for review")
@app_commands.describe(
    submission_type="The type of submission",
    title="A short title for your submission",
    description="A detailed description",
    link="Optional link (URL)",
    attachment="Optional file attachment"
)
async def submit(
    interaction: discord.Interaction,
    submission_type: str,
    title: str,
    description: str,
    link: Optional[str] = None,
    attachment: Optional[discord.Attachment] = None
):
    """Handle submission command."""
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True
        )
        return
    
    # Validate submission type
    stype = config.get_submission_type(submission_type)
    if not stype:
        await interaction.response.send_message(
            f"Invalid submission type: `{submission_type}`. "
            f"Available types: {', '.join(config.get_all_submission_types().keys())}",
            ephemeral=True
        )
        return
    
    # Validate requirements
    if stype.get("require_link") and not link:
        await interaction.response.send_message(
            "This submission type requires a link.",
            ephemeral=True
        )
        return
    
    if stype.get("require_attachment") and not attachment:
        await interaction.response.send_message(
            "This submission type requires an attachment.",
            ephemeral=True
        )
        return
    
    # Validate link format if provided
    if link and not validate_url(link):
        await interaction.response.send_message(
            "Invalid URL format. Please provide a valid http:// or https:// URL.",
            ephemeral=True
        )
        return
    
    # Check attachments allowed
    if attachment and not config.allow_attachments:
        await interaction.response.send_message(
            "Attachments are not enabled for this bot.",
            ephemeral=True
        )
        return
    
    # Get bot instance
    bot_instance = interaction.client
    
    # Check cooldown
    cooldown_seconds = stype.get("cooldown_override_seconds") or config.cooldown_seconds
    last_submission = bot_instance.storage.get_last_submission_time(
        interaction.user.id,
        submission_type
    )
    
    if last_submission:
        time_since = (datetime.utcnow() - last_submission.replace(tzinfo=None)).total_seconds()
        if time_since < cooldown_seconds:
            remaining = int(cooldown_seconds - time_since)
            await interaction.response.send_message(
                f"You are on cooldown. Please wait {remaining} more seconds.",
                ephemeral=True
            )
            return
    
    # Check daily limit
    count_today = bot_instance.storage.get_user_submission_count_today(
        interaction.user.id,
        submission_type
    )
    
    if count_today >= config.max_submissions_per_day:
        await interaction.response.send_message(
            f"You have reached the daily limit of {config.max_submissions_per_day} submissions for this type.",
            ephemeral=True
        )
        return
    
    # Create submission
    submission_id = generate_submission_id()
    attachment_info = get_attachment_info(attachment)
    
    submission = {
        "submission_id": submission_id,
        "guild_id": interaction.guild.id,
        "user_id": interaction.user.id,
        "username_at_time": str(interaction.user),
        "submission_type_key": submission_type,
        "title": title[:200],  # Discord limit
        "description": description[:4000],  # Discord limit
        "link": link,
        "attachment_url": attachment_info.get("url") if attachment_info else None,
        "attachment_filename": attachment_info.get("filename") if attachment_info else None,
        "created_at": datetime.utcnow().isoformat(),
        "status": "pending",
        "review_message_id": None,
        "review_channel_id": config.review_channel_id,
        "review_thread_id": None
    }
    
    # Save submission
    bot_instance.storage.save_submission(submission)
    
    # Create review message
    review_message = await bot_instance.review_handler.create_review_message(submission)
    
    if not review_message:
        await interaction.response.send_message(
            f"✅ Submission created (ID: {submission_id}), but failed to create review message. "
            f"Please contact an administrator.",
            ephemeral=True
        )
        logger.error(f"Failed to create review message for submission {submission_id}")
        return
    
    # Confirm to user
    await interaction.response.send_message(
        f"✅ Submission created successfully!\n"
        f"**Submission ID:** `{submission_id}`\n"
        f"Your submission has been sent for review.",
        ephemeral=True
    )
    
    logger.info(f"New submission: {submission_id} by {interaction.user.id}")


@bot.tree.command(name="my_submissions", description="View your recent submissions")
async def my_submissions(interaction: discord.Interaction):
    """Show user's recent submissions."""
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True
        )
        return
    
    bot_instance = interaction.client
    submissions = bot_instance.storage.get_user_submissions(interaction.user.id, limit=5)
    
    if not submissions:
        await interaction.response.send_message(
            "You haven't submitted anything yet.",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="Your Recent Submissions",
        color=discord.Color.blue()
    )
    
    for sub in submissions:
        status_emoji = {
            "pending": "⏳",
            "approved": "✅",
            "rejected": "❌",
            "changes_requested": "💬"
        }
        
        status = sub.get("status", "pending")
        embed.add_field(
            name=f"{status_emoji.get(status, '')} {sub.get('title', 'Untitled')}",
            value=(
                f"**ID:** `{sub.get('submission_id')}`\n"
                f"**Type:** {sub.get('submission_type_key')}\n"
                f"**Status:** {status.upper()}\n"
                f"**Created:** {format_timestamp(datetime.fromisoformat(sub.get('created_at', '').replace('Z', '+00:00')))}"
            ),
            inline=False
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ==================== ADMIN/REVIEWER COMMANDS ====================

@bot.tree.command(name="set_review_channel", description="Set the review channel (Admin only)")
@app_commands.describe(channel="The channel where submissions will be reviewed")
async def set_review_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Set the review channel."""
    if not await check_admin_permission(interaction, config.admin_role_ids):
        return
    
    config.review_channel_id = channel.id
    
    # Update .env would require file write, but for now we'll just update in memory
    # In production, you might want to persist this
    
    await interaction.response.send_message(
        f"✅ Review channel set to {channel.mention}",
        ephemeral=True
    )
    
    logger.info(f"Review channel updated to {channel.id} by {interaction.user.id}")


@bot.tree.command(name="set_notify_channel", description="Set the notification channel for DM fallbacks (Admin only)")
@app_commands.describe(channel="The channel for notifications when DMs fail")
async def set_notify_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Set the notification channel."""
    if not await check_admin_permission(interaction, config.admin_role_ids):
        return
    
    config.notify_channel_id = channel.id
    
    await interaction.response.send_message(
        f"✅ Notification channel set to {channel.mention}",
        ephemeral=True
    )
    
    logger.info(f"Notification channel updated to {channel.id} by {interaction.user.id}")


@bot.tree.command(name="reload_config", description="Reload submission types configuration (Admin only)")
async def reload_config(interaction: discord.Interaction):
    """Reload the submission types configuration."""
    if not await check_admin_permission(interaction, config.admin_role_ids):
        return
    
    count = config.reload_submission_types()
    
    await interaction.response.send_message(
        f"✅ Configuration reloaded. Found {count} submission type(s).",
        ephemeral=True
    )
    
    logger.info(f"Configuration reloaded by {interaction.user.id}")


@bot.tree.command(name="submission_lookup", description="Look up a submission by ID (Reviewer only)")
@app_commands.describe(submission_id="The submission ID to look up")
async def submission_lookup(interaction: discord.Interaction, submission_id: str):
    """Look up a submission by ID."""
    if not await check_reviewer_permission(
        interaction,
        config.reviewer_role_ids,
        config.admin_role_ids
    ):
        return
    
    bot_instance = interaction.client
    submission = bot_instance.storage.get_submission(submission_id)
    
    if not submission:
        await interaction.response.send_message(
            f"Submission `{submission_id}` not found.",
            ephemeral=True
        )
        return
    
    from ui_components import create_submission_embed
    embed = create_submission_embed(submission)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="status", description="View bot status and statistics")
async def status(interaction: discord.Interaction):
    """Show bot status."""
    bot_instance = interaction.client
    stats = bot_instance.storage.get_stats()
    
    is_valid, error = config.validate()
    config_status = {
        "valid": is_valid,
        "error": error
    }
    
    from ui_components import create_status_embed
    embed = create_status_embed(stats, config_status)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ==================== AUTOCOMPLETE ====================

@submit.autocomplete("submission_type")
async def submission_type_autocomplete(
    interaction: discord.Interaction,
    current: str
) -> list[app_commands.Choice[str]]:
    """Autocomplete for submission types."""
    types = config.get_all_submission_types()
    choices = []
    
    for key, stype in types.items():
        label = stype.get("label", key)
        if current.lower() in key.lower() or current.lower() in label.lower():
            choices.append(app_commands.Choice(
                name=f"{label} ({key})",
                value=key
            ))
    
    return choices[:25]  # Discord limit


# ==================== MAIN ====================

if __name__ == "__main__":
    try:
        bot.run(config.discord_token)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

