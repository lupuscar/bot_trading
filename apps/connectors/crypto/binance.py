import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

import ccxt
import pandas as pd

from apps.connectors.base import BaseConnector, Ticker, Balance, Order, Position


class BinanceConnector(BaseConnector):
    """Conector para Binance usando ccxt."""

    def __init__(self, name: str, market_type: str, config: dict = None):
        super().__init__(name, market_type, config)
        self.exchange = None

    def connect(self) -> bool:
        """Establecer conexión con Binance."""
        try:
            api_key = self.config.get('api_key', '')
            api_secret = self.config.get('api_secret', '')
            
            if not api_key or not api_secret:
                try:
                    from apps.core.models import SystemSetting
                    db_key = SystemSetting.objects.filter(key='BINANCE_API_KEY').first()
                    db_secret = SystemSetting.objects.filter(key='BINANCE_API_SECRET').first()
                    if db_key and db_secret:
                        api_key = db_key.value
                        api_secret = db_secret.value
                except Exception as e:
                    self.logger.warning(f"No se pudo leer de SystemSetting: {e}")

            exchange_config = {
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',
                    'adjustForTimeDifference': True,
                },
            }
            
            if self.config.get('testnet', True):
                exchange_config['testnet'] = True

            self.exchange = ccxt.binance(exchange_config)
            
            # Verificar conexión si hay API keys
            if exchange_config['apiKey'] and exchange_config['secret']:
                self.exchange.check_required_credentials()
            else:
                # Si no hay keys, solo podemos acceder a endpoints públicos
                pass
            
            self._connected = True
            self.logger.info(f"Conectado a Binance {'(Testnet)' if self.config.get('testnet', True) else '(Live)'}")
            return True
        except Exception as e:
            self.logger.error(f"Error conectando a Binance: {e}")
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Binance/ccxt no requiere una desconexión explícita, pero cerramos estado."""
        self._connected = False
        self.exchange = None
        self.logger.info("Desconectado de Binance")

    def test_connection(self) -> bool:
        if not self._connected:
            self.connect()
        try:
            # Una llamada ligera a la API privada para validar credenciales
            if self.exchange.apiKey and self.exchange.secret:
                self.exchange.fetch_balance()
            else:
                self.exchange.fetch_time()
            return True
        except Exception as e:
            self.logger.error(f"Fallo en test de conexión: {e}")
            return False

    def get_ticker(self, symbol: str) -> Ticker:
        if not self._connected:
            self.connect()
        ticker = self.exchange.fetch_ticker(symbol)
        return Ticker(
            symbol=symbol,
            bid=Decimal(str(ticker['bid'])),
            ask=Decimal(str(ticker['ask'])),
            last=Decimal(str(ticker['last'])),
            volume=Decimal(str(ticker['baseVolume'])),
            timestamp=datetime.fromtimestamp(ticker['timestamp'] / 1000.0)
        )

    def get_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[datetime] = None,
        end: datetime = None,
        limit: int = None,
    ) -> pd.DataFrame:
        if not self._connected:
            self.connect()
        
        since = int(start.timestamp() * 1000) if start else None
        
        # ccxt usa milisegundos y tiene un límite de velas por request.
        all_ohlcv = []
        while True:
            # Si no hay since, traerá los más recientes.
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit or 1000)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            
            # Si traemos los más recientes (since=None) y ya tuvimos una respuesta, 
            # no podemos seguir iterando hacia atrás o adelante fácilmente sin cambiar logic.
            # ccxt con since=None solo te da la última página. 
            if not start:
                break
                
            since = ohlcv[-1][0] + 1
            if limit and len(all_ohlcv) >= limit:
                break
            # Detener si alcanzamos la fecha de fin (simplificado)
            if end and ohlcv[-1][0] >= int(end.timestamp() * 1000):
                break
            
            # Si trajimos menos de lo solicitado o menos del max, ya no hay más
            if len(ohlcv) < 1000:
                break

        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        return df

    def get_available_symbols(self) -> list[str]:
        if not self._connected:
            self.connect()
        markets = self.exchange.load_markets()
        return list(markets.keys())

    def get_balance(self) -> dict[str, Balance]:
        if not self._connected:
            self.connect()
        balance_info = self.exchange.fetch_balance()
        balances = {}
        for currency, data in balance_info['total'].items():
            if data > 0:
                balances[currency] = Balance(
                    currency=currency,
                    total=Decimal(str(data)),
                    available=Decimal(str(balance_info['free'].get(currency, 0))),
                    reserved=Decimal(str(balance_info['used'].get(currency, 0)))
                )
        return balances

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: Decimal,
        price: Decimal = None,
        stop_price: Decimal = None,
        params: dict = None,
    ) -> Order:
        if not self._connected:
            self.connect()
        
        extra_params = params or {}
        if stop_price:
            extra_params['stopPrice'] = float(stop_price)

        order = self.exchange.create_order(
            symbol=symbol,
            type=order_type,
            side=side,
            amount=float(amount),
            price=float(price) if price else None,
            params=extra_params
        )
        
        result = Order(
            id=str(order['id']),
            symbol=symbol,
            side=side,
            order_type=order_type,
            amount=amount,
            price=price,
            stop_price=stop_price,
            status=order['status'],
            timestamp=datetime.fromtimestamp(order['timestamp'] / 1000.0) if order.get('timestamp') else datetime.now(),
            raw=order
        )
        self._log_order(result, action='PLACED')
        return result

    def cancel_order(self, order_id: str, symbol: str = None) -> bool:
        if not self._connected:
            self.connect()
        try:
            self.exchange.cancel_order(order_id, symbol)
            return True
        except Exception as e:
            self.logger.error(f"Error cancelando orden {order_id}: {e}")
            return False

    def get_order(self, order_id: str, symbol: str = None) -> Order:
        if not self._connected:
            self.connect()
        order = self.exchange.fetch_order(order_id, symbol)
        return self._parse_ccxt_order(order)

    def get_open_orders(self, symbol: str = None) -> list[Order]:
        if not self._connected:
            self.connect()
        orders = self.exchange.fetch_open_orders(symbol)
        return [self._parse_ccxt_order(o) for o in orders]

    def get_positions(self, symbol: str = None) -> list[Position]:
        # Binance Spot no tiene posiciones como en futuros.
        # Si usáramos futuros, fetch_positions() sería necesario.
        return []
        
    def _parse_ccxt_order(self, order_data: dict) -> Order:
        return Order(
            id=str(order_data['id']),
            symbol=order_data['symbol'],
            side=order_data['side'],
            order_type=order_data['type'],
            amount=Decimal(str(order_data['amount'])),
            price=Decimal(str(order_data['price'])) if order_data.get('price') else None,
            filled=Decimal(str(order_data.get('filled', 0))),
            remaining=Decimal(str(order_data.get('remaining', 0))),
            cost=Decimal(str(order_data.get('cost', 0))),
            status=order_data['status'],
            timestamp=datetime.fromtimestamp(order_data['timestamp'] / 1000.0) if order_data.get('timestamp') else None,
            raw=order_data
        )
