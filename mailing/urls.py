from django.urls import path
from . import views

app_name = 'mailing'

urlpatterns = [
    # Admin actions
    path('campaign/<int:campaign_id>/preview/', views.campaign_preview, name='campaign_preview'),
    path('campaign/<int:campaign_id>/send-test/', views.send_test_email, name='send_test_email'),
    path('campaign/<int:campaign_id>/send/', views.send_campaign, name='send_campaign'),
    
    # Public subscription management
    path('subscribe/', views.subscribe, name='subscribe'),
    path('confirm/<int:subscriber_id>/<str:token>/', views.confirm_subscription, name='confirm_subscription'),
    path('unsubscribe/<int:subscriber_id>/<str:token>/', views.unsubscribe, name='unsubscribe'),
    
    # Email tracking
    path('track/open/<str:tracking_id>/', views.track_email_open, name='track_open'),
    path('track/click/<str:tracking_id>/<path:encoded_url>/', views.track_email_click, name='track_click'),
]