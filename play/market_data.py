#!/usr/bin/env python3
import asyncio
import aiohttp
import asyncpg
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Dict, List, Set
from utils.config import get_config, get_db_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class StockQuote:
    """Real-time stock quote data"""
    symbol: str
    current_price: float
    high_price: float
    low_price: float
    previous_close: float
    timestamp: datetime

@dataclass
class CompanyProfile:
    """Company profile and market data"""
    symbol: str
    name: str
    industry: str
    market_cap_b: float  # In billions
    shares_outstanding_m: float  # In millions
    ipo_date: Optional[datetime]
    exchange: str

@dataclass
class MarketMetrics:
    """Key market metrics for a stock"""
    symbol: str
    beta: float
    week52_high: float
    week52_low: float
    avg_volume_10d: float
    dividend_yield: Optional[float]

@dataclass
class EarningsInfo:
    """Upcoming earnings information"""
    symbol: str
    date: datetime
    estimate: Optional[float]
    time: str  # 'bmo' (before market), 'amc' (after market), or 'dmh' (during)

class FinnhubClient:
    """Client for interacting with Finnhub API"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://finnhub.io/api/v1"
        self._session = None
        self._request_semaphore = asyncio.Semaphore(30)  # Rate limit: 30 requests/second
    
    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure aiohttp session exists and return it"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers={
                'X-Finnhub-Token': self.api_key
            })
        return self._session
    
    async def close(self):
        """Close the client session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make a rate-limited request to Finnhub API"""
        session = await self._ensure_session()
        url = f"{self.base_url}/{endpoint}"
        
        async with self._request_semaphore:  # Handle rate limiting
            try:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Finnhub API error: {response.status} for {endpoint}")
                        return {}
                    return await response.json()
            except Exception as e:
                logger.error(f"Error making request to {endpoint}: {e}")
                return {}

    async def get_quote(self, symbol: str) -> Optional[StockQuote]:
        """Get real-time quote for a symbol"""
        data = await self._make_request('quote', {'symbol': symbol})
        if not data or 'c' not in data:
            return None
            
        return StockQuote(
            symbol=symbol,
            current_price=float(data['c']),
            high_price=float(data['h']),
            low_price=float(data['l']),
            previous_close=float(data['pc']),
            timestamp=datetime.fromtimestamp(data['t'])
        )

    async def get_company_profile(self, symbol: str) -> Optional[CompanyProfile]:
        """Get company profile data"""
        data = await self._make_request('stock/profile2', {'symbol': symbol})
        if not data or 'name' not in data:
            return None
            
        try:
            ipo_date = datetime.strptime(data.get('ipo', ''), '%Y-%m-%d') if data.get('ipo') else None
        except ValueError:
            ipo_date = None
            
        return CompanyProfile(
            symbol=symbol,
            name=data['name'],
            industry=data.get('finnhubIndustry', 'Unknown'),
            market_cap_b=float(data.get('marketCapitalization', 0)),
            shares_outstanding_m=float(data.get('shareOutstanding', 0)),
            ipo_date=ipo_date,
            exchange=data.get('exchange', 'Unknown')
        )

    async def get_market_metrics(self, symbol: str) -> Optional[MarketMetrics]:
        """Get key market metrics"""
        data = await self._make_request('stock/metric', {'symbol': symbol, 'metric': 'all'})
        if not data or 'metric' not in data:
            return None
            
        metrics = data['metric']
        try:
            dividend_yield = float(metrics.get('currentDividendYieldTTM', 0))
        except (ValueError, TypeError):
            dividend_yield = None
            
        return MarketMetrics(
            symbol=symbol,
            beta=float(metrics.get('beta', 0)),
            week52_high=float(metrics.get('52WeekHigh', 0)),
            week52_low=float(metrics.get('52WeekLow', 0)),
            avg_volume_10d=float(metrics.get('10DayAverageTradingVolume', 0)),
            dividend_yield=dividend_yield
        )

    async def get_earnings(self, symbol: str) -> Optional[EarningsInfo]:
        """Get upcoming earnings information"""
        # Get earnings for next 30 days
        from_date = datetime.now().strftime('%Y-%m-%d')
        to_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        
        data = await self._make_request('calendar/earnings', {
            'symbol': symbol,
            'from': from_date,
            'to': to_date
        })
        
        if not data or 'earningsCalendar' not in data or not data['earningsCalendar']:
            return None
            
        earnings = data['earningsCalendar'][0]  # Get next earnings event
        try:
            date = datetime.strptime(earnings['date'], '%Y-%m-%d')
            estimate = float(earnings.get('epsEstimate')) if earnings.get('epsEstimate') else None
        except (ValueError, TypeError):
            return None
            
        return EarningsInfo(
            symbol=symbol,
            date=date,
            estimate=estimate,
            time=earnings.get('hour', 'unknown')
        )

    async def get_all_market_data(self, symbol: str) -> Dict:
        """Get all market data for a symbol in a single call"""
        tasks = [
            self.get_quote(symbol),
            self.get_company_profile(symbol),
            self.get_market_metrics(symbol),
            self.get_earnings(symbol)
        ]
        
        quote, profile, metrics, earnings = await asyncio.gather(*tasks)
        
        return {
            'quote': quote,
            'profile': profile,
            'metrics': metrics,
            'earnings': earnings,
            'timestamp': datetime.now()
        }

class MarketDataManager:
    """Manager for handling market data updates and database interactions"""
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Sync initialization (minimal)"""
        self.finnhub_client = None
        self.db_pool = None
        self._symbol_update_lock = None
        self._profile_cache = {}
        self._last_profile_update = {}
    
    @classmethod
    async def create(cls):
        """Async factory method for initialization"""
        if cls._initialized:
            return cls._instance
            
        instance = cls()
        await instance._async_init()
        return instance
    
    async def _async_init(self):
        """Async initialization"""
        if MarketDataManager._initialized:
            return
            
        config = get_config()
        db_config = get_db_config()
        
        self.finnhub_client = FinnhubClient(config["market_apis"]["finnhub_key"])
        self.db_pool = await asyncpg.create_pool(**db_config)
        self._symbol_update_lock = asyncio.Lock()
        
        MarketDataManager._initialized = True
        logger.info("MarketDataManager initialized")

    async def close(self):
        """Close all connections"""
        await self.finnhub_client.close()
        await self.db_pool.close()
    
    async def update_symbol_profile(self, symbol: str, force: bool = False) -> Optional[CompanyProfile]:
        """Update symbol profile in database"""
        async with self._symbol_update_lock:
            # Check cache first
            if not force and symbol in self._profile_cache:
                last_update = self._last_profile_update.get(symbol)
                if last_update and (datetime.now() - last_update).total_seconds() < 86400:  # 24h cache
                    return self._profile_cache[symbol]
            
            # Get fresh data
            profile = await self.finnhub_client.get_company_profile(symbol)
            metrics = await self.finnhub_client.get_market_metrics(symbol)
            
            if not profile:
                return None
                
            # Update database
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE symbols 
                    SET company_name = $2,
                        industry = $3,
                        market_cap_b = $4,
                        shares_outstanding_m = $5,
                        ipo_date = $6,
                        exchange = $7,
                        beta = $8,
                        last_updated = NOW()
                    WHERE symbol = $1
                """, symbol, profile.name, profile.industry, profile.market_cap_b,
                     profile.shares_outstanding_m, profile.ipo_date, profile.exchange,
                     metrics.beta if metrics else None)
            
            # Update cache
            self._profile_cache[symbol] = profile
            self._last_profile_update[symbol] = datetime.now()
            
            return profile
    
    async def record_stock_price(self, symbol: str, quote: StockQuote):
        """Record a stock price point"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO stock_prices 
                (symbol, timestamp, price_usd, daily_high, daily_low, previous_close, volume, market_cap_b)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (symbol, timestamp) DO UPDATE
                SET price_usd = EXCLUDED.price_usd,
                    daily_high = EXCLUDED.daily_high,
                    daily_low = EXCLUDED.daily_low,
                    previous_close = EXCLUDED.previous_close,
                    volume = EXCLUDED.volume,
                    market_cap_b = EXCLUDED.market_cap_b
            """, symbol, quote.timestamp, quote.current_price, quote.high_price,
                 quote.low_price, quote.previous_close, None,  # Volume not available in quote
                 self._profile_cache.get(symbol).market_cap_b if symbol in self._profile_cache else None)
    
    async def enrich_mention(self, mention_id: int, symbol: str):
        """Enrich a mention with market data"""
        # Get all market data
        data = await self.finnhub_client.get_all_market_data(symbol)
        if not data['quote']:
            return
            
        quote = data['quote']
        metrics = data['metrics']
        earnings = data['earnings']
        
        # Update mention with market context
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE mentions 
                SET price_at_mention = $2,
                    daily_high = $3,
                    daily_low = $4,
                    previous_close = $5,
                    volume_10d_avg = $6,
                    next_earnings_date = $7,
                    next_earnings_estimate = $8,
                    market_cap_at_mention = $9,
                    beta_at_mention = $10
                WHERE id = $1
            """, mention_id, quote.current_price, quote.high_price, quote.low_price,
                 quote.previous_close,
                 metrics.avg_volume_10d if metrics else None,
                 earnings.date if earnings else None,
                 earnings.estimate if earnings else None,
                 self._profile_cache.get(symbol).market_cap_b if symbol in self._profile_cache else None,
                 metrics.beta if metrics else None)
        
        # Record price point
        await self.record_stock_price(symbol, quote)
    
    async def get_stock_symbols(self) -> Set[str]:
        """Get all stock symbols from database"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT symbol FROM symbols WHERE type = 'stock'")
            return {row['symbol'] for row in rows}
    
    async def update_all_profiles(self):
        """Update all stock symbol profiles"""
        symbols = await self.get_stock_symbols()
        for symbol in symbols:
            try:
                await self.update_symbol_profile(symbol, force=True)
                await asyncio.sleep(0.1)  # Rate limiting
            except Exception as e:
                logger.error(f"Error updating profile for {symbol}: {e}")

async def test_manager():
    """Test the MarketDataManager"""
    manager = await MarketDataManager.create()
    
    try:
        # Test profile updates
        symbols = ['AAPL', 'MSFT', 'GOOGL']
        for symbol in symbols:
            logger.info(f"\nUpdating profile for {symbol}...")
            profile = await manager.update_symbol_profile(symbol)
            if profile:
                logger.info(f"Updated {profile.name} ({profile.industry})")
                
            # Test price recording
            quote = await manager.finnhub_client.get_quote(symbol)
            if quote:
                logger.info(f"Recording price: ${quote.current_price:.2f}")
                await manager.record_stock_price(symbol, quote)
            
            await asyncio.sleep(0.1)
            
    finally:
        await manager.close()

if __name__ == "__main__":
    # Update test function to use manager
    asyncio.run(test_manager()) 