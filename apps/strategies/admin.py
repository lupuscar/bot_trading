from django.contrib import admin

from .models import Strategy


@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    list_display = ['name', 'version', 'timeframe', 'is_active', 'user', 'created_at']
    list_filter = ['timeframe', 'is_active', 'version']
    search_fields = ['name', 'description']
    list_editable = ['is_active']
