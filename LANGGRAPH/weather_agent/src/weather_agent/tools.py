from langchain_tavily import TavilySearch

from weather_agent.config import settings


def build_search_tool(max_results: int = 5) -> TavilySearch:
    return TavilySearch(api_key=settings.tavily_api_key, max_results=max_results)
