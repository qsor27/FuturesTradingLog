"""
Discord Webhook Notifier

Sends formatted notifications to Discord channels via webhooks.
"""
import requests
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum

from utils.logging_config import get_logger

logger = get_logger(__name__)


class DiscordColor(Enum):
    """Discord embed colors"""
    BLUE = 0x3498db      # Info
    GREEN = 0x2ecc71     # Success
    YELLOW = 0xf39c12    # Warning
    RED = 0xe74c3c       # Error
    PURPLE = 0x9b59b6    # Critical
    GRAY = 0x95a5a6      # Neutral


class DiscordNotifier:
    """Discord webhook notification client"""

    def __init__(self, webhook_url: str):
        """
        Initialize Discord notifier

        Args:
            webhook_url: Discord webhook URL
        """
        self.webhook_url = webhook_url
        self.timeout = 10  # seconds

    def send_message(
        self,
        content: Optional[str] = None,
        embeds: Optional[List[Dict]] = None,
        username: Optional[str] = None
    ) -> Dict:
        """
        Send message to Discord webhook

        Args:
            content: Plain text message content
            embeds: List of embed objects
            username: Override webhook username

        Returns:
            Dictionary with send result
        """
        try:
            payload = {}

            if content:
                payload['content'] = content

            if embeds:
                payload['embeds'] = embeds

            if username:
                payload['username'] = username

            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 204:
                logger.info("Discord notification sent successfully")
                return {'status': 'sent', 'code': 204}
            else:
                logger.warning(f"Discord API returned status {response.status_code}: {response.text}")
                return {
                    'status': 'error',
                    'code': response.status_code,
                    'message': response.text
                }

        except requests.exceptions.Timeout:
            logger.error("Discord webhook request timed out")
            return {'status': 'timeout', 'message': 'Request timed out'}

        except requests.exceptions.RequestException as e:
            logger.error(f"Discord webhook request failed: {e}")
            return {'status': 'error', 'message': str(e)}

    def create_embed(
        self,
        title: str,
        description: str,
        color: DiscordColor = DiscordColor.BLUE,
        fields: Optional[List[Dict]] = None,
        footer: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> Dict:
        """
        Create Discord embed object

        Args:
            title: Embed title
            description: Embed description
            color: Embed color
            fields: List of field objects with 'name', 'value', 'inline'
            footer: Footer text
            timestamp: Timestamp for embed

        Returns:
            Discord embed dictionary
        """
        embed = {
            'title': title,
            'description': description,
            'color': color.value
        }

        if fields:
            embed['fields'] = fields

        if footer:
            embed['footer'] = {'text': footer}

        if timestamp:
            embed['timestamp'] = timestamp.isoformat()

        return embed

    def send_validation_alert(
        self,
        issue_count: int,
        critical_count: int,
        position_count: int,
        details: Optional[Dict] = None
    ) -> Dict:
        """
        Send validation alert to Discord

        Args:
            issue_count: Total issues found
            critical_count: Critical issues found
            position_count: Number of affected positions
            details: Additional details

        Returns:
            Send result
        """
        # Determine color and priority
        if critical_count > 0:
            color = DiscordColor.RED
            priority = "🚨 CRITICAL"
        elif issue_count > 20:
            color = DiscordColor.YELLOW
            priority = "⚠️ HIGH"
        else:
            color = DiscordColor.YELLOW
            priority = "⚠️ MEDIUM"

        # Build description
        description = f"**{priority} - Position Validation Issues Detected**\n\n"

        if critical_count > 0:
            description += f"🔴 **{critical_count}** critical issues require immediate attention\n"

        description += f"📊 **{issue_count}** total issues found across **{position_count}** positions"

        # Build fields
        fields = []

        if details:
            if 'passed' in details:
                fields.append({
                    'name': '✅ Passed',
                    'value': str(details['passed']),
                    'inline': True
                })

            if 'failed' in details:
                fields.append({
                    'name': '❌ Failed',
                    'value': str(details['failed']),
                    'inline': True
                })

            if 'repaired' in details:
                fields.append({
                    'name': '🔧 Auto-Repaired',
                    'value': str(details['repaired']),
                    'inline': True
                })

        # Add issue breakdown
        if critical_count > 0:
            fields.append({
                'name': '🚨 Critical Issues',
                'value': f"{critical_count} require immediate review",
                'inline': False
            })

        # Create embed
        embed = self.create_embed(
            title="Position Validation Alert",
            description=description,
            color=color,
            fields=fields,
            footer="Futures Trading Log - Automated Validation",
            timestamp=datetime.utcnow()
        )

        return self.send_message(embeds=[embed])

    def send_repair_summary(
        self,
        repaired: int,
        failed: int,
        position_count: int
    ) -> Dict:
        """
        Send repair summary to Discord

        Args:
            repaired: Successfully repaired issues
            failed: Failed repairs
            position_count: Number of positions affected

        Returns:
            Send result
        """
        # Determine color
        if failed == 0:
            color = DiscordColor.GREEN
        elif failed > repaired:
            color = DiscordColor.YELLOW
        else:
            color = DiscordColor.BLUE

        description = "**Automated Repair Summary**\n\n"
        description += f"🔧 Successfully repaired **{repaired}** issues\n"

        if failed > 0:
            description += f"❌ Failed to repair **{failed}** issues\n"

        description += f"\n📊 Affected **{position_count}** positions"

        # Build fields
        fields = [
            {
                'name': '✅ Successful Repairs',
                'value': str(repaired),
                'inline': True
            },
            {
                'name': '❌ Failed Repairs',
                'value': str(failed),
                'inline': True
            },
            {
                'name': '📈 Success Rate',
                'value': f"{(repaired / (repaired + failed) * 100):.1f}%" if (repaired + failed) > 0 else "N/A",
                'inline': True
            }
        ]

        embed = self.create_embed(
            title="Automated Repair Complete",
            description=description,
            color=color,
            fields=fields,
            footer="Futures Trading Log - Auto-Repair",
            timestamp=datetime.utcnow()
        )

        return self.send_message(embeds=[embed])

    def send_validation_summary(
        self,
        total_positions: int,
        validated: int,
        passed: int,
        failed: int,
        issues_found: int,
        critical_issues: int
    ) -> Dict:
        """
        Send validation batch summary to Discord

        Args:
            total_positions: Total positions to validate
            validated: Positions successfully validated
            passed: Positions that passed validation
            failed: Positions that failed validation
            issues_found: Total issues found
            critical_issues: Critical issues found

        Returns:
            Send result
        """
        # Determine color
        if critical_issues > 0:
            color = DiscordColor.RED
        elif failed > 0:
            color = DiscordColor.YELLOW
        else:
            color = DiscordColor.GREEN

        description = "**Batch Validation Complete**\n\n"
        description += f"Validated **{validated}** of **{total_positions}** positions"

        # Build fields
        fields = [
            {
                'name': '✅ Passed',
                'value': f"{passed} ({(passed/validated*100):.1f}%)" if validated > 0 else "0",
                'inline': True
            },
            {
                'name': '❌ Failed',
                'value': f"{failed} ({(failed/validated*100):.1f}%)" if validated > 0 else "0",
                'inline': True
            },
            {
                'name': '📊 Issues Found',
                'value': str(issues_found),
                'inline': True
            }
        ]

        if critical_issues > 0:
            fields.append({
                'name': '🚨 Critical Issues',
                'value': f"{critical_issues} require attention",
                'inline': False
            })

        embed = self.create_embed(
            title="Validation Summary",
            description=description,
            color=color,
            fields=fields,
            footer="Futures Trading Log - Batch Validation",
            timestamp=datetime.utcnow()
        )

        return self.send_message(embeds=[embed])

    def send_test_notification(self) -> Dict:
        """
        Send test notification to verify webhook

        Returns:
            Send result
        """
        embed = self.create_embed(
            title="✅ Discord Integration Test",
            description="Discord webhook is configured correctly and working!",
            color=DiscordColor.GREEN,
            fields=[
                {
                    'name': '🔔 Notifications Enabled',
                    'value': 'You will receive validation alerts and repair summaries',
                    'inline': False
                }
            ],
            footer="Futures Trading Log",
            timestamp=datetime.utcnow()
        )

        return self.send_message(embeds=[embed])