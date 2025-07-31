from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls
from search import views as search_views
from home import views
from home.views import highlight_detail
from django.shortcuts import render, get_object_or_404

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("search/", search_views.search, name="search"),
    path("highlight/<slug:slug>/", highlight_detail, name="highlight_detail"),
    # News item detail pages (custom view still needed)
    path("news/<slug:slug>/", views.news_item_detail_view, name="news_item_detail"),

    # Obituary detail pages
    path("obituaries/<slug:slug>/", views.obituary_detail_view, name="obituary_detail"),
    
    # Award recipient detail pages
    path("awards/recipient/<slug:slug>/", views.award_recipient_detail_view, name="award-recipient-detail"),

    # Symposium images API
    path("api/symposium-images/<str:year>/", views.symposium_images_api, name="symposium-images-api"),

    # Allauth URLs for membership authentication
    path("accounts/", include("allauth.urls")),
    
    # Member views
    path("members/", include("members.urls")),

    # Wagtail's page routing — MUST come last
    path("", include(wagtail_urls)),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

