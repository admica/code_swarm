# price_tracker.py


## Functions

### `is_market_hours(self, timestamp)`

Check if the given timestamp is during market hours (9:30 AM - 4:00 PM ET, Mon-Fri)


## Classes

### `CryptoPrice`

Represents a crypto price point from an exchange

### `MockCryptoTracker`

Simulates crypto price tracking with mock data for testing

#### Methods

- `__init__()`

### `PriceDatabase`

Handles database operations for price storage

#### Methods

- `__init__(pool)`

### `PriceCollector`

#### Methods

- `__init__(db_pool)`
- `is_market_hours(timestamp)`: Check if the given timestamp is during market hours (9:30 AM - 4:00 PM ET, Mon-Fri).


## Dependencies

- asyncio
- asyncpg
- backend.cache.PriceCache
- dataclasses.dataclass
- datetime.datetime
- datetime.time
- datetime.timedelta
- logging
- pytz
- random
- stock_price_tracker.StockPrice
- stock_price_tracker.StockPriceTracker
- traceback
- typing.Dict
- typing.List
- typing.Optional
- typing.Tuple
- utils.config.get_config
- utils.config.get_db_config
