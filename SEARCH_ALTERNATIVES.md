# Web Search Alternatives for Vera

## Current Situation

DuckDuckGo has aggressive rate limiting that causes frequent failures when searching HashiCorp documentation. The current implementation already has:
- Reduced retries (1 attempt instead of 3)
- 8-second delays between retries
- Suppressed async warnings
- Graceful fallback to PDF-only results

However, rate limiting still occurs frequently during normal usage.

---

## Option 1: Disable Web Search Entirely (Recommended for Now)

**Overview:**
Remove or comment out the DuckDuckGo web search section, relying entirely on PDF semantic search.

**Pros:**
- No rate limiting issues
- Faster responses (no waiting for failed web searches)
- PDF search already covers HashiCorp validated designs comprehensively
- Zero additional setup or API keys required

**Cons:**
- Limited to validated design PDFs (doesn't search broader HashiCorp docs)
- Won't find community content or blog posts

**Implementation:**
- Comment out lines 335-399 in `tools.py`
- Update tool description to indicate it searches validated designs only
- ~5 minute implementation

**Cost:** Free

**When to Use:** If validated design PDFs provide sufficient coverage for your SE workflows

---

## Option 2: Google Custom Search API

**Overview:**
Use Google's Custom Search JSON API to search HashiCorp documentation.

**Setup Steps:**
1. Create a project in Google Cloud Console
2. Enable Custom Search API
3. Create a Custom Search Engine (CSE) restricted to hashicorp.com
4. Get API key and Search Engine ID
5. Add to environment variables:
   ```
   GOOGLE_SEARCH_API_KEY=your_key
   GOOGLE_SEARCH_ENGINE_ID=your_cse_id
   ```

**Pros:**
- Reliable and fast
- Excellent search quality
- 100 free queries/day (sufficient for typical SE usage)
- Official Google product with good documentation

**Cons:**
- Requires Google account and API key setup
- Limited to 100 queries/day on free tier
- Paid tier required for higher volume ($5 per 1000 queries after free tier)

**Implementation:**
- Install: `pip install google-api-python-client`
- Replace DuckDuckGo code with Google CSE API calls
- ~30 minutes implementation

**Cost:**
- Free: 100 queries/day
- Paid: $5 per 1,000 queries

**Documentation:** https://developers.google.com/custom-search/v1/overview

---

## Option 3: Brave Search API

**Overview:**
Privacy-focused search API from Brave browser company.

**Setup Steps:**
1. Sign up at https://brave.com/search/api/
2. Get API key from dashboard
3. Add to environment variables:
   ```
   BRAVE_SEARCH_API_KEY=your_key
   ```

**Pros:**
- Privacy-focused (no tracking)
- Generous free tier: 2,000 queries/month
- Simple RESTful API
- Good documentation

**Cons:**
- Newer service (less proven than Google/Bing)
- Requires API key setup
- Rate limits on free tier (1 query/second)

**Implementation:**
- Use `requests` library (already installed)
- Replace DuckDuckGo with Brave API calls
- ~30 minutes implementation

**Cost:**
- Free: 2,000 queries/month (1 req/sec)
- Paid: $5/month for 15,000 queries

**Documentation:** https://brave.com/search/api/

---

## Option 4: Bing Search API (Azure)

**Overview:**
Microsoft's Bing Search API via Azure Cognitive Services.

**Setup Steps:**
1. Create Azure account
2. Create Bing Search resource in Azure Portal
3. Get API key
4. Add to environment variables:
   ```
   BING_SEARCH_API_KEY=your_key
   ```

**Pros:**
- Enterprise-grade reliability
- Good search quality
- 1,000 free queries/month
- Part of Azure ecosystem (if already using Azure)

**Cons:**
- Requires Azure account
- More complex setup than alternatives
- Azure billing can be confusing

**Implementation:**
- Use `requests` library (already installed)
- Replace DuckDuckGo with Bing API calls
- ~30 minutes implementation

**Cost:**
- Free: 1,000 queries/month
- Paid: Varies by tier ($3-$7 per 1,000 queries)

**Documentation:** https://learn.microsoft.com/en-us/bing/search-apis/

---

## Option 5: SearXNG (Self-Hosted Meta-Search)

**Overview:**
Self-hosted meta-search engine that aggregates results from multiple search engines.

**Setup Steps:**
1. Deploy SearXNG instance:
   - Docker: `docker run -d -p 8080:8080 searxng/searxng`
   - Or deploy to cloud service (Fly.io, Railway, etc.)
2. Configure to search multiple engines
3. Point Vera to your SearXNG instance

**Pros:**
- No API keys needed
- No rate limits (you control it)
- Privacy-focused
- Aggregates multiple search engines
- Free to run (just server costs)

**Cons:**
- Requires maintaining a server/container
- More complex setup
- Responsible for uptime and maintenance
- Search engines may still block your IP if overused

**Implementation:**
- Deploy SearXNG instance
- Replace DuckDuckGo with SearXNG API calls
- ~1-2 hours implementation (including deployment)

**Cost:**
- Free if running locally
- $5-10/month for cloud hosting

**Documentation:** https://docs.searxng.org/

---

## Option 6: Add Search Result Caching

**Overview:**
Cache search results locally to reduce API calls to DuckDuckGo (or any other search provider).

**Implementation:**
- Cache search results in SQLite or JSON file
- TTL: 24-48 hours for cached results
- Hash query + product as cache key

**Pros:**
- Reduces API calls by 50-80% (typical usage patterns)
- Works with any search provider (DuckDuckGo, Google, etc.)
- Faster responses for repeated queries
- Simple to implement

**Cons:**
- Doesn't eliminate rate limits, just reduces frequency
- Cached results may be stale
- Storage overhead (minimal, ~1-10MB)
- Still subject to rate limits on fresh queries

**Implementation:**
- ~1 hour to add caching layer
- Use `cachetools` or simple JSON file cache

**Cost:** Free

---

## Comparison Matrix

| Option | Setup Time | Cost (Free) | Cost (Paid) | Reliability | Maintenance |
|--------|-----------|-------------|-------------|-------------|-------------|
| Disable Web Search | 5 min | Free | N/A | ★★★★★ | None |
| Google CSE | 30 min | 100/day | $5/1k | ★★★★★ | None |
| Brave Search | 30 min | 2k/month | $5/15k | ★★★★ | None |
| Bing Search | 30 min | 1k/month | $3-7/1k | ★★★★★ | None |
| SearXNG | 1-2 hrs | Server cost | Server cost | ★★★ | Medium |
| Caching | 1 hr | Free | N/A | ★★★ | Low |

---

## Recommendations

### For Immediate Use
**Disable Web Search** - The PDF semantic search is excellent and covers validated designs comprehensively. This eliminates all rate limiting issues.

### For Long-Term (If Broader Search Needed)
**Brave Search API** - Best balance of:
- Generous free tier (2,000/month)
- Simple setup
- Good reliability
- Privacy-focused

### For Enterprise/High Volume
**Google Custom Search API** - Most reliable and scalable, with enterprise support if needed.

### For Privacy/Control
**SearXNG** - If you want full control and privacy, worth the extra setup effort.

---

## Current Status

- Web search is **enabled** with minimal retry logic
- Falls back gracefully to PDF-only results when rate limited
- Async warnings suppressed
- Rate limit messages logged as INFO (not WARNING)

## Next Steps

1. Monitor how often rate limiting occurs in normal usage
2. If frequent (>20% of searches), consider switching to Brave Search API
3. If PDF search proves sufficient, disable web search entirely
4. Add caching regardless of which option is chosen (reduces load)

---

## Implementation Notes

When implementing any search API:

1. **Add to requirements.txt:**
   ```
   # Option 2: Google
   google-api-python-client==2.108.0

   # Option 3/4: Brave/Bing (use requests, already installed)
   # No additional dependencies needed
   ```

2. **Add to .env.example:**
   ```
   # Search API Configuration (choose one)
   # GOOGLE_SEARCH_API_KEY=your_key
   # GOOGLE_SEARCH_ENGINE_ID=your_cse_id
   # BRAVE_SEARCH_API_KEY=your_key
   # BING_SEARCH_API_KEY=your_key
   ```

3. **Update config.py:**
   ```python
   # Search API settings
   SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "duckduckgo")  # duckduckgo, google, brave, bing, none
   GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
   GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")
   BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")
   BING_SEARCH_API_KEY = os.getenv("BING_SEARCH_API_KEY", "")
   ```

4. **Refactor tools.py:**
   - Create separate functions for each search provider
   - Add a factory pattern to select provider based on config
   - Maintain consistent error handling across all providers
