# Discord Notifications Setup Guide

This guide explains how to configure Discord webhook notifications for the Futures Trading Log application's position validation and automated repair system.

## Overview

The Discord notification system provides real-time alerts for:
- **Validation Issues**: When position-execution integrity problems are detected
- **Repair Summaries**: Results of automated repair operations
- **Critical Alerts**: High-priority issues requiring immediate attention

All notifications use rich Discord embeds with color-coding, emojis, and structured fields for better readability.

## Prerequisites

- A Discord server where you have "Manage Webhooks" permission
- Discord desktop or web application access

## Step 1: Create Discord Webhook

1. **Open Server Settings**
   - Navigate to your Discord server
   - Click the server name dropdown → "Server Settings"

2. **Create Webhook**
   - Go to "Integrations" section
   - Click "Webhooks" → "New Webhook"
   - Name it (e.g., "Trading Log Alerts")
   - Select the channel where notifications should appear
   - Click "Copy Webhook URL"

3. **Save Webhook URL**
   - The URL format will be: `https://discord.com/api/webhooks/{id}/{token}`
   - Keep this URL secure - anyone with it can post to your channel

## Step 2: Configure Application

### Option A: Environment Variable (Recommended)

Add to your `.env` file:
```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
```

### Option B: Docker Environment

For Docker deployments, add to `docker-compose.yml`:
```yaml
services:
  app:
    environment:
      - DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
```

### Option C: System Environment Variable

**Linux/Mac:**
```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
```

**Windows (PowerShell):**
```powershell
$env:DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
```

**Windows (Command Prompt):**
```cmd
set DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
```

## Step 3: Test Configuration

Run the test script to verify your webhook is working:

```bash
python scripts/test_discord_webhook.py
```

Expected output:
```
Testing Discord webhook configuration...
Discord webhook URL: https://discord.com/api/webhooks/****/****

Sending test notification 1/4...
✓ Successfully sent: Basic notification test

Sending test notification 2/4...
✓ Successfully sent: Validation alert test

Sending test notification 3/4...
✓ Successfully sent: Repair summary test

Sending test notification 4/4...
✓ Successfully sent: Critical issue test

All tests passed! Discord notifications are working correctly.
```

You should see 4 test messages appear in your Discord channel.

## Step 4: Restart Application

After configuring the webhook URL, restart your application:

```bash
# If running locally
python app.py

# If using Docker
docker-compose restart

# If using Celery workers (for background jobs)
celery -A celery_app worker --loglevel=info
```

## Notification Types

### 1. Validation Alerts

Triggered when position validation detects integrity issues.

**Example Discord Message:**
```
🔍 Position Validation Alert
⚠️ MEDIUM - Position Validation Issues Detected

📊 Found 5 issues across 3 positions

Details:
• Total Issues: 5
• Critical Issues: 0
• Positions Affected: 3
• Position IDs: 101, 102, 105
```

**Color Coding:**
- 🔴 Red: Critical issues detected (requires immediate attention)
- 🟡 Yellow: Non-critical issues detected

### 2. Repair Summaries

Triggered after automated repair operations complete.

**Example Discord Message:**
```
🔧 Automated Repair Summary
✅ LOW - Repair Operation Completed

📊 Successfully repaired 3 issues across 2 positions

Details:
• Repaired: 3
• Failed: 0
• Positions Affected: 2
• Position IDs: 101, 102
• Success Rate: 100.0%
```

**Color Coding:**
- 🟢 Green: All repairs successful
- 🟡 Yellow: Some repairs failed

## Triggering Notifications

### Manual Validation

```bash
# Validate single position
curl -X POST http://localhost:5000/api/validation/positions/123/validate

# Validate all positions
curl -X POST http://localhost:5000/api/validation/jobs/validate \
  -H "Content-Type: application/json" \
  -d '{"auto_repair": true}'
```

### Automated Background Jobs

Background jobs automatically trigger notifications:

1. **Daily Full Validation** (3:00 AM)
   - Validates all positions from last 7 days
   - Auto-repairs issues when possible
   - Sends summary to Discord

2. **Recent Position Checks** (Every 30 minutes)
   - Validates positions modified in last 2 hours
   - Auto-repairs issues when possible
   - Sends alerts only if issues found

### Programmatic Usage

```python
from services.notification_service import NotificationService

# Initialize service
notifier = NotificationService()

# Send validation alert
notifier.send_validation_alert(
    issue_count=5,
    critical_count=2,
    position_ids=[101, 102, 105],
    details={
        'issue_types': ['QUANTITY_MISMATCH', 'TIMESTAMP_ANOMALY'],
        'validation_time': '2025-09-29T10:30:00Z'
    }
)

# Send repair summary
notifier.send_repair_summary(
    total_repaired=3,
    total_failed=1,
    position_ids=[101, 102],
    details={
        'repair_methods': ['FIFO_RECONCILIATION', 'TIMESTAMP_CORRECTION'],
        'repair_time': '2025-09-29T10:35:00Z'
    }
)
```

## Troubleshooting

### No Notifications Appearing

1. **Verify webhook URL is set:**
   ```python
   python -c "from config.config import config; print(f'Webhook URL: {config.discord_webhook_url[:50]}...')"
   ```

2. **Check if Discord is enabled:**
   ```python
   python -c "from config.config import config; print(f'Discord enabled: {config.discord_notifications_enabled}')"
   ```

3. **Test webhook manually:**
   ```bash
   python scripts/test_discord_webhook.py
   ```

4. **Check application logs:**
   ```bash
   # Look for Discord-related errors
   grep -i "discord" data/logs/app.log
   ```

### Webhook URL Invalid

**Error:** `Invalid webhook URL`

**Solution:** Ensure URL format is correct:
- Must start with `https://discord.com/api/webhooks/`
- Must contain webhook ID and token
- Example: `https://discord.com/api/webhooks/123456789/abcdef123456`

### Rate Limiting

**Error:** `Rate limited by Discord`

**Solution:** Discord webhooks have rate limits:
- 30 requests per minute per webhook
- 5 requests per second per webhook

If you hit these limits, the application will automatically retry after a delay.

### Permission Denied

**Error:** `Webhook not found or permission denied`

**Solution:**
- Verify the webhook still exists in Discord
- Check that the channel hasn't been deleted
- Ensure webhook hasn't been removed from server settings
- Create a new webhook if needed

## Configuration Options

### Enable/Disable Discord Notifications

Discord notifications are automatically enabled when `DISCORD_WEBHOOK_URL` is set. To disable:

```bash
# Remove or comment out the environment variable
# DISCORD_WEBHOOK_URL=...
```

### Custom Notification Channels

You can create multiple webhooks for different notification types:

```bash
# Critical alerts only
DISCORD_WEBHOOK_URL_CRITICAL=https://discord.com/api/webhooks/.../...

# All notifications
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/.../...
```

Then modify `config.py` to support multiple webhook URLs.

### Notification Frequency

Background job schedules can be adjusted in `celery_app.py`:

```python
# Validate all positions daily at 3 AM
'validate-all-positions': {
    'task': 'tasks.validation_tasks.validate_all_positions_task',
    'schedule': crontab(minute=0, hour=3),  # Adjust time here
    'args': (None, 7, True),
}

# Validate recent positions every 30 minutes
'validate-recent-positions': {
    'task': 'tasks.validation_tasks.validate_recent_positions_task',
    'schedule': crontab(minute='*/30'),  # Adjust frequency here
    'args': (2, True),
}
```

## Security Considerations

1. **Keep Webhook URL Secret**
   - Don't commit webhook URLs to version control
   - Use `.env` files (add to `.gitignore`)
   - Rotate webhooks if compromised

2. **Limit Channel Access**
   - Only authorized users should see notification channel
   - Use Discord permissions to restrict access
   - Consider private channels for sensitive alerts

3. **Webhook Validation**
   - Application validates webhook URL format
   - Failed requests are logged but don't expose URL
   - Rate limiting prevents abuse

## Additional Resources

- [Discord Webhooks Documentation](https://discord.com/developers/docs/resources/webhook)
- [Celery Beat Scheduling](https://docs.celeryproject.org/en/stable/userguide/periodic-tasks.html)
- [NotificationService API Reference](../services/notification_service.py)
- [DiscordNotifier Implementation](../services/discord_notifier.py)

## Support

For issues or questions:
1. Check application logs: `data/logs/app.log`
2. Run test script: `python scripts/test_discord_webhook.py`
3. Review this documentation
4. Check Discord webhook status in server settings