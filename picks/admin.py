from django.contrib import admin

from .models import Pick, Purchase


@admin.register(Pick)
class PickAdmin(admin.ModelAdmin):
    list_display = ("author", "match", "get_bet_type_display", "line_point",
                    "odds_price", "outcome", "accustat_points", "created_at")
    list_filter = ("outcome", "market", "match__sport")
    search_fields = ("author__username", "match__home", "match__away")


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("buyer", "pick", "status", "price_paid", "platform_fee",
                    "created_at")
    list_filter = ("status",)
    search_fields = ("buyer__username",)
