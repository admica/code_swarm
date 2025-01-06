# PATH: ./backend/recent_mentions.py
from fastapi import APIRouter, Query
from typing import List
from datetime import datetime, timedelta
from db import get_db_connection

router = APIRouter()

@router.get("/recent-mentions")
async def get_recent_mentions(
    lookback_hours: int = Query(default=24, ge=1, le=168),
    min_mentions: int = Query(default=3, ge=1)
):
    """
    Get recent mentions for all symbols with basic stats
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            query = """
            WITH mention_stats AS (
                SELECT 
                    symbol,
                    COUNT(*) as mention_count,
                    COUNT(DISTINCT subreddit) as subreddit_count,
                    AVG(sentiment_score) as avg_sentiment,
                    SUM(CASE WHEN sentiment_score > 0.2 THEN 1 ELSE 0 END) as bullish_count,
                    SUM(CASE WHEN sentiment_score < -0.2 THEN 1 ELSE 0 END) as bearish_count
                FROM mentions 
                WHERE mentioned_at > NOW() - interval '%s hours'
                GROUP BY symbol
                HAVING COUNT(*) >= %s
            )
            SELECT 
                m.symbol,
                COALESCE(s.type, 'UNKNOWN') as type,
                m.mention_count,
                m.subreddit_count,
                m.avg_sentiment,
                m.bullish_count,
                m.bearish_count
            FROM mention_stats m
            LEFT JOIN symbols s ON m.symbol = s.symbol
            ORDER BY m.mention_count DESC
            LIMIT 100;
            """
            
            cur.execute(query, (lookback_hours, min_mentions))
            results = cur.fetchall()
            
            return [{
                'symbol': row[0],
                'type': row[1],
                'mentions': row[2],
                'subreddits': row[3],
                'avgSentiment': float(row[4]) if row[4] is not None else 0.0,
                'bullishCount': row[5],
                'bearishCount': row[6]
            } for row in results]
            
    finally:
        conn.close() 