from django.urls import path

from . import views

urlpatterns = [
    path("contests/", views.contest_list, name="contest_list"),
    path("contests/<int:pk>/", views.contest_detail, name="contest_detail"),
    path("contests/<int:pk>/enter/", views.enter, name="contest_enter"),
    path("contests/<int:pk>/pick/", views.pick, name="contest_pick"),
]
