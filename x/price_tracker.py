from dataclasses import dataclass
from datetime import datetime, timedelta, time
import asyncio
import logging
import random
from typing import List, Dict, Optional, Tuple
import asyncpg
from utils.config import get_db_config, get_config
from stock_price_tracker import StockPriceTracker, StockPrice
from backend.cache import PriceCache
import pytz
import traceback

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

@dataclass
class CryptoPrice:
    """Represents a crypto price point from an exchange"""
    symbol: str
    timestamp: datetime
    exchange: str
    price_usd: float
    volume_24h: float

class MockCryptoTracker:
    """Simulates crypto price tracking with mock data for testing"""
    def __init__(self):
        self.exchanges = ['binance', 'coinbase', 'kraken']
        self.crypto_base_prices = {
            'BTC': 42000.0,
            'ETH': 2200.0,
            'DOGE': 0.08,
        }
        self.exchange_variance = 0.02
        self.crypto_volume_ranges = {
            'BTC': (1000, 5000),
            'ETH': (10000, 50000),
            'DOGE': (1000000, 5000000),
        }

    async def get_crypto_price(self, symbol: str, timestamp: datetime) -> List[CryptoPrice]:
        """Get mock crypto prices from all exchanges"""
        logger.debug(f"Generating mock crypto prices for {symbol} at {timestamp}")
        base_price = self.crypto_base_prices.get(symbol, 100.0)
        volume_range = self.crypto_volume_ranges.get(symbol, (1000, 5000))
        
        prices = []
        for exchange in self.exchanges:
            variance = random.uniform(-self.exchange_variance, self.exchange_variance)
            price = base_price * (1 + variance)
            volume = random.uniform(*volume_range)
            
            prices.append(CryptoPrice(
                symbol=symbol,
                timestamp=timestamp,
                exchange=exchange,
                price_usd=round(price, 8),
                volume_24h=round(volume, 2)
            ))
            logger.debug(f"Generated {exchange} price for {symbol}: ${price:.2f}")
        
        return prices

class PriceDatabase:
    """Handles database operations for price storage"""
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def store_crypto_price(self, price: CryptoPrice):
        """Store crypto price in database with transaction"""
        logger.info(f"Storing crypto price for {price.symbol}: ${price.price_usd:.2f} on {price.exchange}")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    await conn.execute("""
                        INSERT INTO crypto_prices 
                        (symbol, timestamp, exchange, price_usd, volume_24h)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (symbol, timestamp, exchange) 
                        DO UPDATE SET 
                            price_usd = EXCLUDED.price_usd,
                            volume_24h = EXCLUDED.volume_24h
                    """, price.symbol, price.timestamp, price.exchange,
                         price.price_usd, price.volume_24h)
                    logger.info(f"Successfully stored crypto price for {price.symbol}")
                except Exception as e:
                    logger.error(f"Error storing crypto price for {price.symbol}: {str(e)}")
                    logger.error(f"Stack trace: {traceback.format_exc()}")
                    raise

    async def store_stock_price(self, price: StockPrice, mention_timestamp: Optional[datetime] = None):
        """Store stock price in database with transaction"""
        logger.info(f"Storing stock price for {price.symbol}: ${price.price_usd:.2f}")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    await conn.execute("""
                        INSERT INTO stock_prices 
                        (symbol, timestamp, mention_timestamp, price_usd, daily_high, daily_low, 
                         previous_close, market_cap_b, beta)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """, price.symbol, price.timestamp, mention_timestamp, price.price_usd,
                         price.daily_high, price.daily_low, price.previous_close,
                         price.market_cap_b, price.beta)
                    logger.info(f"Successfully stored stock price data for {price.symbol}")
                    
                    if price.market_cap_b is not None or price.beta is not None:
                        logger.debug(f"Updating symbol metadata for {price.symbol}")
                        await conn.execute("""
                            UPDATE symbols
                            SET market_cap_b = COALESCE($2, market_cap_b),
                                beta = COALESCE($3, beta),
                                last_updated = NOW()
                            WHERE symbol = $1
                        """, price.symbol, price.market_cap_b, price.beta)
                        logger.info(f"Updated symbol metadata for {price.symbol}")
                except Exception as e:
                    logger.error(f"Error storing stock price for {price.symbol}: {str(e)}")
                    logger.error(f"Stack trace: {traceback.format_exc()}")
                    raise

class PriceCollector:
    def __init__(self, db_pool: asyncpg.Pool):
        config = get_config()
        self.cache_window_days = int(config.get('price_tracking', 'cache_window_days', fallback='5'))
        self.price_match_minutes = int(config.get('price_tracking', 'price_match_minutes', fallback='3'))
        self.collection_interval = 60  # Collect prices every minute
        self.rate_limit_delay = 1.0  # 1 second between API calls

        # Components
        self.crypto_tracker = MockCryptoTracker()
        self.stock_tracker = StockPriceTracker()
        self.db = PriceDatabase(db_pool)
        self.price_queue = asyncio.Queue()
        self.price_cache = PriceCache(
            window_days=self.cache_window_days,
            match_minutes=self.price_match_minutes
        )
        self.tracked_symbols = set()  # Set of symbols to track prices for
        self.running = False
        self.worker_task = None
        self.price_collector_task = None
        self.api_lock = asyncio.Lock()  # Lock for rate limiting

    async def queue_price_lookup(self, symbol: str, asset_type: str, mention_timestamp: datetime):
        """Queue a price lookup request for a mention"""
        if asset_type == 'stock':
            self.tracked_symbols.add(symbol)  # Add to tracked symbols if it's a stock
            
        await self.price_queue.put({
            'symbol': symbol,
            'type': asset_type,
            'mention_timestamp': mention_timestamp
        })
        logger.info(f"Added price lookup to queue for {symbol} at {mention_timestamp}")
    
        queue_size = self.price_queue.qsize()
        if queue_size > 10:
            logger.warning(f"Price lookup queue size is high: {queue_size} items")

    def is_market_hours(self, timestamp: datetime) -> bool:
        """Check if the given timestamp is during market hours (9:30 AM - 4:00 PM ET, Mon-Fri)"""
        if not timestamp.tzinfo:
            timestamp = pytz.UTC.localize(timestamp)
        
        et_tz = pytz.timezone('US/Eastern')
        et_time = timestamp.astimezone(et_tz)
        
        # Check if it's a weekday (Monday = 0, Sunday = 6)
        if et_time.weekday() > 4:  # Saturday or Sunday
            return False
            
        # Convert to time object for hour/minute comparison
        market_time = et_time.time()
        market_open = time(9, 30)  # 9:30 AM ET
        market_close = time(16, 0)  # 4:00 PM ET
        
        return market_open <= market_time <= market_close

    async def continuous_price_collector(self):
        """Continuously collect stock prices during market hours"""
        while self.running:
            try:
                now = datetime.now(pytz.UTC)
                
                # Only collect during market hours
                if self.is_market_hours(now):
                    logger.debug(f"Collecting prices for {len(self.tracked_symbols)} symbols")
                    
                    # Collect prices for all tracked symbols
                    for symbol in self.tracked_symbols:
                        try:
                            async with self.api_lock:  # Ensure rate limiting
                                price_data = await self.stock_tracker.get_stock_price(symbol, now)
                                if price_data:
                                    # Store in cache
                                    self.price_cache.add_price(
                                        symbol,
                                        price_data.price_usd,
                                        price_data.timestamp
                                    )
                                    
                                    # Store in database
                                    await self.db.store_stock_price(price_data)
                                    logger.debug(f"Collected price for {symbol}: ${price_data.price_usd}")
                                
                                # Rate limiting delay
                                await asyncio.sleep(self.rate_limit_delay)
                                
                        except Exception as e:
                            logger.error(f"Error collecting price for {symbol}: {str(e)}")
                else:
                    logger.debug("Outside market hours, skipping price collection")
                
                # Wait before next collection cycle
                await asyncio.sleep(self.collection_interval)
                
            except Exception as e:
                logger.error(f"Error in continuous collection: {str(e)}")
                logger.error(f"Stack trace: {traceback.format_exc()}")
                await asyncio.sleep(self.collection_interval)

    async def price_worker(self):
        """Process mentions and store prices from cache"""
        while self.running:
            try:
                item = await self.price_queue.get()
                try:
                    if item['type'] == 'stock':
                        # Check if we have a cached price first
                        cached_data = self.price_cache.get_price_at_time(
                            item['symbol'],
                            item['mention_timestamp']
                        )
                        
                        if cached_data:
                            # Use cached price
                            price = cached_data['price']
                            price_timestamp = cached_data['timestamp']
                            price_data = StockPrice(
                                symbol=item['symbol'],
                                timestamp=price_timestamp,
                                price_usd=price,
                                daily_high=None,
                                daily_low=None,
                                previous_close=None,
                                market_cap_b=None,
                                beta=None
                            )
                            await self.db.store_stock_price(price_data, item['mention_timestamp'])
                            logger.info(f"Stored cached price for {item['symbol']} mention: ${price} at {price_timestamp}")
                        else:
                            # If during market hours, try to get current price
                            if self.is_market_hours(item['mention_timestamp']):
                                try:
                                    async with self.api_lock:  # Ensure rate limiting
                                        price_data = await self.stock_tracker.get_stock_price(
                                            item['symbol'],
                                            item['mention_timestamp']
                                        )
                                        if price_data:
                                            # Store in cache and database
                                            self.price_cache.add_price(
                                                item['symbol'],
                                                price_data.price_usd,
                                                price_data.timestamp
                                            )
                                            await self.db.store_stock_price(price_data, item['mention_timestamp'])
                                            logger.info(f"Stored live price for {item['symbol']} mention: ${price_data.price_usd}")
                                        
                                        # Rate limiting delay
                                        await asyncio.sleep(self.rate_limit_delay)
                                except Exception as e:
                                    logger.error(f"Error getting price for {item['symbol']}: {str(e)}")
                            else:
                                logger.debug(f"Mention for {item['symbol']} is outside market hours, skipping price lookup")

                    elif item['type'] == 'crypto':
                        prices = await self.crypto_tracker.get_crypto_price(
                            item['symbol'],
                            item['mention_timestamp']
                        )
                        for price in prices:
                            await self.db.store_crypto_price(price)

                finally:
                    self.price_queue.task_done()

            except Exception as e:
                logger.error(f"Error in price worker: {str(e)}")
                logger.error(f"Stack trace: {traceback.format_exc()}")
                await asyncio.sleep(1)

    async def start(self):
        """Start the price collection service"""
        self.running = True
        self.worker_task = asyncio.create_task(self.price_worker())
        self.price_collector_task = asyncio.create_task(self.continuous_price_collector())
        logger.info("Price collector started")

    async def stop(self):
        """Stop the price collection service"""
        logger.info("Stopping price collection service")
        self.running = False
        if self.worker_task:
            await self.price_queue.join()
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        if self.price_collector_task:
            self.price_collector_task.cancel()
            try:
                await self.price_collector_task
            except asyncio.CancelledError:
                pass

async def test_price_collector():
    """Test the price collection system"""
    config = get_db_config()
    pool = await asyncpg.create_pool(**config)
    
    collector = PriceCollector(pool)
    await collector.start()
    
    try:
        # Test continuous collection during market hours
        now = datetime.now(pytz.UTC)
        test_symbols = ['AAPL', 'MSFT', 'GOOGL']
        
        # Queue mentions for test symbols
        logger.info("\nTesting price collection and mention handling:")
        for symbol in test_symbols:
            # Queue a mention for now
            await collector.queue_price_lookup(symbol, 'stock', now)
            logger.info(f"Queued mention for {symbol} at {now}")
            
            # Queue a mention for 2 minutes ago
            past_time = now - timedelta(minutes=2)
            await collector.queue_price_lookup(symbol, 'stock', past_time)
            logger.info(f"Queued mention for {symbol} at {past_time}")
            
            # Queue a mention for outside market hours (should be skipped)
            outside_hours = now.replace(hour=3, minute=0)  # 3 AM
            await collector.queue_price_lookup(symbol, 'stock', outside_hours)
            logger.info(f"Queued mention for {symbol} at {outside_hours} (outside market hours)")
        
        # Let the collector run for a few cycles
        logger.info("\nWaiting for price collection cycles...")
        await asyncio.sleep(180)  # Wait 3 minutes
        
        # Queue some more mentions to test cache matching
        logger.info("\nTesting cache matching with new mentions:")
        for symbol in test_symbols:
            # Queue a mention for now (should match recently collected price)
            await collector.queue_price_lookup(symbol, 'stock', now + timedelta(seconds=30))
            logger.info(f"Queued new mention for {symbol}")
        
        # Wait for processing
        logger.info("\nWaiting for queue to empty...")
        await collector.price_queue.join()
        
        # Verify data storage
        async with pool.acquire() as conn:
            # Check stored prices
            stock_count = await conn.fetchval("""
                SELECT COUNT(*) FROM stock_prices 
                WHERE timestamp > NOW() - interval '5 minutes'
            """)
            
            # Check mentions with prices vs without
            with_prices = await conn.fetchval("""
                SELECT COUNT(*) FROM stock_prices 
                WHERE mention_timestamp IS NOT NULL 
                AND timestamp > NOW() - interval '5 minutes'
            """)
            
            logger.info(f"\nVerification Results:")
            logger.info(f"Total prices stored in last 5 minutes: {stock_count}")
            logger.info(f"Mentions with matched prices: {with_prices}")
            
            # Test some specific scenarios
            for symbol in test_symbols:
                latest = await conn.fetchrow("""
                    SELECT price_usd, timestamp, mention_timestamp 
                    FROM stock_prices 
                    WHERE symbol = $1 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """, symbol)
                
                if latest:
                    logger.info(f"{symbol} latest price: ${latest['price_usd']} at {latest['timestamp']}")
                    if latest['mention_timestamp']:
                        logger.info(f"  Matched with mention at: {latest['mention_timestamp']}")
    
    finally:
        await collector.stop()
        await pool.close()

if __name__ == "__main__":
    asyncio.run(test_price_collector())
