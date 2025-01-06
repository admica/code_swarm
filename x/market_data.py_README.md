# market_data.py


## Functions

### `__new__(cls)`


## Classes

### `StockQuote`

Real-time stock quote data

### `CompanyProfile`

Company profile and market data

### `MarketMetrics`

Key market metrics for a stock

### `EarningsInfo`

Upcoming earnings information

### `FinnhubClient`

Client for interacting with Finnhub API

#### Methods

- `__init__(api_key)`

### `MarketDataManager`

Manager for handling market data updates and database interactions

#### Methods

- `__new__(cls)`
- `__init__()`: Sync initialization (minimal).


## Dependencies

- aiohttp
- asyncio
- asyncpg
- dataclasses.dataclass
- datetime.datetime
- datetime.timedelta
- logging
- typing.Dict
- typing.List
- typing.Optional
- typing.Set
- utils.config.get_config
- utils.config.get_db_config
