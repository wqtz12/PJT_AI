# Implementation Plan - Add Search Capability to Daily News Skill

## Goal Description
Enable the Daily News Skill to accept a generic "theme" or "stock symbol" as input, instead of just predefined categories. This will allow the user to scrape news related to specific topics or stocks from Naver and NewsAPI.

## User Review Required
> [!IMPORTANT]
> This change introduces a new mode of operation for the skill.
> - **Category Mode**: The existing behavior (collecting top news from specific sections).
> - **Search Mode**: The new behavior (searching for keywords).
> The skill will automatically detect if the input is a known category. If not, it will treat it as a search query.

## Proposed Changes

### News Agent
#### [MODIFY] [naver.py](file:///Users/jbs/PJT_AI/src/agent/news_agent/collectors/naver.py)
- Add `search_articles(query, limit)` method.
- Implement scraping of Naver News search results (`https://search.naver.com/search.naver?where=news&query=...`).
    - Parse search result items (title, link, date, description).
    - Use existing `scraper` to fetch full content from the result links.

#### [MODIFY] [daily_news_skill.py](file:///Users/jbs/PJT_AI/src/agent/news_agent/daily_news_skill.py)
- Update `SkillConfig` to accept `query` or allow `categories` to contain search terms.
- Update `collect_category` (or rename/wrapper) to logic:
    - Check if input is a known category key (e.g., "경제", "technology").
    - If yes, proceed with existing category collection.
    - If no, call `search_articles` on `NaverCollector` and `NewsAPICollector`.
- Update `main` and `parse_args` to support the new input usage.

#### [MODIFY] [SKILL.md](file:///Users/jbs/PJT_AI/src/agent/news_agent/SKILL.md)
- Update documentation to explain how to use the search feature.

## Verification Plan

### Automated Tests
- None existing.
- Run the skill with `dry-run` and a keyword to verify it collects articles.

### Manual Verification
1.  **Search Test (Naver)**: Run `python -m src.agent.news_agent.daily_news_skill --keyword "삼성전자" --limit 3 --dry-run`
    - Verify it logs "Searching Naver for '삼성전자'..."
    - Verify it finds articles about Samsung Electronics.
2.  **Category Test**: Run `python -m src.agent.news_agent.daily_news_skill --categories "경제" --limit 3 --dry-run`
    - Verify it still works for predefined categories.
