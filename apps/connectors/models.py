"""
Modelos de base de datos para los conectores.
Almacenan la configuración de conexiones a exchanges y brokers.
"""
from django.db import models
from django.contrib.auth.models import User

from apps.core.models import ActivatableModel, MarketType


class ExchangeConnection(ActivatableModel):
    """
    Configuración de conexión a un exchange o broker.
    Las API keys se almacenan encriptadas.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='exchange_connections',
        verbose_name='Usuario',
    )
    name = models.CharField(
        'Nombre',
        max_length=100,
        help_text='Nombre identificador (ej: "Mi cuenta Binance")',
    )
    exchange_id = models.CharField(
        'Exchange ID',
        max_length=50,
        help_text='Identificador del exchange (ej: binance, kraken, oanda)',
    )
    market_type = models.CharField(
        'Tipo de mercado',
        max_length=20,
        choices=MarketType.choices,
    )
    api_key = models.CharField(
        'API Key',
        max_length=255,
        blank=True,
        default='',
    )
    api_secret = models.CharField(
        'API Secret',
        max_length=255,
        blank=True,
        default='',
    )
    api_passphrase = models.CharField(
        'Passphrase',
        max_length=255,
        blank=True,
        default='',
        help_text='Requerido por algunos exchanges (ej: Coinbase Pro)',
    )
    is_testnet = models.BooleanField(
        'Usar Testnet',
        default=True,
        help_text='Usar entorno de pruebas del exchange',
    )
    extra_config = models.JSONField(
        'Configuración extra',
        default=dict,
        blank=True,
        help_text='Parámetros adicionales en formato JSON',
    )

    class Meta:
        verbose_name = 'Conexión a Exchange'
        verbose_name_plural = 'Conexiones a Exchanges'
        unique_together = ['user', 'name']
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.exchange_id}) - {self.get_market_type_display()}'

    def get_connector_config(self) -> dict:
        """Devuelve la configuración para instanciar el conector."""
        config = {
            'api_key': self.api_key,
            'api_secret': self.api_secret,
            'testnet': self.is_testnet,
        }
        if self.api_passphrase:
            config['passphrase'] = self.api_passphrase
        config.update(self.extra_config)
        return config
