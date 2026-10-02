from django.contrib import admin

from .models import ExchangeConnection


@admin.register(ExchangeConnection)
class ExchangeConnectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'exchange_id', 'market_type', 'is_testnet', 'is_active', 'user']
    list_filter = ['market_type', 'exchange_id', 'is_active', 'is_testnet']
    search_fields = ['name', 'exchange_id']
    list_editable = ['is_active']

    fieldsets = (
        ('General', {
            'fields': ('user', 'name', 'exchange_id', 'market_type', 'is_active'),
        }),
        ('Credenciales API', {
            'fields': ('api_key', 'api_secret', 'api_passphrase', 'is_testnet'),
            'classes': ('collapse',),
        }),
        ('Configuración Extra', {
            'fields': ('extra_config',),
            'classes': ('collapse',),
        }),
    )
