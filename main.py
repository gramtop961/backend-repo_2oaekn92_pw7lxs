import os
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import NewsArticle, RawArticle

app = FastAPI(title="MarketView AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "MarketView AI backend running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = os.getenv("DATABASE_NAME") or "❌ Not Set"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"

    return response


# Basic models for responses
class NewsResponse(BaseModel):
    id: str
    source: str
    title_ko: str
    summary_ko: str
    sentiment: str
    published_at: Optional[datetime] = None
    tags: Optional[List[str]] = []
    ticker: Optional[str] = None


@app.get("/api/news", response_model=List[NewsResponse])
def list_news(limit: int = 20, sentiment: Optional[str] = None, ticker: Optional[str] = None):
    """List latest processed news items"""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    f: dict = {}
    if sentiment:
        f["sentiment"] = sentiment
    if ticker:
        f["ticker"] = ticker

    items = get_documents("news", f, limit)
    results: List[NewsResponse] = []
    for it in items:
        results.append(NewsResponse(
            id=str(it.get("_id")),
            source=it.get("source", ""),
            title_ko=it.get("title_ko", it.get("title_en", "")),
            summary_ko=it.get("summary_ko", ""),
            sentiment=it.get("sentiment", "neutral"),
            published_at=it.get("published_at"),
            tags=it.get("tags", []),
            ticker=it.get("ticker")
        ))
    return results


@app.post("/api/ingest")
def ingest_article(payload: RawArticle):
    """Ingest a raw article that has been already processed externally. Stores to 'news' collection."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    # For MVP, we accept RawArticle and transform into NewsArticle minimal fields
    # In real system, this would run LLM summarization and sentiment here.
    title_ko = payload.title  # placeholder: assume already Korean or simple passthrough
    doc = NewsArticle(
        url=payload.url,
        source=payload.source,
        title_en=None,
        title_ko=title_ko,
        summary_ko=(payload.content or "").strip()[:500] or "요약 없음",
        sentiment="neutral",
        published_at=payload.published_at,
        tags=[],
        ticker=payload.ticker
    )
    inserted_id = create_document("news", doc)
    return {"id": inserted_id, "status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
