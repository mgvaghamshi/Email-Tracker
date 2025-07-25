# EmailTracker API Documentation

## Overview

EmailTracker API is a professional email sending and tracking service designed to provide enterprise-grade email infrastructure similar to Mailgun. It offers comprehensive email delivery, tracking, analytics, and management capabilities.

## Key Features

### 🚀 Email Sending
- **Single Email Sending**: Send individual emails with full tracking
- **Bulk Email Campaigns**: Send up to 1,000 emails per request
- **Scheduled Delivery**: Schedule emails for future delivery
- **Template Support**: HTML and plain text email content
- **Campaign Management**: Group emails into campaigns for analytics

### 📊 Real-time Tracking
- **Open Tracking**: Invisible pixel tracking with bot detection
- **Click Tracking**: Track all link clicks with redirect
- **Bounce Detection**: Handle hard and soft bounces
- **Unsubscribe Management**: Automatic unsubscribe handling
- **Delivery Confirmation**: Real-time delivery status updates

### 📈 Analytics & Reporting
- **Campaign Analytics**: Comprehensive engagement metrics
- **Deliverability Stats**: Overall delivery performance
- **Engagement Insights**: Device, client, and geographic breakdowns
- **Top Performing Links**: Click performance analysis
- **Time-based Analytics**: Hourly engagement patterns

### 🔐 Security & Authentication
- **API Key Management**: Secure token-based authentication
- **Rate Limiting**: Configurable per-key rate limits
- **Bot Detection**: Intelligent filtering of automated traffic
- **Webhook Signatures**: Secure webhook delivery verification

### 🔔 Webhooks
- **Real-time Events**: Instant notifications for email events
- **Automatic Retries**: Reliable delivery with exponential backoff
- **Event Types**: Opens, clicks, bounces, complaints, deliveries
- **Signature Verification**: Secure webhook payload validation

## Quick Start

### 1. Create an API Key

```bash
curl -X POST "https://api.emailtracker.com/api/v1/auth/api-keys" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "My First API Key",
       "requests_per_minute": 100,
       "requests_per_day": 10000
     }'
```

### 2. Send Your First Email

```bash
curl -X POST "https://api.emailtracker.com/api/v1/emails/send" \
     -H "Authorization: Bearer your_api_key" \
     -H "Content-Type: application/json" \
     -d '{
       "to_email": "recipient@example.com",
       "from_email": "sender@yourcompany.com",
       "from_name": "Your Company",
       "subject": "Welcome to our service!",
       "html_content": "<h1>Welcome!</h1><p>Thank you for signing up.</p>",
       "text_content": "Welcome! Thank you for signing up."
     }'
```

### 3. Check Campaign Analytics

```bash
curl -H "Authorization: Bearer your_api_key" \
     "https://api.emailtracker.com/api/v1/analytics/campaigns/your_campaign_id"
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/api-keys` - Create API key
- `GET /api/v1/auth/api-keys` - List API keys
- `PATCH /api/v1/auth/api-keys/{key_id}` - Update API key
- `DELETE /api/v1/auth/api-keys/{key_id}` - Revoke API key

### Email Sending
- `POST /api/v1/emails/send` - Send single email
- `POST /api/v1/emails/send-bulk` - Send bulk emails
- `GET /api/v1/emails/trackers` - List email trackers
- `GET /api/v1/emails/trackers/{tracker_id}` - Get tracker details

### Tracking
- `GET /api/v1/track/open/{tracker_id}` - Track email open (automatic)
- `GET /api/v1/track/click/{tracker_id}` - Track link click (automatic)
- `GET /api/v1/track/events/{tracker_id}` - Get tracking events
- `GET /api/v1/track/clicks/{tracker_id}` - Get click events

### Analytics
- `GET /api/v1/analytics/campaigns/{campaign_id}` - Campaign analytics
- `GET /api/v1/analytics/deliverability` - Deliverability stats
- `GET /api/v1/analytics/campaigns/{campaign_id}/engagement` - Engagement analytics
- `GET /api/v1/analytics/campaigns/{campaign_id}/top-links` - Top performing links

### Webhooks
- `POST /api/v1/webhooks/events/send` - Send webhook event
- `GET /api/v1/webhooks/events` - List webhook events
- `POST /api/v1/webhooks/test` - Test webhook endpoint

## Rate Limits

Rate limits are enforced per API key:
- **Default**: 100 requests per minute, 10,000 per day
- **Configurable**: Set custom limits per API key
- **Headers**: Rate limit info returned in response headers
- **HTTP 429**: Returned when rate limit exceeded

## Authentication

All API requests require authentication using API keys:

```bash
Authorization: Bearer your_api_key_here
```

## Error Handling

The API returns standard HTTP status codes:

- **200**: Success
- **201**: Created
- **202**: Accepted (for asynchronous operations)
- **400**: Bad Request
- **401**: Unauthorized
- **404**: Not Found
- **429**: Rate Limit Exceeded
- **500**: Internal Server Error

Error responses include detailed information:

```json
{
  "error": {
    "code": 400,
    "message": "Invalid email address",
    "type": "validation_error",
    "timestamp": 1706198400.123,
    "path": "/api/v1/emails/send"
  }
}
```

## Webhook Events

Webhooks are sent for the following events:

- **email.sent**: Email was successfully sent
- **email.delivered**: Email was delivered to recipient
- **email.opened**: Email was opened by recipient
- **email.clicked**: Link in email was clicked
- **email.bounced**: Email bounced (hard or soft)
- **email.complained**: Recipient marked email as spam
- **email.unsubscribed**: Recipient unsubscribed

## Best Practices

### Email Sending
1. **Include both HTML and text content** for better deliverability
2. **Use descriptive campaign IDs** for better analytics
3. **Batch large sends** into smaller chunks (100-500 emails)
4. **Monitor deliverability stats** regularly

### Tracking
1. **Review bot detection settings** if open rates seem low
2. **Use unique campaign IDs** for accurate analytics
3. **Monitor click patterns** to optimize content

### API Usage
1. **Store API keys securely** and rotate regularly
2. **Implement proper error handling** for all requests
3. **Use webhooks** for real-time event processing
4. **Monitor rate limits** to avoid throttling

## Support

- **Documentation**: https://docs.emailtracker.com
- **API Reference**: https://api.emailtracker.com/docs
- **Status Page**: https://status.emailtracker.com
- **Support Email**: support@emailtracker.com

## SDKs and Libraries

Official SDKs available for:
- **Node.js**: `npm install emailtracker-js`
- **Python**: `pip install emailtracker-python`
- **PHP**: `composer require emailtracker/php-sdk`
- **Ruby**: `gem install emailtracker-ruby`

## Changelog

### v1.0.0 (2025-01-25)
- Initial release
- Email sending and tracking
- Analytics and reporting
- API key management
- Webhook support
- Bot detection
