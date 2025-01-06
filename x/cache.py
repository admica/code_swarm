# PATH: ./utils/cache.py
from datetime import datetime, timedelta
import pytz
import logging
from typing import Optional, Dict, List, Tuple
import asyncio

logger = logging.getLogger(__name__)

class PriceCache:
    """Cache for storing recent price data"""
    
    def __init__(self, window_days: int = 5, match_minutes: int = 3):
        """Initialize price cache with window and matching parameters"""
        self.window_days = window_days
        self.match_minutes = match_minutes
        self.prices: Dict[str, List[Tuple[datetime, float]]] = {}
        self.lock = asyncio.Lock()
    
    def get_all_prices(self) -> dict:
        """Get all prices currently in the cache"""
        return {symbol: list(prices) for symbol, prices in self.prices.items()}
    
    async def add_price(self, symbol: str, price: float, timestamp: datetime):
        """Add a price point to the cache"""
        if not timestamp.tzinfo:
            timestamp = pytz.UTC.localize(timestamp)
            
        async with self.lock:
            if symbol not in self.prices:
                self.prices[symbol] = []
            self.prices[symbol].append((timestamp, price))
            await self._cleanup_old_prices(symbol)
    
    def get_price_at_time(self, symbol: str, target_time: datetime) -> Optional[dict]:
        """Get the closest price to the target time within match_minutes window"""
        if symbol not in self.prices:
            return None

        # Convert times to UTC for comparison
        if not target_time.tzinfo:
            target_time = pytz.UTC.localize(target_time)
        
        match_window = timedelta(minutes=self.match_minutes)
        closest_price = None
        min_diff = match_window

        for ts, price in self.prices[symbol]:
            if not ts.tzinfo:
                ts = pytz.UTC.localize(ts)
            
            time_diff = abs(ts - target_time)
            if time_diff <= match_window and time_diff < min_diff:
                closest_price = {'timestamp': ts, 'price': price}
                min_diff = time_diff

        return closest_price

    async def _cleanup_old_prices(self, symbol: str):
        """Remove prices older than the window"""
        if symbol not in self.prices:
            return

        cutoff = datetime.now(pytz.UTC) - timedelta(days=self.window_days)
        self.prices[symbol] = [(ts, price) for ts, price in self.prices[symbol] 
                             if ts > cutoff]
        
    async def cleanup(self):
        """Clean up old prices for all symbols"""
        async with self.lock:
            for symbol in list(self.prices.keys()):
                await self._cleanup_old_prices(symbol)
                if not self.prices[symbol]:  # Remove empty lists
                    del self.prices[symbol]
