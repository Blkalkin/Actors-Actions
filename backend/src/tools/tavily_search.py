"""Tavily search integration for actor research and enrichment."""
from typing import List, Dict, Any, Optional
from src.config import TAVILY_API_KEY

# Initialize Tavily client if API key is available
tavily_client = None
if TAVILY_API_KEY:
    try:
        from tavily import TavilyClient
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        print("✅ Tavily search enabled")
    except ImportError:
        print("⚠️  tavily-python not installed - search disabled")
    except Exception as e:
        print(f"⚠️  Tavily initialization failed: {e}")
else:
    print("⚠️  TAVILY_API_KEY not found - search disabled")


def search_for_actor_context(query: str, max_results: int = 3) -> Optional[str]:
    """
    Search the web for context about an actor using Tavily.
    
    Args:
        query: Search query (e.g., actor's research_query)
        max_results: Maximum number of results to return
        
    Returns:
        Formatted string with search results, or None if search unavailable
    """
    if not tavily_client:
        return None
    
    try:
        # Perform search with Tavily
        response = tavily_client.search(
            query=query,
            max_results=max_results,
            search_depth="basic"  # Can be "basic" or "advanced"
        )
        
        # Format results
        if not response or 'results' not in response:
            return None
        
        results = []
        for idx, result in enumerate(response['results'][:max_results], 1):
            title = result.get('title', 'No title')
            content = result.get('content', 'No content')
            url = result.get('url', '')
            
            results.append(f"{idx}. {title}\n   {content}\n   Source: {url}")
        
        return "\n\n".join(results)
    
    except Exception as e:
        print(f"Tavily search error: {e}")
        return None


def enrich_actor_with_search(actor: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance actor profile with real-time web search results.
    
    Args:
        actor: Actor dictionary with research_query
        
    Returns:
        Actor dictionary with added 'search_context' field
    """
    research_query = actor.get('research_query', '')
    
    if not research_query or not tavily_client:
        return actor
    
    print(f"🔍 Searching Tavily for: {research_query}")
    
    search_results = search_for_actor_context(research_query)
    
    if search_results:
        actor['search_context'] = search_results
        print(f"✅ Found context for {actor.get('identifier', 'actor')}")
    else:
        actor['search_context'] = None
    
    return actor


# Example usage function (for demonstration)
def example_search():
    """Example of how to use Tavily search."""
    if not tavily_client:
        print("Tavily not available")
        return
    
    # Example: Search for context about a tech startup founder
    query = "Y Combinator startup founder challenges 2024"
    results = search_for_actor_context(query, max_results=3)
    
    if results:
        print("Search Results:")
        print(results)
    else:
        print("No results found")


if __name__ == "__main__":
    example_search()

