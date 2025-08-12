"""
Generate and send weekly analytics reports.
Usage: python manage.py send_weekly_report
"""

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from django.template.loader import render_to_string
from django.db import models
from datetime import timedelta, date
from collections import Counter
from analytics.models import (
    AnalyticsEvent, DailySummary, WeeklyReport,
    AnalyticsConfiguration, AnalyticsDebugLog
)
import json


class Command(BaseCommand):
    help = 'Generate and send weekly analytics reports'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--week-start',
            type=str,
            help='Week start date (YYYY-MM-DD). Defaults to last Monday'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Generate report but don\'t send email'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Generate report even if already exists'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Send to specific email address (for testing)'
        )
    
    def handle(self, *args, **options):
        config = AnalyticsConfiguration.get_config()
        
        if not config.enabled:
            self.stdout.write(
                self.style.WARNING('Analytics is disabled. Skipping report.')
            )
            return
        
        if not config.send_weekly_reports and not options['force']:
            self.stdout.write(
                self.style.WARNING('Weekly reports are disabled. Use --force to override.')
            )
            return
        
        # Calculate week dates
        if options['week_start']:
            try:
                week_start = date.fromisoformat(options['week_start'])
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('Invalid date format. Use YYYY-MM-DD')
                )
                return
        else:
            # Default to last Monday
            today = timezone.now().date()
            days_since_monday = today.weekday()
            week_start = today - timedelta(days=days_since_monday + 7)
        
        week_end = week_start + timedelta(days=6)
        
        self.stdout.write(f'Generating report for week: {week_start} to {week_end}')
        
        # Check if report already exists
        existing_report = WeeklyReport.objects.filter(
            week_start=week_start,
            week_end=week_end
        ).first()
        
        if existing_report and existing_report.is_generated and not options['force']:
            self.stdout.write(
                self.style.WARNING('Report already exists. Use --force to regenerate.')
            )
            return
        
        # Generate report
        try:
            report_data = self.generate_report_data(week_start, week_end)
            
            # Save or update report
            if existing_report:
                report = existing_report
            else:
                report = WeeklyReport(week_start=week_start, week_end=week_end)
            
            report.report_data = report_data
            report.is_generated = True
            report.generation_errors = ''
            report.save()
            
            self.stdout.write(
                self.style.SUCCESS(f'Report generated successfully: {report.pk}')
            )
            
            # Send email
            if not options['dry_run']:
                recipients = []
                
                if options['email']:
                    recipients = [options['email']]
                elif config.report_recipients:
                    recipients = config.report_recipients
                
                if recipients:
                    self.send_report_email(report, recipients)
                    report.sent_to = recipients
                    report.sent_at = timezone.now()
                    report.is_sent = True
                    report.save()
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'Report sent to {len(recipients)} recipients')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING('No recipients configured')
                    )
            else:
                self.stdout.write(
                    self.style.WARNING('Dry run - email not sent')
                )
                
        except Exception as e:
            error_msg = str(e)
            self.stdout.write(
                self.style.ERROR(f'Report generation failed: {error_msg}')
            )
            
            # Save error to report
            if 'report' in locals():
                report.generation_errors = error_msg
                report.is_generated = False
                report.save()
            
            # Log error
            AnalyticsDebugLog.objects.create(
                level='ERROR',
                component='send_weekly_report',
                message=f'Weekly report generation failed: {error_msg}'
            )
    
    def generate_report_data(self, week_start, week_end):
        """Generate comprehensive report data"""
        
        # Get events for the week
        week_events = AnalyticsEvent.objects.filter(
            timestamp__date__gte=week_start,
            timestamp__date__lte=week_end,
            is_bot=False
        )
        
        # Get previous week for comparison
        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = week_end - timedelta(days=7)
        
        prev_week_events = AnalyticsEvent.objects.filter(
            timestamp__date__gte=prev_week_start,
            timestamp__date__lte=prev_week_end,
            is_bot=False
        )
        
        # Calculate metrics
        metrics = {
            'page_views': {
                'current': week_events.filter(event_type='page_view').count(),
                'previous': prev_week_events.filter(event_type='page_view').count(),
            },
            'unique_visitors': {
                'current': week_events.values('session_id').distinct().count(),
                'previous': prev_week_events.values('session_id').distinct().count(),
            },
            'searches': {
                'current': week_events.filter(event_type='search').count(),
                'previous': prev_week_events.filter(event_type='search').count(),
            },
            'errors': {
                'current': week_events.filter(event_type='error').count(),
                'previous': prev_week_events.filter(event_type='error').count(),
            }
        }
        
        # Calculate percentage changes
        for metric in metrics:
            current = metrics[metric]['current']
            previous = metrics[metric]['previous']
            
            if previous > 0:
                change = ((current - previous) / previous) * 100
            elif current > 0:
                change = 100  # New activity
            else:
                change = 0
            
            metrics[metric]['change'] = round(change, 1)
            metrics[metric]['change_direction'] = 'up' if change > 0 else 'down' if change < 0 else 'same'
        
        # Top pages
        top_pages = list(week_events.filter(
            event_type='page_view'
        ).values('page_url').annotate(
            views=models.Count('id')
        ).order_by('-views')[:10])
        
        # Top searches
        search_queries = []
        for event in week_events.filter(event_type='search'):
            if event.event_data and 'query' in event.event_data:
                search_queries.append(event.event_data['query'])
        
        top_searches = Counter(search_queries).most_common(10)
        
        # Daily breakdown
        daily_stats = []
        current = week_start
        while current <= week_end:
            day_events = week_events.filter(timestamp__date=current)
            daily_stats.append({
                'date': current.strftime('%Y-%m-%d'),
                'day_name': current.strftime('%A'),
                'page_views': day_events.filter(event_type='page_view').count(),
                'visitors': day_events.values('session_id').distinct().count(),
                'searches': day_events.filter(event_type='search').count(),
            })
            current += timedelta(days=1)
        
        # System health
        failed_events = week_events.filter(processing_status='failed').count()
        total_events = week_events.count()
        error_rate = (failed_events / total_events * 100) if total_events > 0 else 0
        
        # Notable events/insights
        insights = []
        
        # Check for significant changes
        if metrics['page_views']['change'] > 50:
            insights.append(f"🎉 Page views increased by {metrics['page_views']['change']:.1f}%")
        elif metrics['page_views']['change'] < -30:
            insights.append(f"⚠️ Page views decreased by {abs(metrics['page_views']['change']):.1f}%")
        
        if metrics['searches']['current'] > metrics['searches']['previous'] * 2:
            insights.append("🔍 Search activity doubled compared to previous week")
        
        # Check for errors
        if metrics['errors']['current'] > 10:
            insights.append(f"❌ {metrics['errors']['current']} errors occurred this week")
        
        # Top performing day
        best_day = max(daily_stats, key=lambda x: x['page_views'])
        if best_day['page_views'] > 0:
            insights.append(f"📈 Best day: {best_day['day_name']} with {best_day['page_views']} page views")
        
        return {
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'generated_at': timezone.now().isoformat(),
            'metrics': metrics,
            'top_pages': top_pages,
            'top_searches': top_searches,
            'daily_stats': daily_stats,
            'system_health': {
                'error_rate': round(error_rate, 2),
                'failed_events': failed_events,
                'total_events': total_events,
            },
            'insights': insights,
        }
    
    def send_report_email(self, report, recipients):
        """Send report via email"""
        
        subject = f'Weekly Analytics Report - {report.week_start} to {report.week_end}'
        
        # Create text version
        text_content = self.generate_text_report(report.report_data)
        
        # Send email
        try:
            send_mail(
                subject=subject,
                message=text_content,
                from_email=None,  # Uses DEFAULT_FROM_EMAIL
                recipient_list=recipients,
                fail_silently=False,
            )
        except Exception as e:
            raise Exception(f'Email sending failed: {e}')
    
    def generate_text_report(self, report_data):
        """Generate plain text report"""
        
        lines = []
        lines.append('📊 WEEKLY ANALYTICS REPORT')
        lines.append('=' * 50)
        lines.append(f"Week: {report_data['week_start']} to {report_data['week_end']}")
        lines.append('')
        
        # Key metrics
        lines.append('📈 KEY METRICS')
        lines.append('-' * 20)
        metrics = report_data['metrics']
        
        for metric_name, data in metrics.items():
            current = data['current']
            change = data['change']
            direction = '↑' if change > 0 else '↓' if change < 0 else '→'
            
            lines.append(f"{metric_name.replace('_', ' ').title():15} {current:8,} ({direction} {abs(change):4.1f}%)")
        
        lines.append('')
        
        # Insights
        if report_data['insights']:
            lines.append('💡 KEY INSIGHTS')
            lines.append('-' * 20)
            for insight in report_data['insights']:
                lines.append(f"• {insight}")
            lines.append('')
        
        # Top pages
        lines.append('🏆 TOP PAGES')
        lines.append('-' * 20)
        for i, page in enumerate(report_data['top_pages'][:5], 1):
            url = page['page_url']
            if len(url) > 40:
                url = url[:37] + '...'
            lines.append(f"{i:2}. {url:40} {page['views']:6,} views")
        lines.append('')
        
        # Top searches
        if report_data['top_searches']:
            lines.append('🔍 TOP SEARCHES')
            lines.append('-' * 20)
            for i, (query, count) in enumerate(report_data['top_searches'][:5], 1):
                lines.append(f"{i:2}. {query:30} {count:6,} searches")
            lines.append('')
        
        # Daily breakdown
        lines.append('📅 DAILY BREAKDOWN')
        lines.append('-' * 20)
        lines.append('Day         Page Views  Visitors  Searches')
        lines.append('-' * 40)
        for day in report_data['daily_stats']:
            lines.append(f"{day['day_name'][:9]:10} {day['page_views']:10,} {day['visitors']:9,} {day['searches']:9,}")
        
        lines.append('')
        lines.append('Generated by APS Analytics System')
        lines.append(f"Report ID: {report_data.get('report_id', 'N/A')}")
        
        return '\n'.join(lines)