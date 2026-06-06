"""
UI components (embeds, buttons, modals) for the submission bot.
"""
import discord
from typing import Optional, Dict, Any
from datetime import datetime
from utils import format_timestamp, truncate_string


class ReviewButtons(discord.ui.View):
    """Buttons for reviewing a submission."""
    
    def __init__(
        self,
        submission_id: str,
        reviewer_role_ids: list[int],
        admin_role_ids: list[int]
    ):
        super().__init__(timeout=None)  # Persistent view
        self.submission_id = submission_id
        self.reviewer_role_ids = reviewer_role_ids
        self.admin_role_ids = admin_role_ids
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if the user can review."""
        from permissions import can_review
        
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "This action can only be used in a server.",
                ephemeral=True
            )
            return False
        
        if not can_review(
            interaction.user,
            self.reviewer_role_ids,
            self.admin_role_ids
        ):
            await interaction.response.send_message(
                "You don't have permission to review submissions.",
                ephemeral=True
            )
            return False
        
        return True
    
    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success,
        emoji="✅"
    )
    async def approve_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Handle approve button click."""
        modal = ReviewNoteModal(
            action="approve",
            submission_id=self.submission_id,
            require_note=False
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.danger,
        emoji="❌"
    )
    async def reject_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Handle reject button click."""
        modal = ReviewNoteModal(
            action="reject",
            submission_id=self.submission_id,
            require_note=True
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="Request Changes",
        style=discord.ButtonStyle.secondary,
        emoji="💬"
    )
    async def request_changes_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """Handle request changes button click."""
        modal = ReviewNoteModal(
            action="request_changes",
            submission_id=self.submission_id,
            require_note=True
        )
        await interaction.response.send_modal(modal)


class ReviewNoteModal(discord.ui.Modal, title="Review Note"):
    """Modal for entering a review note."""
    
    def __init__(self, action: str, submission_id: str, require_note: bool = False):
        super().__init__()
        self.action = action
        self.submission_id = submission_id
        self.require_note = require_note
        
        # Add note input
        self.note_input = discord.ui.TextInput(
            label="Review Note (Optional)" if not require_note else "Review Note (Required)",
            placeholder="Enter any notes about your decision...",
            style=discord.TextStyle.paragraph,
            required=require_note,
            max_length=1000
        )
        self.add_item(self.note_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        from review import ReviewHandler
        
        note = self.note_input.value or None
        
        # Get the review handler from the bot
        bot = interaction.client
        if not hasattr(bot, 'review_handler'):
            await interaction.response.send_message(
                "Error: Review handler not available.",
                ephemeral=True
            )
            return
        
        review_handler: ReviewHandler = bot.review_handler
        
        # Process the review action
        success, message = await review_handler.process_review_action(
            interaction=interaction,
            submission_id=self.submission_id,
            action=self.action,
            note=note
        )
        
        if success:
            await interaction.response.send_message(
                message,
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Error: {message}",
                ephemeral=True
            )


def create_submission_embed(submission: Dict[str, Any]) -> discord.Embed:
    """Create an embed for displaying a submission."""
    embed = discord.Embed(
        title=f"📝 {submission.get('title', 'Untitled')}",
        description=truncate_string(submission.get('description', ''), 2000),
        color=discord.Color.blue(),
        timestamp=datetime.fromisoformat(
            submission.get('created_at', datetime.utcnow().isoformat())
            .replace('Z', '+00:00')
        )
    )
    
    # Add fields
    embed.add_field(
        name="Submission Type",
        value=submission.get('submission_type_key', 'unknown'),
        inline=True
    )
    
    embed.add_field(
        name="Status",
        value=submission.get('status', 'pending').upper(),
        inline=True
    )
    
    embed.add_field(
        name="Submitted By",
        value=f"<@{submission.get('user_id')}> ({submission.get('username_at_time', 'Unknown')})",
        inline=False
    )
    
    if submission.get('link'):
        embed.add_field(
            name="Link",
            value=submission.get('link'),
            inline=False
        )
    
    if submission.get('attachment_url'):
        embed.add_field(
            name="Attachment",
            value=f"[{submission.get('attachment_filename', 'File')}]({submission.get('attachment_url')})",
            inline=False
        )
    
    # Footer with submission ID
    embed.set_footer(text=f"Submission ID: {submission.get('submission_id')}")
    
    return embed


def create_status_embed(stats: Dict[str, Any], config_status: Dict[str, Any]) -> discord.Embed:
    """Create an embed for bot status."""
    embed = discord.Embed(
        title="🤖 Bot Status",
        color=discord.Color.green()
    )
    
    # Configuration status
    config_text = "✅ Configured" if config_status.get("valid") else "❌ Not Configured"
    embed.add_field(
        name="Configuration",
        value=config_text,
        inline=True
    )
    
    if not config_status.get("valid"):
        embed.add_field(
            name="Error",
            value=config_status.get("error", "Unknown error"),
            inline=False
        )
    
    # Statistics
    embed.add_field(
        name="Total Submissions",
        value=str(stats.get("total_submissions", 0)),
        inline=True
    )
    
    embed.add_field(
        name="Pending",
        value=str(stats.get("pending", 0)),
        inline=True
    )
    
    embed.add_field(
        name="Approved",
        value=str(stats.get("approved", 0)),
        inline=True
    )
    
    embed.add_field(
        name="Rejected",
        value=str(stats.get("rejected", 0)),
        inline=True
    )
    
    embed.add_field(
        name="Changes Requested",
        value=str(stats.get("changes_requested", 0)),
        inline=True
    )
    
    # File paths
    embed.add_field(
        name="Data Files",
        value=f"Submissions: `{stats.get('submissions_file', 'N/A')}`\n"
              f"Decisions: `{stats.get('decisions_file', 'N/A')}`",
        inline=False
    )
    
    return embed


