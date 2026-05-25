from django.urls import path

from . import views

urlpatterns = [
    path("wallet/add/", views.add_funds, name="add_funds"),
    path("payments/webhook/", views.webhook, name="payments_webhook"),
]
