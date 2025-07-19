from django.urls import path
from . import views
from . import payment

urlpatterns = [
    path('dashboard/', views.member_dashboard, name='member_dashboard'),
    path('profile/', views.member_profile, name='member_profile'),
    path('directory/', views.member_directory, name='member_directory'),
    path('detail/<int:pk>/', views.member_detail, name='member_detail'),
    
    # Payment URLs
    path('payment/', payment.membership_payment, name='membership_payment'),
    path('payment/create-intent/', payment.create_payment_intent, name='create_payment_intent'),
    path('payment/webhook/', payment.stripe_webhook, name='stripe_webhook'),
    path('payment/mock-success/', payment.mock_payment_success, name='mock_payment_success'),
]