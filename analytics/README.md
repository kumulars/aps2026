# APS 2026 Analytics System

A comprehensive, error-resilient analytics system built specifically for the American Peptide Society 2026 website. This system provides detailed insights into user behavior, content performance, and system health with automatic weekly reporting.

## Features

### 🚀 **Zero-Configuration Tracking (Stage 1)**
- Automatic page view tracking
- Search query monitoring
- Error detection and reporting
- Performance metrics collection
- Bot filtering
- Session analysis

### 📊 **Comprehensive Dashboard (Stage 2)**
- Real-time metrics display
- Interactive charts and graphs
- Top pages and searches
- System health monitoring
- Data export capabilities
- Date range filtering

### 🔧 **Error-Resilient Design**
- Analytics never affects site performance
- Comprehensive error handling and recovery
- Automatic data validation and repair
- Built-in debugging tools
- Rollback capabilities

### 📧 **Automated Reporting (Stage 2)**
- Weekly email reports with insights
- Comparison with previous periods
- Key metrics and trends
- System health alerts
- Customizable recipients

### 🎯 **Advanced Analytics (Stage 3)**
- **User Journey Mapping**: Track complete user paths through your site
- **A/B Testing Framework**: Built-in A/B testing with statistical analysis
- **Custom Event Tracking**: JavaScript SDK for tracking any user interaction
- **Conversion Funnels**: Define and analyze conversion paths
- **Advanced Dashboards**: Sophisticated visualizations and insights
- **User Segmentation**: Group users for targeted analysis

## Architecture

```
analytics/
├── models.py              # Data models with error handling
├── middleware.py          # Automatic event tracking
├── utils.py              # Helper functions and bot detection
├── wagtail_hooks.py      # Admin dashboard integration
├── management/commands/
│   ├── debug_analytics.py    # Debugging and troubleshooting
│   └── send_weekly_report.py # Report generation and email
└── templates/analytics/
    └── dashboard.html        # Admin dashboard interface
```

## Data Models

### AnalyticsEvent
- **Core tracking model** with comprehensive error handling
- Tracks page views, searches, clicks, form submissions, downloads, errors
- Includes user identification, session tracking, performance metrics
- Built-in retry logic and failure tracking

### DailySummary
- **Pre-aggregated daily statistics** for performance
- Traffic metrics, engagement data, content performance
- Error tracking and processing status

### WeeklyReport
- **Automated report generation** with email delivery
- Week-over-week comparisons and insights
- Report status tracking and error handling

### AnalyticsConfiguration
- **Centralized settings management**
- Feature flags for different tracking types
- Data retention policies
- Email settings and bot detection rules
- Debug and performance settings

## Quick Start

### 1. Installation
The system is already installed and configured in your project. Analytics tracking starts automatically when you access any page.

### 2. Access Dashboard
1. Log into Wagtail admin: `/admin/`
2. Click "Analytics" in the left menu
3. View real-time dashboard with metrics and charts

### 3. Configuration
```bash
# Access settings through admin or directly:
python manage.py shell
>>> from analytics.models import AnalyticsConfiguration
>>> config = AnalyticsConfiguration.get_config()
>>> config.enabled = True  # Enable/disable analytics
>>> config.send_weekly_reports = True  # Enable email reports
>>> config.report_recipients = ['admin@example.com']  # Set recipients
>>> config.save()
```

### 4. Weekly Reports
```bash
# Generate and send weekly report
python manage.py send_weekly_report

# Test report generation (no email sent)
python manage.py send_weekly_report --dry-run

# Send to specific email for testing
python manage.py send_weekly_report --email your@email.com
```

## Management Commands

### Debug and Troubleshooting
```bash
# Run system health checks
python manage.py debug_analytics --check

# View recent events
python manage.py debug_analytics --recent 20

# Show error logs
python manage.py debug_analytics --errors

# Show statistics
python manage.py debug_analytics --stats

# Validate data integrity
python manage.py debug_analytics --validate

# Create test event for debugging
python manage.py debug_analytics --test-event

# Clear test data
python manage.py debug_analytics --clear-test
```

### Weekly Reports
```bash
# Generate current week report
python manage.py send_weekly_report

# Generate specific week
python manage.py send_weekly_report --week-start 2024-01-01

# Dry run (no email)
python manage.py send_weekly_report --dry-run

# Force regenerate existing report
python manage.py send_weekly_report --force

# Send to test email
python manage.py send_weekly_report --email test@example.com
```

## Dashboard Features

### Metrics Overview
- **Page Views**: Total page views with trend analysis
- **Unique Visitors**: Distinct session tracking
- **Searches**: Query analysis and popular terms
- **Errors**: Error rate and recent issues

### Interactive Charts
- **Traffic Trends**: Daily page views, visitors, and searches
- **Performance Metrics**: Load times and error rates
- **Content Analysis**: Top performing pages

### System Health
- **Real-time Status**: Analytics system health indicators
- **Error Monitoring**: Failed events and processing issues
- **Debug Information**: Detailed troubleshooting data

## Configuration Options

### Feature Flags
```python
# In Django admin or shell:
config = AnalyticsConfiguration.get_config()

# Master controls
config.enabled = True                    # Enable/disable all analytics
config.track_page_views = True          # Track page visits
config.track_searches = True            # Track search queries
config.track_errors = True              # Track error events
config.track_downloads = True           # Track file downloads

# Performance settings
config.sampling_rate = 1.0              # Sample rate (0.0-1.0)
config.max_events_per_minute = 1000     # Rate limiting

# Data retention
config.raw_event_retention_days = 30    # Raw events retention
config.daily_summary_retention_days = 365  # Daily summaries retention

# Email settings
config.send_weekly_reports = True       # Enable weekly emails
config.report_recipients = [            # Email addresses
    'admin@americanpeptidesociety.org',
    'analytics@americanpeptidesociety.org'
]

# Debug settings
config.debug_mode = False               # Enable verbose logging
config.test_mode = False                # Mark events as test data

config.save()
```

## Error Handling & Recovery

### Built-in Safety Features
1. **Analytics Isolation**: Analytics errors never affect the main site
2. **Graceful Degradation**: System continues if analytics fails
3. **Automatic Recovery**: Failed events can be retried
4. **Data Validation**: Integrity checks and repair tools
5. **Debug Logging**: Comprehensive error tracking

### Common Issues & Solutions

#### Analytics Not Tracking
```bash
# Check system status
python manage.py debug_analytics --check

# Verify configuration
python manage.py shell
>>> from analytics.models import AnalyticsConfiguration
>>> config = AnalyticsConfiguration.get_config()
>>> print(f"Enabled: {config.enabled}")

# Check middleware is installed
# Look for 'analytics.middleware.AnalyticsMiddleware' in settings.MIDDLEWARE
```

#### High Error Rate
```bash
# Check recent errors
python manage.py debug_analytics --errors

# View failed events
python manage.py shell
>>> from analytics.models import AnalyticsEvent
>>> failed = AnalyticsEvent.objects.filter(processing_status='failed')
>>> for event in failed[:5]:
...     print(f"{event.timestamp}: {event.last_error}")
```

#### Missing Data
```bash
# Validate data integrity
python manage.py debug_analytics --validate

# Check for gaps in daily summaries
python manage.py shell
>>> from analytics.models import DailySummary
>>> summaries = DailySummary.objects.all().order_by('date')
>>> for summary in summaries:
...     print(f"{summary.date}: {summary.total_page_views} views")
```

### Emergency Procedures

#### Disable Analytics
```bash
# Quick disable via management command
python manage.py shell
>>> from analytics.models import AnalyticsConfiguration
>>> config = AnalyticsConfiguration.get_config()
>>> config.enabled = False
>>> config.save()
>>> print("Analytics disabled")

# Or remove from middleware in settings.py
```

#### Clear All Data
```bash
python manage.py shell
>>> from analytics.models import AnalyticsEvent, DailySummary, WeeklyReport
>>> AnalyticsEvent.objects.all().delete()
>>> DailySummary.objects.all().delete()
>>> WeeklyReport.objects.all().delete()
>>> print("All analytics data cleared")
```

## Performance Considerations

### Database Optimization
- **Proper Indexing**: All models include optimized database indexes
- **Data Archival**: Automatic cleanup of old events
- **Query Optimization**: Efficient queries for dashboard and reports
- **Batch Processing**: Events processed in batches for performance

### Monitoring
- **Rate Limiting**: Prevents analytics from overwhelming the system
- **Sampling**: Can reduce tracking for high-traffic scenarios
- **Bot Filtering**: Automatic detection and filtering of bot traffic
- **Error Tracking**: Comprehensive monitoring of system health

## Development & Testing

### Adding Custom Events
```python
# In your views or middleware
from analytics.models import AnalyticsEvent

def track_custom_event(request, event_type, data):
    try:
        AnalyticsEvent.objects.create(
            event_type=event_type,
            user=request.user if request.user.is_authenticated else None,
            session_id=request.session.get('analytics_session_id', ''),
            page_url=request.build_absolute_uri(),
            event_data=data,
            processing_status='processed'
        )
    except Exception as e:
        # Handle error gracefully
        pass
```

### Testing
```bash
# Create test data
python manage.py debug_analytics --test-event

# Run system checks
python manage.py debug_analytics --check

# Test report generation
python manage.py send_weekly_report --dry-run

# Clear test data
python manage.py debug_analytics --clear-test
```

## Security & Privacy

### Data Protection
- **IP Address Hashing**: IP addresses can be hashed for privacy
- **Sensitive Parameter Filtering**: Automatic removal of passwords, tokens
- **User Data Anonymization**: Optional anonymization of user data
- **GDPR Compliance**: Data retention policies and deletion capabilities

### Bot Protection
- **Automatic Detection**: Comprehensive bot identification
- **User Agent Filtering**: Configurable bot patterns
- **Rate Limiting**: Protection against abuse
- **Validation**: Data integrity checks

## Production Deployment

### Scheduled Tasks
Add to your cron configuration:
```bash
# Send weekly reports every Monday at 9 AM
0 9 * * 1 /path/to/your/project/manage.py send_weekly_report

# Clean up old debug logs daily at 2 AM
0 2 * * * /path/to/your/project/manage.py debug_analytics --cleanup
```

### Email Configuration
Ensure your Django email settings are configured:
```python
# In settings.py
EMAIL_HOST = 'your-smtp-host'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@domain.com'
EMAIL_HOST_PASSWORD = 'your-password'
DEFAULT_FROM_EMAIL = 'APS Analytics <analytics@americanpeptidesociety.org>'
```

### Monitoring
Set up monitoring for:
- Analytics system health
- Error rates and failed events
- Report generation success
- Email delivery status

## Support & Troubleshooting

For issues or questions about the analytics system:

1. **Check System Status**: `python manage.py debug_analytics --check`
2. **Review Error Logs**: `python manage.py debug_analytics --errors`
3. **Validate Data**: `python manage.py debug_analytics --validate`
4. **Test Components**: Use debug commands to isolate issues

The analytics system is designed to be self-healing and provides comprehensive debugging tools to identify and resolve issues quickly.

## Stage 3: Advanced Analytics Features

### JavaScript SDK Usage

The APS Analytics SDK is automatically loaded on all pages and provides advanced tracking capabilities:

```javascript
// Track custom events
APS.Analytics.track('button_click', {
    button_name: 'subscribe_newsletter',
    location: 'header'
});

// Track conversion goals
APS.Analytics.goal('newsletter_signup', 10.0, {
    campaign: 'homepage_banner'
});

// Get A/B test variant
const variant = APS.Analytics.getABTestVariant('homepage_hero');
if (variant === 'variant_a') {
    // Show variant A
} else {
    // Show control
}

// Mark A/B test conversion
APS.Analytics.abTestConversion('homepage_hero', 'signup');

// Identify users
APS.Analytics.identifyUser(userId, {
    username: 'john_doe',
    member_tier: 'premium'
});

// Track performance
APS.Analytics.trackTiming('api_call', 'search_researchers', 1250);

// Track errors
APS.Analytics.trackError(new Error('Custom error'), {
    context: 'form_submission'
});
```

### User Journey Analysis

Access user journey data through the advanced dashboard:

1. **Go to**: `/admin/analytics/advanced/`
2. **Select**: "User Journeys" tab
3. **View**: Complete user paths, entry/exit points, conversion tracking

**API Access**:
```javascript
// Get journey data
fetch('/api/analytics/journeys/?days=30')
    .then(response => response.json())
    .then(data => {
        console.log('Journey metrics:', data.metrics);
        console.log('Common paths:', data.common_paths);
    });
```

### A/B Testing

#### Creating A/B Tests

```python
from analytics.models_advanced import ABTest

# Create test
test = ABTest.objects.create(
    name='peptide_search_layout',
    description='Testing search interface layouts',
    is_active=True,
    variants={
        'control': {'layout': 'table'},
        'variant_a': {'layout': 'cards'},
        'variant_b': {'layout': 'list'}
    },
    primary_goal='researcher_profile_click',
    secondary_goals=['search_refinement', 'export_results']
)
```

#### Frontend Implementation

```javascript
// Get variant assignment
const variant = APS.Analytics.getABTestVariant('peptide_search_layout');

// Apply variant
if (variant === 'variant_a') {
    showCardLayout();
} else if (variant === 'variant_b') {
    showListLayout();
} else {
    showTableLayout(); // control
}

// Track conversion when user clicks researcher profile
document.addEventListener('click', function(e) {
    if (e.target.closest('.researcher-profile-link')) {
        APS.Analytics.abTestConversion('peptide_search_layout', 'researcher_profile_click');
    }
});
```

#### View Results

1. **Dashboard**: `/admin/analytics/advanced/` → A/B Tests tab
2. **API**: `/api/analytics/ab-test/peptide_search_layout/results/`

### Custom Event Tracking

The SDK automatically tracks many interactions, but you can add custom tracking:

```javascript
// Track specific interactions
document.getElementById('export-button').addEventListener('click', function() {
    APS.Analytics.track('data_export', {
        export_type: 'researcher_list',
        filter_count: getActiveFilters().length,
        result_count: getTotalResults()
    });
});

// Track form interactions
form.addEventListener('submit', function() {
    APS.Analytics.track('form_submit', {
        form_type: 'contact',
        field_count: this.elements.length,
        completion_time: getFormTime()
    });
});

// Track content engagement
function trackVideoPlay(videoId, videoTitle) {
    APS.Analytics.track('video_play', {
        video_id: videoId,
        video_title: videoTitle,
        position: 'news_article'
    });
}
```

### Conversion Funnels

Define conversion paths and track user progression:

```python
from analytics.models_advanced import ConversionFunnel

# Define membership funnel
funnel = ConversionFunnel.objects.create(
    name='membership_signup',
    description='Track users from homepage to membership completion',
    steps=[
        {'name': 'Homepage Visit', 'event_name': 'page_view', 'url_contains': '/'},
        {'name': 'Membership Page', 'event_name': 'page_view', 'url_contains': '/membership/'},
        {'name': 'Registration Form', 'event_name': 'form_view', 'form_type': 'membership'},
        {'name': 'Form Submission', 'event_name': 'form_submit', 'form_type': 'membership'},
        {'name': 'Payment Complete', 'event_name': 'conversion_goal', 'goal_name': 'membership_paid'}
    ],
    time_window_hours=48
)
```

### Advanced Dashboard Features

#### Journey Visualization
- **Flow Diagrams**: Visual representation of user paths
- **Drop-off Analysis**: Identify where users leave
- **Conversion Tracking**: See goal completions in context

#### A/B Test Analytics
- **Statistical Significance**: Confidence intervals and p-values  
- **Variant Performance**: Detailed metrics for each variant
- **Segment Analysis**: Results broken down by user segments

#### Custom Event Analytics
- **Event Timeline**: Chronological view of all events
- **Category Breakdown**: Events grouped by type
- **Property Analysis**: Deep dive into event properties

#### Performance Insights
- **Page Load Analysis**: Identify slow pages
- **Error Tracking**: JavaScript and server errors
- **User Experience Metrics**: Bounce rate, session duration

### API Endpoints

All Stage 3 features are accessible via REST API:

```bash
# Custom events
POST /api/analytics/events/
{
    "events": [
        {
            "name": "button_click",
            "category": "interaction", 
            "properties": {"button_name": "subscribe"}
        }
    ],
    "session_id": "uuid",
    "user_id": 123
}

# A/B test variant
POST /api/analytics/ab-test/homepage_hero/variant/
{"session_id": "uuid", "user_id": 123}

# A/B test conversion
POST /api/analytics/ab-test/homepage_hero/conversion/
{"session_id": "uuid", "goal": "signup", "value": 10.0}

# Journey analysis
GET /api/analytics/journeys/?days=30

# Funnel analysis
GET /api/analytics/funnel/membership_signup/?days=30

# A/B test results
GET /api/analytics/ab-test/homepage_hero/results/
```

### Advanced Management Commands

```bash
# Generate sample A/B test data
python manage.py shell -c "
from analytics.models_advanced import ABTest, ABTestParticipation
# Create test data
"

# Analyze user journeys
python manage.py shell -c "
from analytics.models_advanced import UserJourney
journeys = UserJourney.objects.all()
print(f'Average pages per journey: {sum(j.page_count for j in journeys) / len(journeys):.1f}')
"

# Export advanced analytics data
python manage.py shell -c "
from analytics.models_advanced import CustomEvent
import csv
with open('custom_events.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerow(['Name', 'Category', 'Timestamp', 'Properties'])
    for event in CustomEvent.objects.all():
        writer.writerow([event.name, event.category, event.timestamp, event.properties])
"
```

## Complete Feature Summary

### ✅ Stage 1 (Basic Analytics)
- ✅ Page view tracking
- ✅ Search monitoring  
- ✅ Error detection
- ✅ Basic dashboard
- ✅ Daily summaries

### ✅ Stage 2 (Enhanced Analytics)
- ✅ Content performance analysis
- ✅ Weekly email reports
- ✅ Advanced dashboard features
- ✅ Data export capabilities
- ✅ System health monitoring

### ✅ Stage 3 (Advanced Analytics)
- ✅ **User Journey Mapping**: Complete session flow tracking
- ✅ **A/B Testing Framework**: Full testing infrastructure with statistical analysis  
- ✅ **Custom Event Tracking**: JavaScript SDK with 50+ automatic event types
- ✅ **Advanced Dashboards**: Journey visualization, funnel analysis, test results
- ✅ **Conversion Funnels**: Multi-step conversion tracking
- ✅ **API Integration**: RESTful APIs for all advanced features
- ✅ **Performance Monitoring**: JavaScript error tracking, page load analysis
- ✅ **User Segmentation**: Flexible user grouping and analysis

**Your analytics system is now enterprise-grade and feature-complete!** 🎯

---

**Generated by APS Analytics System v2.0 - Stage 3 Complete**  
*Built with error-resilience, advanced insights, and maintainability in mind*