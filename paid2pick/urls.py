from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),  # login, logout, etc.
    path("accounts/", include("accounts.urls")),             # register
    path("", include("picks.urls")),                         # picks/, purchases/
    path("", include("contests.urls")),                      # contests/
    path("", include("payments.urls")),                      # wallet/add/, webhook
    path("", include("web.urls")),                           # games (home)
]
