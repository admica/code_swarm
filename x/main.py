# PATH: ./backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import endpoints after app is created
from momentum_endpoints import *
from pattern_endpoints import *
from correlation_endpoints import *
from recent_mentions import *
from market_overview import *