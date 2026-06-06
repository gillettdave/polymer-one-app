"""
Review workflow handling for submissions.
"""
import discord
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from storage import Storage
from config import Config
from permissions import can_review, is_role_allowlisted
from ui_components import create_submission_embed, ReviewButtons
from utils import format_timestamp

logger = logging.getLogger(__name__)


class ReviewHandler:
    """Handles the review workflow for submissions."""
    
    def __init__(self, bot: discord.Client, storage: Storage, config: Config):
        self.bot = bot
        self.storage = storage
        self.config = config
    
    async def create_review_message(
        self,
        submission: Dict[str, Any]
    ) -> Optional[discord.Message]:
        """
        Create a review message (in channel or thread) for a submission.
        Returns the created message, or None if creation failed.
        """
        guild = self.bot.get_guild(self.config.guild_id)
        if not guild:
            return None
        
        review_channel = guild.get_channel(self.config.review_channel_id)
        if not review_channel:
            return None
        
        # Check permissions
        if not review_channel.permissions_for(guild.me).send_messages:
            return None
        
        embed = create_submission_embed(submission)
        
        view = ReviewButtons(
            submission_id=submission["submission_id"],
            reviewer_role_ids=self.config.reviewer_role_ids,
            admin_role_ids=self.config.admin_role_ids
        )
        
        try:
            if self.config.use_threads:
                # Create a thread for this submission
                thread_name = f"{submission['submission_id']} - {submission.get('title', 'Submission')[:50]}"
                
                # Check thread creation permissions (public threads only)
                bot_perms = review_channel.permissions_for(guild.me)
                can_create_threads = bot_perms.create_public_threads
                
                if can_create_threads:
                    try:
                        message = await review_channel.send(
                            embed=embed,
                            view=view
                        )
                        thread = await message.create_thread(name=thread_name)
                        
                        # Check if bot can post in threads
                        if not bot_perms.send_messages_in_threads:
                            logger.warning(
                                f"Bot lacks send_messages_in_threads permission. "
                                f"Outcome messages will be posted in review channel instead of thread."
                            )
                        
                        # Update submission with thread ID
                        self.storage.update_submission_status(
                            submission["submission_id"],
                            submission["status"],
                            review_message_id=message.id,
                            review_thread_id=thread.id
                        )
                        
                        return message
                    except discord.HTTPException as e:
                        logger.warning(
                            f"Thread creation failed for submission {submission['submission_id']}: {e}. "
                            f"Falling back to review channel message-only mode."
                        )
                        # Fall through to channel-only mode
                else:
                    logger.warning(
                        f"Bot lacks create_public_threads permission. "
                        f"Falling back to review channel message-only mode for submission {submission['submission_id']}."
                    )
                
                # Fallback to regular message if thread creation fails or permissions missing
                message = await review_channel.send(
                    embed=embed,
                    view=view
                )
                self.storage.update_submission_status(
                    submission["submission_id"],
                    submission["status"],
                    review_message_id=message.id
                )
                return message
            else:
                # Post directly to channel
                message = await review_channel.send(
                    embed=embed,
                    view=view
                )
                self.storage.update_submission_status(
                    submission["submission_id"],
                    submission["status"],
                    review_message_id=message.id
                )
                return message
        except discord.HTTPException as e:
            logger.error(f"Error creating review message for submission {submission.get('submission_id', 'unknown')}: {e}")
            return None
    
    async def process_review_action(
        self,
        interaction: discord.Interaction,
        submission_id: str,
        action: str,
        note: Optional[str] = None
    ) -> tuple[bool, str]:
        """
        Process a review action (approve/reject/request_changes).
        Returns (success, message).
        """
        if not isinstance(interaction.user, discord.Member):
            return False, "This action can only be used in a server."
        
        # Defense-in-depth: Check permissions even though UI layer also checks
        if not can_review(
            interaction.user,
            self.config.reviewer_role_ids,
            self.config.admin_role_ids
        ):
            return False, "You don't have permission to review submissions."
        
        # Get submission
        submission = self.storage.get_submission(submission_id)
        if not submission:
            return False, "Submission not found."
        
        # Check if already reviewed
        if submission.get("status") != "pending":
            return False, f"Submission has already been {submission.get('status')}."
        
        # Determine new status
        status_map = {
            "approve": "approved",
            "reject": "rejected",
            "request_changes": "changes_requested"
        }
        
        new_status = status_map.get(action)
        if not new_status:
            return False, f"Invalid action: {action}"
        
        # Update submission
        self.storage.update_submission_status(submission_id, new_status)
        
        # Log decision
        self.storage.log_decision(
            submission_id=submission_id,
            action=action,
            reviewer_id=interaction.user.id,
            reviewer_name=str(interaction.user),
            note=note
        )
        
        # Update the review message embed
        await self._update_review_message(submission_id, new_status, interaction.user, note)
        
        # Assign role if approved and configured
        if new_status == "approved":
            await self._assign_approval_role(submission, interaction.user)
        
        # Notify the submitter
        await self._notify_submitter(submission, new_status, note, interaction.user)
        
        # Post outcome in review thread/channel
        await self._post_outcome(submission, new_status, interaction.user, note)
        
        return True, f"Submission {new_status} successfully."
    
    async def _update_review_message(
        self,
        submission_id: str,
        new_status: str,
        reviewer: discord.Member,
        note: Optional[str]
    ) -> None:
        """Update the review message embed with the decision."""
        submission = self.storage.get_submission(submission_id)
        if not submission:
            return
        
        review_message_id = submission.get("review_message_id")
        review_channel_id = submission.get("review_channel_id")
        
        if not review_message_id or not review_channel_id:
            return
        
        guild = self.bot.get_guild(self.config.guild_id)
        if not guild:
            return
        
        review_channel = guild.get_channel(review_channel_id)
        if not review_channel:
            return
        
        try:
            # Try to get the message (might be in a thread)
            message = None
            review_thread_id = submission.get("review_thread_id")
            
            if review_thread_id:
                thread = guild.get_thread(review_thread_id)
                if thread:
                    try:
                        message = await thread.fetch_message(review_message_id)
                    except discord.NotFound:
                        pass
            
            if not message:
                try:
                    message = await review_channel.fetch_message(review_message_id)
                except discord.NotFound:
                    return
            
            # Update embed
            embed = create_submission_embed(submission)
            
            # Update status field
            for i, field in enumerate(embed.fields):
                if field.name == "Status":
                    embed.set_field_at(
                        i,
                        name="Status",
                        value=new_status.upper(),
                        inline=True
                    )
                    break
            
            # Add review info
            status_emoji = {
                "approved": "✅",
                "rejected": "❌",
                "changes_requested": "💬"
            }
            
            embed.add_field(
                name=f"{status_emoji.get(new_status, '')} Reviewed",
                value=f"By {reviewer.mention} at {format_timestamp()}",
                inline=False
            )
            
            if note:
                embed.add_field(
                    name="Review Note",
                    value=note[:1000],  # Discord embed field limit
                    inline=False
                )
            
            # Disable buttons (update view to be empty)
            await message.edit(embed=embed, view=None)
        except discord.HTTPException as e:
            logger.error(f"Error updating review message for submission {submission_id}: {e}")
    
    async def _assign_approval_role(
        self,
        submission: Dict[str, Any],
        reviewer: discord.Member
    ) -> None:
        """Assign the default approval role if configured."""
        submission_type_key = submission.get("submission_type_key")
        submission_type = self.config.get_submission_type(submission_type_key)
        
        if not submission_type:
            return
        
        role_id = submission_type.get("default_approval_role_id")
        if not role_id:
            return
        
        # Check if role is allowlisted
        allowlisted_roles = self.config.get_allowlisted_role_ids()
        if not is_role_allowlisted(role_id, allowlisted_roles):
            logger.warning(f"Role {role_id} not in allowlist, skipping assignment for submission {submission.get('submission_id')}")
            return
        
        guild = self.bot.get_guild(self.config.guild_id)
        if not guild:
            return
        
        role = guild.get_role(role_id)
        if not role:
            logger.warning(f"Role {role_id} not found in guild for submission {submission.get('submission_id')}")
            return
        
        user_id = submission.get("user_id")
        member = guild.get_member(user_id)
        if not member:
            # Try to fetch member
            try:
                member = await guild.fetch_member(user_id)
            except discord.NotFound:
                logger.warning(f"User {user_id} not found in guild for role assignment (submission {submission.get('submission_id')})")
                return
        
        # Check if bot has permission to manage roles
        if not guild.me.guild_permissions.manage_roles:
            logger.warning(f"Bot lacks manage_roles permission for role assignment (submission {submission.get('submission_id')})")
            return
        
        # Check role hierarchy
        if role.position >= guild.me.top_role.position:
            logger.warning(f"Role {role.name} (ID: {role_id}) is higher than bot's highest role, cannot assign (submission {submission.get('submission_id')})")
            return
        
        try:
            if role not in member.roles:
                await member.add_roles(role, reason=f"Submission {submission.get('submission_id')} approved")
        except discord.HTTPException as e:
            logger.error(f"Error assigning role {role_id} to user {user_id} for submission {submission.get('submission_id')}: {e}")
    
    async def _notify_submitter(
        self,
        submission: Dict[str, Any],
        status: str,
        note: Optional[str],
        reviewer: discord.Member
    ) -> None:
        """Send a DM to the submitter about the decision."""
        user_id = submission.get("user_id")
        user = self.bot.get_user(user_id)
        
        if not user:
            # Try to fetch user
            try:
                user = await self.bot.fetch_user(user_id)
            except discord.NotFound:
                await self._fallback_notify(submission, status, note, reviewer)
                return
        
        status_messages = {
            "approved": "✅ Your submission has been **approved**!",
            "rejected": "❌ Your submission has been **rejected**.",
            "changes_requested": "💬 Your submission needs **changes** before it can be approved."
        }
        
        embed = discord.Embed(
            title=status_messages.get(status, f"Your submission has been {status}"),
            description=f"**Submission:** {submission.get('title', 'Untitled')}\n"
                       f"**ID:** {submission.get('submission_id')}",
            color=discord.Color.green() if status == "approved" else discord.Color.orange(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="Reviewed By",
            value=str(reviewer),
            inline=True
        )
        
        if note:
            embed.add_field(
                name="Note",
                value=note[:1000],
                inline=False
            )
        
        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            # DMs closed, use fallback
            await self._fallback_notify(submission, status, note, reviewer)
        except discord.HTTPException as e:
            logger.error(f"Error sending DM to user {user_id} for submission {submission.get('submission_id')}: {e}")
            await self._fallback_notify(submission, status, note, reviewer)
    
    async def _fallback_notify(
        self,
        submission: Dict[str, Any],
        status: str,
        note: Optional[str],
        reviewer: discord.Member
    ) -> None:
        """Fallback notification in a channel if DMs fail."""
        if not self.config.notify_channel_id:
            return
        
        guild = self.bot.get_guild(self.config.guild_id)
        if not guild:
            return
        
        notify_channel = guild.get_channel(self.config.notify_channel_id)
        if not notify_channel:
            return
        
        status_messages = {
            "approved": "✅ Your submission has been **approved**!",
            "rejected": "❌ Your submission has been **rejected**.",
            "changes_requested": "💬 Your submission needs **changes** before it can be approved."
        }
        
        user_mention = f"<@{submission.get('user_id')}>"
        message = (
            f"{user_mention} - {status_messages.get(status, f'Your submission has been {status}')}\n"
            f"**Submission:** {submission.get('title', 'Untitled')} (ID: {submission.get('submission_id')})\n"
            f"**Reviewed by:** {reviewer.mention}"
        )
        
        if note:
            message += f"\n**Note:** {note}"
        
        try:
            await notify_channel.send(message)
        except discord.HTTPException as e:
            logger.error(f"Error sending fallback notification to channel {self.config.notify_channel_id} for submission {submission.get('submission_id')}: {e}")
    
    async def _post_outcome(
        self,
        submission: Dict[str, Any],
        status: str,
        reviewer: discord.Member,
        note: Optional[str]
    ) -> None:
        """Post the outcome in the review thread/channel."""
        review_channel_id = submission.get("review_channel_id")
        review_thread_id = submission.get("review_thread_id")
        
        if not review_channel_id:
            return
        
        guild = self.bot.get_guild(self.config.guild_id)
        if not guild:
            return
        
        channel = None
        if review_thread_id:
            thread = guild.get_thread(review_thread_id)
            if thread:
                # Check if bot can post in thread
                bot_perms = thread.permissions_for(guild.me)
                if bot_perms.send_messages_in_threads:
                    channel = thread
                else:
                    logger.warning(
                        f"Bot lacks send_messages_in_threads permission for thread {review_thread_id}. "
                        f"Posting outcome in review channel instead."
                    )
        
        if not channel:
            channel = guild.get_channel(review_channel_id)
        
        if not channel:
            logger.error(f"Could not find review channel {review_channel_id} or thread {review_thread_id} for outcome message")
            return
        
        status_emoji = {
            "approved": "✅",
            "rejected": "❌",
            "changes_requested": "💬"
        }
        
        message = (
            f"{status_emoji.get(status, '')} **Decision:** {status.upper()}\n"
            f"**Reviewed by:** {reviewer.mention}\n"
            f"**Submission ID:** {submission.get('submission_id')}"
        )
        
        if note:
            message += f"\n**Note:** {note}"
        
        try:
            await channel.send(message)
        except discord.HTTPException as e:
            logger.error(f"Error posting outcome for submission {submission.get('submission_id')}: {e}")

