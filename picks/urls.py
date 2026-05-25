from django.urls import path

from . import views

urlpatterns = [
    path("picks/", views.browse, name="picks_browse"),
    path("picks/make/", views.pick_make, name="pick_make"),
    path("picks/<int:pk>/buy/", views.buy, name="pick_buy"),
    path("purchases/", views.purchases, name="purchases"),
]
