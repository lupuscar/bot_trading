from django.contrib import admin

from .models import PaperAccount, PaperTrade


@admin.register(PaperAccount)
class PaperAccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'current_balance', 'currency', 'total_return_pct', 'is_active', 'user']
    list_filter = ['is_active', 'currency']

    @admin.display(description='Retorno %')
    def total_return_pct(self, obj):
        return f'{obj.total_return_pct:.2f}%'


@admin.register(PaperTrade)
class PaperTradeAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'side', 'amount', 'entry_price', 'exit_price', 'pnl', 'status', 'created_at']
    list_filter = ['status', 'side', 'symbol']
    search_fields = ['symbol']
