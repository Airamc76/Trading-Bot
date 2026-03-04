import feedparser
import logging
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

# Fuentes de noticias (RSS)
RSS_FEEDS = {
    "CRYPTO": [
        "https://cointelegraph.com/rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/"
    ],
    "FOREX": [
        "https://www.investing.com/rss/news_1.rss",
        "https://www.cnbc.com/id/15839069/device/rss/rss.html"
    ]
}

analyzer = SentimentIntensityAnalyzer()

def get_market_sentiment():
    """
    Obtiene noticias recientes y calcula un score de sentimiento promedio.
    Retorna un dict con el sentimiento por categoría.
    """
    sentiment_results = {"CRYPTO": 0.0, "FOREX": 0.0}
    
    for category, urls in RSS_FEEDS.items():
        total_score = 0
        count = 0
        
        for url in urls:
            try:
                feed = feedparser.parse(url)
                # Tomamos los últimos 5 artículos de cada feed
                for entry in feed.entries[:5]:
                    text = entry.title + " " + entry.get("summary", "")
                    vs = analyzer.polarity_scores(text)
                    total_score += vs['compound']
                    count += 1
            except Exception as e:
                logger.warning(f"Error parsing feed {url}: {e}")
        
        if count > 0:
            sentiment_results[category] = total_score / count
            
    logger.info(f"📊 Sentimiento detectado -> CRYPTO: {sentiment_results['CRYPTO']:.2f}, FOREX: {sentiment_results['FOREX']:.2f}")
    return sentiment_results
