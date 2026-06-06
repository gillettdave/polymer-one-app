"""
Permission checking utilities for the submission bot.
"""
from typing import Optional
import discord
from discord import app_commands


def has_reviewer_role(member: discord.Member, reviewer_role_ids: list[int]) -> bool:
    """Check if a member has any of the reviewer roles."""
    if not reviewer_role_ids:
        return False
    
    member_role_ids = [role.id for role in member.roles]
    return any(role_id in member_role_ids for role_id in reviewer_role_ids)


def has_admin_role(member: discord.Member, admin_role_ids: list[int]) -> bool:
    """Check if a member has any of the admin roles."""
    if not admin_role_ids:
        return False
    
    member_role_ids = [role.id for role in member.roles]
    return any(role_id in member_role_ids for role_id in admin_role_ids)


def can_review(
    member: discord.Member,
    reviewer_role_ids: list[int],
    admin_role_ids: list[int]
) -> bool:
    """
    Check if a member can review submissions.
    Requires either reviewer role, admin role, or manage_guild permission.
    """
    # Check for manage_guild permission (administrator)
    if member.guild_permissions.manage_guild:
        return True
    
    # Check for admin role
    if has_admin_role(member, admin_role_ids):
        return True
    
    # Check for reviewer role
    if has_reviewer_role(member, reviewer_role_ids):
        return True
    
    return False


def can_configure(
    member: discord.Member,
    admin_role_ids: list[int]
) -> bool:
    """
    Check if a member can configure the bot.
    Requires either admin role or manage_guild permission.
    """
    if member.guild_permissions.manage_guild:
        return True
    
    if has_admin_role(member, admin_role_ids):
        return True
    
    return False


async def check_reviewer_permission(
    interaction: discord.Interaction,
    reviewer_role_ids: list[int],
    admin_role_ids: list[int]
) -> bool:
    """Check if the interaction user can review, sending an error if not."""
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True
        )
        return False
    
    if not can_review(interaction.user, reviewer_role_ids, admin_role_ids):
        await interaction.response.send_message(
            "You don't have permission to review submissions.",
            ephemeral=True
        )
        return False
    
    return True


async def check_admin_permission(
    interaction: discord.Interaction,
    admin_role_ids: list[int]
) -> bool:
    """Check if the interaction user can configure the bot, sending an error if not."""
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            "This command can only be used in a server.",
            ephemeral=True
        )
        return False
    
    if not can_configure(interaction.user, admin_role_ids):
        await interaction.response.send_message(
            "You don't have permission to configure the bot.",
            ephemeral=True
        )
        return False
    
    return True


def is_role_allowlisted(role_id: int, allowlisted_role_ids: list[int]) -> bool:
    """Check if a role ID is in the allowlist for assignment."""
    return role_id in allowlisted_role_ids


