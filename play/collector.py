import asyncio
import logging
from datetime import datetime, time, timedelta
import pytz
import aiohttp
from typing import Optional, Dict, List
from utils.config import get_config
from backend.cache import PriceCache
from utils.market_utils import get_market_time

logger = logging.getLogger(__name__)

class PriceCollector:
    """Collects and stores price data for stocks and cryptocurrencies"""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
        self.price_queue = asyncio.Queue()
        self.running = False
        self.tasks = []
        self.price_cache = PriceCache()
        
        # Configure collection intervals
        self.collection_interval = 60  # Collect prices every 60 seconds
        self.cleanup_interval = 3600   # Clean old prices every hour
        self.rate_limit_delay = 1.0    # Delay between API calls in seconds
        
        # Track symbols we're actively collecting
        self.active_symbols = set()
        
        # Configure market hours (EST)
        self.market_open = time(9, 30)   # 9:30 AM
        self.market_close = time(16, 0)  # 4:00 PM
        self.est_tz = pytz.timezone('US/Eastern')
        
        # Rate limiting lock
        self.api_lock = asyncio.Lock()
    
    async def start(self):
        """Start the price collection system"""
        if self.running:
            return
            
        self.running = True
        
        # Start collection tasks
        self.tasks.extend([
            asyncio.create_task(self._run_continuous_collection()),
            asyncio.create_task(self._process_queue()),
            asyncio.create_task(self._cleanup_old_prices())
        ])
    
    async def stop(self):
        """Stop the price collection system"""
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
            
        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
    
    def _is_market_open(self, timestamp: datetime) -> bool:
        """Check if the market is open at the given timestamp"""
        if not timestamp.tzinfo:
            timestamp = pytz.UTC.localize(timestamp)
            
        # Convert to EST
        est_time = timestamp.astimezone(self.est_tz)
        
        # Check if weekend
        if est_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
            
        # Check market hours
        current_time = est_time.time()
        return self.market_open <= current_time < self.market_close
    
    async def queue_price_lookup(self, symbol: str, asset_type: str, timestamp: datetime):
        """Queue a price lookup request"""
        if not timestamp.tzinfo:
            timestamp = pytz.UTC.localize(timestamp)
            
        # Add to queue
        await self.price_queue.put({
            'symbol': symbol,
            'asset_type': asset_type,
            'timestamp': timestamp
        })
        
        # Track symbol for continuous collection if it's a stock
        if asset_type == 'stock':
            self.active_symbols.add(symbol)
            logger.info(f"Added {symbol} to active symbols for continuous collection")
            
        logger.info(f"Queued price lookup for {symbol} at {timestamp}")
    
    async def _run_continuous_collection(self):
        """Continuously collect prices for active symbols during market hours"""
        while self.running:
            try:
                # Use test time for continuous collection
                now = get_market_time()
                
                # Only collect during market hours
                if self._is_market_open(now):
                    logger.info(f"Starting collection cycle for {len(self.active_symbols)} symbols")
                    for symbol in self.active_symbols:
                        # Get current price with rate limiting
                        try:
                            async with self.api_lock:
                                price = await self._get_stock_price(symbol)
                                if price:
                                    # Store in cache
                                    await self.price_cache.add_price(symbol, price, now)
                                    
                                    # Store in database
                                    async with self.db_pool.acquire() as conn:
                                        await conn.execute("""
                                            INSERT INTO stock_prices (symbol, price_usd, timestamp)
                                            VALUES ($1, $2, $3)
                                        """, symbol, price, now)
                                        
                                    logger.info(f"Collected price for {symbol}: ${price}")
                                else:
                                    logger.warning(f"No price returned for {symbol}")
                                
                                # Rate limiting delay
                                await asyncio.sleep(self.rate_limit_delay)
                                
                        except Exception as e:
                            logger.error(f"Error collecting price for {symbol}: {e}")
                else:
                    logger.debug(f"Outside market hours ({now} ET), skipping price collection")
                
                # Wait before next collection cycle
                await asyncio.sleep(self.collection_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in continuous collection: {e}")
                await asyncio.sleep(self.collection_interval)
    
    async def _process_queue(self):
        """Process queued price lookups"""
        while self.running:
            try:
                # Get request from queue
                request = await self.price_queue.get()
                symbol = request['symbol']
                asset_type = request['asset_type']
                timestamp = request['timestamp']
                
                try:
                    if asset_type == 'stock':
                        # Check if during market hours for stocks
                        if not self._is_market_open(timestamp):
                            logger.info(f"Skipping {symbol} lookup - outside market hours: {timestamp}")
                            continue
                            
                        # Try to find matching price in cache
                        cached_price = self.price_cache.get_price_at_time(symbol, timestamp)
                        
                        if cached_price:
                            # Store mention with matched price
                            async with self.db_pool.acquire() as conn:
                                await conn.execute("""
                                    UPDATE stock_prices 
                                    SET mention_timestamp = $1
                                    WHERE symbol = $2 
                                    AND timestamp = $3
                                """, timestamp, symbol, cached_price['timestamp'])
                                
                            logger.info(f"Matched {symbol} mention at {timestamp} with price from {cached_price['timestamp']}")
                        else:
                            # Try to get historical price
                            async with self.api_lock:
                                price = await self._get_stock_price(symbol)
                                if price:
                                    async with self.db_pool.acquire() as conn:
                                        await conn.execute("""
                                            INSERT INTO stock_prices (symbol, price_usd, timestamp, mention_timestamp)
                                            VALUES ($1, $2, $3, $4)
                                        """, symbol, price, timestamp, timestamp)
                                    logger.info(f"Stored new price for {symbol} mention: ${price} at {timestamp}")
                                else:
                                    logger.warning(f"Could not get price for {symbol} at {timestamp}")
                                    
                                await asyncio.sleep(self.rate_limit_delay)
                    
                    elif asset_type == 'crypto':
                        # Get current price for crypto with rate limiting
                        async with self.api_lock:
                            price = await self._get_crypto_price(symbol)
                            if price:
                                async with self.db_pool.acquire() as conn:
                                    await conn.execute("""
                                        INSERT INTO crypto_prices (symbol, price_usd, timestamp)
                                        VALUES ($1, $2, $3)
                                    """, symbol, price, timestamp)
                                logger.info(f"Stored crypto price for {symbol}: ${price} at {timestamp}")
                            else:
                                logger.warning(f"Could not get crypto price for {symbol}")
                            
                            await asyncio.sleep(self.rate_limit_delay)
                
                except Exception as e:
                    logger.error(f"Error processing request for {symbol}: {e}")
                
                finally:
                    self.price_queue.task_done()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in queue processing: {e}")
                await asyncio.sleep(1)
    
    async def _cleanup_old_prices(self):
        """Clean up old prices from cache and database"""
        while self.running:
            try:
                # Clean cache
                self.price_cache.cleanup()
                
                # Clean database
                async with self.db_pool.acquire() as conn:
                    # Keep 5 days of data
                    await conn.execute("""
                        DELETE FROM stock_prices 
                        WHERE timestamp < NOW() - interval '5 days'
                    """)
                    await conn.execute("""
                        DELETE FROM crypto_prices 
                        WHERE timestamp < NOW() - interval '5 days'
                    """)
                
                # Wait for next cleanup
                await asyncio.sleep(self.cleanup_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup: {e}")
                await asyncio.sleep(self.cleanup_interval)
    
    async def _get_stock_price(self, symbol: str) -> Optional[float]:
        """Get current stock price from Finnhub"""
        try:
            config = get_config()
            async with aiohttp.ClientSession() as session:
                url = f"https://finnhub.io/api/v1/quote"
                params = {
                    'symbol': symbol,
                    'token': config['market_apis']['finnhub_key']
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('c')  # Current price
                    else:
                        logger.error(f"Finnhub API error: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error getting stock price: {e}")
            return None
    
    async def _get_crypto_price(self, symbol: str) -> Optional[float]:
        """Get current crypto price from Finnhub"""
        try:
            config = get_config()
            async with aiohttp.ClientSession() as session:
                url = f"https://finnhub.io/api/v1/crypto/candle"
                params = {
                    'symbol': f"BINANCE:{symbol}USDT",
                    'resolution': '1',
                    'token': config['market_apis']['finnhub_key'],
                    'from': int(datetime.now().timestamp()) - 60,
                    'to': int(datetime.now().timestamp())
                }
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('c'):
                            return data['c'][-1]  # Last closing price
                    else:
                        logger.error(f"Finnhub API error: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error getting crypto price: {e}")
            return None
    
    def get_cache_contents(self):
        """Get the current contents of the price cache"""
        cache_contents = {}
        for symbol, prices in self.price_cache.prices.items():
            # Sort prices by timestamp
            sorted_prices = sorted(prices, key=lambda x: x['timestamp'])
            
            # Get statistics
            if sorted_prices:
                latest_price = sorted_prices[-1]
                oldest_price = sorted_prices[0]
                price_count = len(sorted_prices)
                
                cache_contents[symbol] = {
                    'latest_price': {
                        'price': latest_price['price'],
                        'timestamp': latest_price['timestamp'].isoformat()
                    },
                    'oldest_price': {
                        'price': oldest_price['price'],
                        'timestamp': oldest_price['timestamp'].isoformat()
                    },
                    'price_count': price_count,
                    'time_range': (latest_price['timestamp'] - oldest_price['timestamp']).total_seconds() / 3600.0  # hours
                }
        
        return {
            'cache_stats': {
                'total_symbols': len(cache_contents),
                'total_prices': sum(info['price_count'] for info in cache_contents.values()),
                'active_symbols': list(self.active_symbols)
            },
            'symbols': cache_contents
        }
    
    def get_symbol_prices(self, symbol: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None):
        """Get cached prices for a specific symbol within an optional time range"""
        if symbol not in self.price_cache.prices:
            return None
            
        prices = self.price_cache.prices[symbol]
        
        # Filter by time range if specified
        if start_time or end_time:
            filtered_prices = []
            for price_data in prices:
                timestamp = price_data['timestamp']
                if start_time and timestamp < start_time:
                    continue
                if end_time and timestamp > end_time:
                    continue
                filtered_prices.append({
                    'price': price_data['price'],
                    'timestamp': timestamp.isoformat()
                })
            return filtered_prices
            
        # Return all prices if no time range specified
        return [{
            'price': p['price'],
            'timestamp': p['timestamp'].isoformat()
        } for p in prices] 