from django.contrib import admin

from .models import LedgerEntry, Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance")
    search_fields = ("user__username",)


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "wallet", "amount", "kind", "balance_after")
    list_filter = ("kind",)
    search_fields = ("wallet__user__username",)
