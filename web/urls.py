from django.urls import path

from . import views

urlpatterns = [
    path("", views.games, name="games"),
    path("game/<int:pk>/", views.game_detail, name="game_detail"),
]
