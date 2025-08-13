# Django admin is disabled for mailing models
# All mailing functionality is now available in the beautiful Wagtail admin at /admin/
# 
# The mailing system is integrated as Wagtail snippets with:
# - Email Campaigns
# - Mailing Lists  
# - Subscribers
# - Email Templates
# - Automation Rules
# - Email Logs
#
# Look for the "Email Marketing" menu in the Wagtail admin sidebar!

from django.contrib import admin

# No models registered - everything is managed via Wagtail admin interface