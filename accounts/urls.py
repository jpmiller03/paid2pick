from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.register, name="register"),
    path("u/<int:pk>/", views.profile, name="profile"),
]
