from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import PickerStats, User

admin.site.register(User, UserAdmin)


@admin.register(PickerStats)
class PickerStatsAdmin(admin.ModelAdmin):
    list_display = ("user", "sport", "wins", "losses", "win_pct",
                    "win_pct_last7", "accustat")
    list_filter = ("sport",)
    search_fields = ("user__username",)
