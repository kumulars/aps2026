"""
Debug command for analytics troubleshooting.
Usage: python manage.py debug_analytics [options]
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from analytics.models import (
    AnalyticsEvent, DailySummary, AnalyticsConfiguration,
    AnalyticsDebugLog, WeeklyReport
)
import json


class Command(BaseCommand):
    help = 'Debug analytics system and check for issues'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            action='store_true',
            help='Run system checks'
        )
        parser.add_argument(
            '--recent',
            type=int,
            default=10,
            help='Show N most recent events'
        )
        parser.add_argument(
            '--errors',
            action='store_true',
            help='Show recent errors'
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show statistics'
        )
        parser.add_argument(
            '--test-event',
            action='store_true',
            help='Create a test event'
        )
        parser.add_argument(
            '--clear-test',
            action='store_true',
            help='Clear test data'
        )
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Validate data integrity'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Analytics Debug Tool ===\n'))
        
        if options['check']:
            self.run_system_checks()
        
        if options['recent']:
            self.show_recent_events(options['recent'])
        
        if options['errors']:
            self.show_errors()
        
        if options['stats']:
            self.show_statistics()
        
        if options['test_event']:
            self.create_test_event()
        
        if options['clear_test']:
            self.clear_test_data()
        
        if options['validate']:
            self.validate_data()
        
        # Default: show summary if no specific option
        if not any([options['check'], options['errors'], options['stats'], 
                   options['test_event'], options['clear_test'], options['validate']]):
            self.show_summary()
    
    def run_system_checks(self):
        """Run comprehensive system checks"""
        self.stdout.write('\n📋 Running System Checks...\n')
        
        checks = []
        
        # Check 1: Configuration
        try:
            config = AnalyticsConfiguration.get_config()
            checks.append(('Configuration', 'OK', f'Analytics {"enabled" if config.enabled else "disabled"}'))
        except Exception as e:
            checks.append(('Configuration', 'ERROR', str(e)))
        
        # Check 2: Database tables
        try:
            AnalyticsEvent.objects.exists()
            checks.append(('Database Tables', 'OK', 'All tables accessible'))
        except Exception as e:
            checks.append(('Database Tables', 'ERROR', str(e)))
        
        # Check 3: Recent activity
        try:
            recent_count = AnalyticsEvent.objects.filter(
                timestamp__gte=timezone.now() - timedelta(hours=1)
            ).count()
            status = 'OK' if recent_count > 0 else 'WARNING'
            checks.append(('Recent Activity', status, f'{recent_count} events in last hour'))
        except Exception as e:
            checks.append(('Recent Activity', 'ERROR', str(e)))
        
        # Check 4: Error rate
        try:
            total = AnalyticsEvent.objects.filter(
                timestamp__gte=timezone.now() - timedelta(hours=24)
            ).count()
            errors = AnalyticsEvent.objects.filter(
                timestamp__gte=timezone.now() - timedelta(hours=24),
                processing_status='failed'
            ).count()
            error_rate = (errors / total * 100) if total > 0 else 0
            status = 'OK' if error_rate < 5 else 'WARNING' if error_rate < 20 else 'ERROR'
            checks.append(('Error Rate', status, f'{error_rate:.1f}% ({errors}/{total})'))
        except Exception as e:
            checks.append(('Error Rate', 'ERROR', str(e)))
        
        # Check 5: Daily summaries
        try:
            today = timezone.now().date()
            summary_exists = DailySummary.objects.filter(date=today).exists()
            status = 'OK' if summary_exists else 'INFO'
            msg = 'Today\'s summary exists' if summary_exists else 'Today\'s summary pending'
            checks.append(('Daily Summaries', status, msg))
        except Exception as e:
            checks.append(('Daily Summaries', 'ERROR', str(e)))
        
        # Display results
        for check, status, message in checks:
            if status == 'OK':
                icon = '✅'
                style = self.style.SUCCESS
            elif status == 'WARNING':
                icon = '⚠️'
                style = self.style.WARNING
            elif status == 'ERROR':
                icon = '❌'
                style = self.style.ERROR
            else:
                icon = 'ℹ️'
                style = self.style.HTTP_INFO
            
            self.stdout.write(f'{icon} {check:20} {style(status):8} {message}')
    
    def show_recent_events(self, count):
        """Show recent analytics events"""
        self.stdout.write(f'\n📊 Recent {count} Events:\n')
        
        events = AnalyticsEvent.objects.all()[:count]
        
        for event in events:
            status_icon = '✅' if event.processing_status == 'processed' else '❌'
            self.stdout.write(
                f'{status_icon} [{event.timestamp.strftime("%Y-%m-%d %H:%M:%S")}] '
                f'{event.event_type:12} {event.page_url[:50]}'
            )
            
            if event.event_data:
                self.stdout.write(f'   Data: {json.dumps(event.event_data)[:100]}')
            
            if event.processing_status == 'failed':
                self.stdout.write(self.style.ERROR(f'   Error: {event.last_error}'))
    
    def show_errors(self):
        """Show recent errors and debug logs"""
        self.stdout.write('\n❌ Recent Errors:\n')
        
        # Failed events
        failed_events = AnalyticsEvent.objects.filter(
            processing_status='failed'
        ).order_by('-timestamp')[:10]
        
        if failed_events:
            self.stdout.write('\nFailed Events:')
            for event in failed_events:
                self.stdout.write(
                    f'  [{event.timestamp.strftime("%Y-%m-%d %H:%M:%S")}] '
                    f'{event.event_type}: {event.last_error[:100]}'
                )
        else:
            self.stdout.write('  No failed events')
        
        # Debug logs
        error_logs = AnalyticsDebugLog.objects.filter(
            level__in=['ERROR', 'CRITICAL']
        ).order_by('-timestamp')[:10]
        
        if error_logs:
            self.stdout.write('\nError Logs:')
            for log in error_logs:
                self.stdout.write(
                    f'  [{log.timestamp.strftime("%Y-%m-%d %H:%M:%S")}] '
                    f'{log.component}: {log.message[:100]}'
                )
        else:
            self.stdout.write('  No error logs')
    
    def show_statistics(self):
        """Show analytics statistics"""
        self.stdout.write('\n📈 Analytics Statistics:\n')
        
        # Overall stats
        total_events = AnalyticsEvent.objects.count()
        total_summaries = DailySummary.objects.count()
        total_reports = WeeklyReport.objects.count()
        
        self.stdout.write(f'Total Events:     {total_events:,}')
        self.stdout.write(f'Daily Summaries:  {total_summaries:,}')
        self.stdout.write(f'Weekly Reports:   {total_reports:,}')
        
        # Today's stats
        today_events = AnalyticsEvent.objects.filter(
            timestamp__date=timezone.now().date()
        )
        
        if today_events.exists():
            self.stdout.write('\nToday\'s Activity:')
            
            # Event type breakdown
            from django.db.models import Count
            event_types = today_events.values('event_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            for et in event_types:
                self.stdout.write(f'  {et["event_type"]:15} {et["count"]:,}')
            
            # User stats
            unique_sessions = today_events.values('session_id').distinct().count()
            bot_events = today_events.filter(is_bot=True).count()
            
            self.stdout.write(f'\nUnique Sessions:  {unique_sessions:,}')
            self.stdout.write(f'Bot Events:       {bot_events:,}')
    
    def create_test_event(self):
        """Create a test event for debugging"""
        self.stdout.write('\n🧪 Creating test event...')
        
        event = AnalyticsEvent.objects.create(
            event_type='custom',
            page_url='http://test.example.com/debug',
            event_data={
                'test': True,
                'created_by': 'debug_analytics',
                'timestamp': timezone.now().isoformat()
            },
            processing_status='processed'
        )
        
        self.stdout.write(self.style.SUCCESS(f'Created test event: {event.id}'))
    
    def clear_test_data(self):
        """Clear test data"""
        self.stdout.write('\n🧹 Clearing test data...')
        
        # Delete test events
        count = AnalyticsEvent.objects.filter(
            event_data__test=True
        ).delete()[0]
        
        self.stdout.write(f'Deleted {count} test events')
    
    def validate_data(self):
        """Validate data integrity"""
        self.stdout.write('\n🔍 Validating Data Integrity...\n')
        
        issues = []
        
        # Check for orphaned sessions
        from django.db.models import Count
        session_events = AnalyticsEvent.objects.values('session_id').annotate(
            count=Count('id')
        ).filter(count=1, session_id__gt='')
        
        if session_events.count() > 10:
            issues.append(f'Found {session_events.count()} single-event sessions (possible issue)')
        
        # Check for future timestamps
        future_events = AnalyticsEvent.objects.filter(
            timestamp__gt=timezone.now()
        ).count()
        
        if future_events > 0:
            issues.append(f'Found {future_events} events with future timestamps')
        
        # Check for missing summaries
        from datetime import date
        start_date = AnalyticsEvent.objects.earliest('timestamp').timestamp.date()
        end_date = timezone.now().date()
        
        current = start_date
        missing_dates = []
        while current < end_date:
            if not DailySummary.objects.filter(date=current).exists():
                if AnalyticsEvent.objects.filter(timestamp__date=current).exists():
                    missing_dates.append(current)
            current += timedelta(days=1)
        
        if missing_dates:
            issues.append(f'Missing summaries for {len(missing_dates)} days')
        
        # Display results
        if issues:
            self.stdout.write(self.style.WARNING('Issues found:'))
            for issue in issues:
                self.stdout.write(f'  ⚠️  {issue}')
        else:
            self.stdout.write(self.style.SUCCESS('✅ No integrity issues found'))
    
    def show_summary(self):
        """Show default summary"""
        self.stdout.write('\n📊 Analytics Summary\n')
        
        config = AnalyticsConfiguration.get_config()
        
        self.stdout.write(f'Status: {"🟢 Enabled" if config.enabled else "🔴 Disabled"}')
        self.stdout.write(f'Debug Mode: {"Yes" if config.debug_mode else "No"}')
        
        # Quick stats
        total = AnalyticsEvent.objects.count()
        today = AnalyticsEvent.objects.filter(
            timestamp__date=timezone.now().date()
        ).count()
        
        self.stdout.write(f'\nTotal Events: {total:,}')
        self.stdout.write(f'Today: {today:,}')
        
        self.stdout.write('\nRun with --help to see available options')