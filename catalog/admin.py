from django.contrib import admin

from .models import Match, Sport


@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    list_display = ("category", "label", "odds_api_key", "active")


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("__str__", "sport", "commence_time", "status",
                    "home_score", "away_score")
    list_filter = ("sport", "status")
    search_fields = ("home", "away", "external_id")
    date_hierarchy = "commence_time"
