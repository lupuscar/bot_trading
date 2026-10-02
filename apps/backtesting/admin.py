from django.contrib import admin

from .models import BacktestRun


@admin.register(BacktestRun)
class BacktestRunAdmin(admin.ModelAdmin):
    list_display = [
        'strategy', 'symbol', 'timeframe', 'status',
        'total_return_pct', 'sharpe_ratio', 'total_trades', 'created_at',
    ]
    list_filter = ['status', 'timeframe', 'strategy']
    search_fields = ['symbol', 'strategy__name']
    readonly_fields = [
        'final_capital', 'total_return_pct', 'max_drawdown_pct',
        'sharpe_ratio', 'total_trades', 'winning_trades', 'losing_trades',
        'profit_factor', 'results_data',
    ]
