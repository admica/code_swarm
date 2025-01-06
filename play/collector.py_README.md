# collector.py

## Overview


## Classes

### `PriceCollector`

Collects and stores price data for stocks and cryptocurrencies

#### Methods

- `__init__(db_pool)`
- `_is_market_open(timestamp)`: Check if the market is open at the given timestamp.
- `get_cache_contents()`: Get the current contents of the price cache.
- `get_symbol_prices(symbol, start_time, end_time)`: Get cached prices for a specific symbol within an optional time range.

