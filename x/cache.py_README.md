# cache.py

## Overview

The `PriceCache` class is a Python implementation of a price data caching system, designed to store recent price data for various symbols. It provides methods for adding new prices, retrieving all prices, and finding the closest price within a specified time window.


## Classes

### `PriceCache`

Cache for storing recent price data

#### Methods

- `__init__(window_days, match_minutes)`: Initialize price cache with window and matching parameters.
- `get_all_prices()`: Get all prices currently in the cache.
- `get_price_at_time(symbol, target_time)`: Get the closest price to the target time within match_minutes window.

