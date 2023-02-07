"""coriolis URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.urls import include, path
from django.conf.urls.static import static

import debug_toolbar


def trigger_error(request):
    _ = 1 / 0


urlpatterns = [
    path('__debug__/', include(debug_toolbar.urls)),
    path('sentry-debug/', trigger_error),
    path('admin/', admin.site.urls),

    path('accounts/', include('allauth_2fa.urls')),
    path('accounts/', include('allauth.urls')),
    path('hijack/', include('hijack.urls')),

    path('payments/', include('payments.urls')),

    path('i18n/', include('django.conf.urls.i18n')),

    path('', include('events.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
