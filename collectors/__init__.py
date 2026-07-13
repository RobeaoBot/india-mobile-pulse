"""
India Mobile Pulse - Collectors Package
"""
from collectors.reddit import RedditCollector
from collectors.youtube import YouTubeCollector
from collectors.news import NewsCollector
from collectors.official import OfficialCollector

ALL_COLLECTORS = [RedditCollector, YouTubeCollector, NewsCollector, OfficialCollector]
