from django.contrib import admin

from .models import TradingBot, TradeRecord


@admin.register(TradingBot)
class TradingBotAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'symbol', 'timeframe', 'mode', 'status',
        'strategy', 'exchange_connection', 'is_active', 'last_run_at',
    ]
    list_filter = ['status', 'mode', 'timeframe', 'is_active']
    search_fields = ['name', 'symbol']
    list_editable = ['is_active']

    fieldsets = (
        ('General', {
            'fields': ('user', 'name', 'description', 'is_active'),
        }),
        ('Componentes', {
            'fields': ('exchange_connection', 'strategy'),
        }),
        ('Configuración de Trading', {
            'fields': ('symbol', 'timeframe', 'mode'),
        }),
        ('Gestión de Riesgo', {
            'fields': (
                'max_position_size', 'risk_per_trade_pct',
                'max_open_positions', 'daily_loss_limit_pct',
            ),
        }),
        ('Estado', {
            'fields': ('status', 'last_signal', 'last_run_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(TradeRecord)
class TradeRecordAdmin(admin.ModelAdmin):
    list_display = [
        'bot', 'symbol', 'side', 'amount', 'price',
        'pnl', 'status', 'created_at',
    ]
    list_filter = ['status', 'side', 'symbol', 'bot']
    search_fields = ['symbol', 'exchange_order_id']
    readonly_fields = ['raw_response', 'signal_data']
