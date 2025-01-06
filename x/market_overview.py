# PATH: ./backend/market_overview.py
from fastapi import Query, HTTPException
from typing import List
from datetime import datetime, timedelta
from collector import get_app, get_collector
import logging

app = get_app()
collector = get_collector()

@app.get("/market-overview")
async def get_market_overview(hours: int = Query(default=24, ge=1, le=168)):
    """
    Get market overview statistics including distributions of mentions by subreddit,
    sentiment, and top mentioned symbols
    """
    if hours < 1 or hours > 168:
        raise HTTPException(status_code=400, detail="Hours must be between 1 and 168")

    async with collector.db_pool.acquire() as conn:
        # Get subreddit distribution (top 5)
        subreddit_distribution = await conn.fetch("""
            SELECT 
                subreddit as name,
                COUNT(*) as value
            FROM mentions
            WHERE mentioned_at > NOW() - ($1::integer * interval '1 hour')
            GROUP BY subreddit
            ORDER BY value DESC
            LIMIT 5
        """, hours)
        subreddit_distribution = [{"name": row['name'], "value": row['value']} for row in subreddit_distribution]
        logging.info(f"Subreddit distribution: {subreddit_distribution}")
        
        # Get sentiment distribution
        sentiment_distribution = await conn.fetch("""
            SELECT
                CASE 
                    WHEN sentiment_score >= 0.2 THEN 'Bullish'
                    WHEN sentiment_score <= -0.2 THEN 'Bearish'
                    ELSE 'Neutral'
                END as name,
                COUNT(*) as value
            FROM mentions
            WHERE mentioned_at > NOW() - ($1::integer * interval '1 hour')
            GROUP BY 
                CASE 
                    WHEN sentiment_score >= 0.2 THEN 'Bullish'
                    WHEN sentiment_score <= -0.2 THEN 'Bearish'
                    ELSE 'Neutral'
                END
            ORDER BY value DESC
        """, hours)
        sentiment_distribution = [{"name": row['name'], "value": row['value']} for row in sentiment_distribution]
        logging.info(f"Sentiment distribution: {sentiment_distribution}")
        
        # Get top mentioned symbols with their type and average sentiment
        symbol_distribution = await conn.fetch("""
            SELECT 
                symbol as name,
                COUNT(*) as value,
                type as category,
                ROUND(AVG(sentiment_score)::numeric, 2) as sentiment
            FROM mentions
            WHERE mentioned_at > NOW() - ($1::integer * interval '1 hour')
            GROUP BY symbol, type
            ORDER BY value DESC
            LIMIT 10
        """, hours)
        symbol_distribution = [{
            "name": row['name'],
            "value": row['value'],
            "category": row['category'],
            "sentiment": row['sentiment']
        } for row in symbol_distribution]
        logging.info(f"Symbol distribution: {symbol_distribution}")
        
        return {
            "subreddit_distribution": subreddit_distribution,
            "sentiment_distribution": sentiment_distribution,
            "symbol_distribution": symbol_distribution
        }