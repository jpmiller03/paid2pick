from django.contrib import admin

from .models import Contest, ContestEntry, ContestGame, ContestPick


class ContestGameInline(admin.TabularInline):
    model = ContestGame
    extra = 0


@admin.register(Contest)
class ContestAdmin(admin.ModelAdmin):
    list_display = ("name", "sport", "starts_at", "ends_at", "entry_fee", "status")
    list_filter = ("status", "sport")
    inlines = [ContestGameInline]


@admin.register(ContestEntry)
class ContestEntryAdmin(admin.ModelAdmin):
    list_display = ("contest", "user", "score", "rank", "payout", "entered_at")
    list_filter = ("contest",)


admin.site.register(ContestPick)
