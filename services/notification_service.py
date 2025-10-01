"""
Notification Service

Handles notifications for validation alerts and other system events.
"""
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum
import json

from config import config
from utils.logging_config import get_logger

logger = get_logger(__name__)


class NotificationChannel(Enum):
    """Available notification channels"""
    LOG = "log"
    EMAIL = "email"
    DISCORD = "discord"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class NotificationPriority(Enum):
    """Notification priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationService:
    """Service for sending notifications through various channels"""

    def __init__(self, notification_config: Optional[Dict] = None):
        """
        Initialize notification service

        Args:
            notification_config: Optional configuration dict with channel settings
        """
        self.notification_config = notification_config or {}
        self.enabled_channels = self._get_enabled_channels()
        self._discord_notifier = None

    @property
    def discord_notifier(self):
        """Lazy load Discord notifier"""
        if self._discord_notifier is None and config.discord_notifications_enabled:
            from services.discord_notifier import DiscordNotifier
            self._discord_notifier = DiscordNotifier(config.discord_webhook_url)
        return self._discord_notifier

    def _get_enabled_channels(self) -> List[NotificationChannel]:
        """Get list of enabled notification channels"""
        # For now, always enable logging
        # Additional channels can be enabled via config
        channels = [NotificationChannel.LOG]

        # Enable Discord if configured
        if config.discord_notifications_enabled:
            channels.append(NotificationChannel.DISCORD)

        if self.notification_config.get('email_enabled'):
            channels.append(NotificationChannel.EMAIL)

        if self.notification_config.get('webhook_enabled'):
            channels.append(NotificationChannel.WEBHOOK)

        if self.notification_config.get('in_app_enabled'):
            channels.append(NotificationChannel.IN_APP)

        return channels

    def send_notification(
        self,
        subject: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        channels: Optional[List[NotificationChannel]] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Send notification through specified channels

        Args:
            subject: Notification subject/title
            message: Notification message body
            priority: Priority level
            channels: Specific channels to use (None = use all enabled)
            metadata: Additional metadata for notification

        Returns:
            Dictionary with send results per channel
        """
        if channels is None:
            channels = self.enabled_channels

        results = {}
        timestamp = datetime.utcnow().isoformat()

        for channel in channels:
            try:
                if channel == NotificationChannel.LOG:
                    results[channel.value] = self._send_log_notification(
                        subject, message, priority, timestamp, metadata
                    )
                elif channel == NotificationChannel.EMAIL:
                    results[channel.value] = self._send_email_notification(
                        subject, message, priority, timestamp, metadata
                    )
                elif channel == NotificationChannel.DISCORD:
                    results[channel.value] = self._send_discord_notification(
                        subject, message, priority, timestamp, metadata
                    )
                elif channel == NotificationChannel.WEBHOOK:
                    results[channel.value] = self._send_webhook_notification(
                        subject, message, priority, timestamp, metadata
                    )
                elif channel == NotificationChannel.IN_APP:
                    results[channel.value] = self._send_in_app_notification(
                        subject, message, priority, timestamp, metadata
                    )
            except Exception as e:
                logger.error(f"Error sending notification via {channel.value}: {e}")
                results[channel.value] = {'status': 'error', 'message': str(e)}

        return results

    def _send_log_notification(
        self,
        subject: str,
        message: str,
        priority: NotificationPriority,
        timestamp: str,
        metadata: Optional[Dict]
    ) -> Dict:
        """Send notification via logging"""
        log_message = f"[{priority.value.upper()}] {subject}: {message}"

        if priority == NotificationPriority.CRITICAL:
            logger.critical(log_message)
        elif priority == NotificationPriority.HIGH:
            logger.error(log_message)
        elif priority == NotificationPriority.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)

        if metadata:
            logger.debug(f"Metadata: {json.dumps(metadata, indent=2)}")

        return {'status': 'sent', 'timestamp': timestamp}

    def _send_discord_notification(
        self,
        subject: str,
        message: str,
        priority: NotificationPriority,
        timestamp: str,
        metadata: Optional[Dict]
    ) -> Dict:
        """
        Send notification via Discord webhook
        """
        if not self.discord_notifier:
            return {
                'status': 'skipped',
                'message': 'Discord not configured',
                'timestamp': timestamp
            }

        try:
            from services.discord_notifier import DiscordColor

            # Map priority to Discord color
            color_map = {
                NotificationPriority.CRITICAL: DiscordColor.RED,
                NotificationPriority.HIGH: DiscordColor.YELLOW,
                NotificationPriority.MEDIUM: DiscordColor.BLUE,
                NotificationPriority.LOW: DiscordColor.GRAY
            }

            color = color_map.get(priority, DiscordColor.BLUE)

            # Build fields from metadata
            fields = []
            if metadata:
                for key, value in metadata.items():
                    if isinstance(value, (str, int, float, bool)):
                        fields.append({
                            'name': key.replace('_', ' ').title(),
                            'value': str(value),
                            'inline': True
                        })

            embed = self.discord_notifier.create_embed(
                title=subject,
                description=message,
                color=color,
                fields=fields if fields else None,
                footer="Futures Trading Log",
                timestamp=datetime.fromisoformat(timestamp)
            )

            result = self.discord_notifier.send_message(embeds=[embed])
            return result

        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")
            return {'status': 'error', 'message': str(e), 'timestamp': timestamp}

    def _send_email_notification(
        self,
        subject: str,
        message: str,
        priority: NotificationPriority,
        timestamp: str,
        metadata: Optional[Dict]
    ) -> Dict:
        """
        Send notification via email

        TODO: Implement email sending
        - Configure SMTP settings
        - Use email library (e.g., smtplib, sendgrid)
        - Handle templates
        """
        logger.info(f"Email notification would be sent: {subject}")

        # Placeholder for actual email implementation
        email_config = self.config.get('email', {})
        to_addresses = email_config.get('to_addresses', [])

        if not to_addresses:
            return {
                'status': 'skipped',
                'message': 'No email addresses configured',
                'timestamp': timestamp
            }

        # TODO: Actually send email here
        return {
            'status': 'not_implemented',
            'message': 'Email sending not yet implemented',
            'timestamp': timestamp
        }

    def _send_webhook_notification(
        self,
        subject: str,
        message: str,
        priority: NotificationPriority,
        timestamp: str,
        metadata: Optional[Dict]
    ) -> Dict:
        """
        Send notification via webhook (e.g., Slack, Discord, custom endpoint)

        TODO: Implement webhook posting
        - Configure webhook URLs
        - Use requests library
        - Handle retries
        """
        logger.info(f"Webhook notification would be sent: {subject}")

        webhook_config = self.config.get('webhook', {})
        webhook_url = webhook_config.get('url')

        if not webhook_url:
            return {
                'status': 'skipped',
                'message': 'No webhook URL configured',
                'timestamp': timestamp
            }

        # TODO: Actually post to webhook here
        # import requests
        # payload = {
        #     'subject': subject,
        #     'message': message,
        #     'priority': priority.value,
        #     'timestamp': timestamp,
        #     'metadata': metadata
        # }
        # response = requests.post(webhook_url, json=payload)

        return {
            'status': 'not_implemented',
            'message': 'Webhook posting not yet implemented',
            'timestamp': timestamp
        }

    def _send_in_app_notification(
        self,
        subject: str,
        message: str,
        priority: NotificationPriority,
        timestamp: str,
        metadata: Optional[Dict]
    ) -> Dict:
        """
        Send in-app notification (stored in database for user to see)

        TODO: Implement in-app notifications
        - Create notifications table
        - Store notification
        - Provide API to fetch/mark as read
        """
        logger.info(f"In-app notification would be created: {subject}")

        # TODO: Store in database
        # notification = {
        #     'subject': subject,
        #     'message': message,
        #     'priority': priority.value,
        #     'timestamp': timestamp,
        #     'metadata': metadata,
        #     'read': False
        # }
        # save_to_database(notification)

        return {
            'status': 'not_implemented',
            'message': 'In-app notifications not yet implemented',
            'timestamp': timestamp
        }

    def send_validation_alert(
        self,
        issue_count: int,
        critical_count: int,
        position_ids: List[int],
        details: Optional[Dict] = None
    ) -> Dict:
        """
        Send validation alert notification

        Args:
            issue_count: Total number of issues found
            critical_count: Number of critical issues
            position_ids: List of affected position IDs
            details: Additional details about the validation

        Returns:
            Send results
        """
        priority = NotificationPriority.HIGH if critical_count > 0 else NotificationPriority.MEDIUM

        # Use Discord-specific formatting if Discord is enabled
        if self.discord_notifier:
            try:
                discord_result = self.discord_notifier.send_validation_alert(
                    issue_count=issue_count,
                    critical_count=critical_count,
                    position_count=len(position_ids),
                    details=details or {}
                )
                logger.info(f"Discord validation alert sent: {discord_result}")
            except Exception as e:
                logger.error(f"Failed to send Discord validation alert: {e}")

        # Also send generic notification to other channels
        subject = "Position Validation Alert"

        if critical_count > 0:
            message = (
                f"Found {critical_count} CRITICAL issues and {issue_count} total issues "
                f"across {len(position_ids)} positions."
            )
        else:
            message = f"Found {issue_count} issues across {len(position_ids)} positions."

        metadata = {
            'issue_count': issue_count,
            'critical_count': critical_count,
            'position_ids': position_ids,
            'details': details or {}
        }

        return self.send_notification(
            subject=subject,
            message=message,
            priority=priority,
            metadata=metadata
        )

    def send_repair_summary(
        self,
        total_repaired: int,
        total_failed: int,
        position_ids: List[int],
        details: Optional[Dict] = None
    ) -> Dict:
        """
        Send repair operation summary notification

        Args:
            total_repaired: Number of successfully repaired issues
            total_failed: Number of failed repairs
            position_ids: List of affected position IDs
            details: Additional details about repair operations

        Returns:
            Send results
        """
        # Use Discord-specific formatting if Discord is enabled
        if self.discord_notifier:
            try:
                discord_result = self.discord_notifier.send_repair_summary(
                    total_repaired=total_repaired,
                    total_failed=total_failed,
                    position_count=len(position_ids),
                    details=details or {}
                )
                logger.info(f"Discord repair summary sent: {discord_result}")
            except Exception as e:
                logger.error(f"Failed to send Discord repair summary: {e}")

        # Also send generic notification to other channels
        subject = "Automated Repair Summary"
        message = (
            f"Repair operation completed: {total_repaired} issues repaired, "
            f"{total_failed} failed across {len(position_ids)} positions."
        )

        priority = NotificationPriority.LOW if total_failed == 0 else NotificationPriority.MEDIUM

        metadata = {
            'total_repaired': total_repaired,
            'total_failed': total_failed,
            'position_ids': position_ids,
            'details': details or {}
        }

        return self.send_notification(
            subject=subject,
            message=message,
            priority=priority,
            metadata=metadata
        )