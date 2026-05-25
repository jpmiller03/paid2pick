from django.contrib import admin

from .models import Deposit


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ("user", "amount_cents", "coins", "provider", "status",
                    "created_at")
    list_filter = ("status", "provider")
    search_fields = ("user__username", "provider_ref")
