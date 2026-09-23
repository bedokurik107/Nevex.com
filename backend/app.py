from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = DATA / "nevex.db"
JSON_FILE = DATA / "gifts.json"
ENV_FILE = ROOT / "backend" / ".env"
STATIC = ROOT / "backend" / "static"

# Load .env BEFORE reading configuration values.
load_dotenv(ENV_FILE)
MRKT_API_URL = os.environ.get("MRKT_API_URL", "https://api.tgmrkt.io/api/v1/gifts/saling").strip()
MRKT_TOKEN = os.environ.get("MRKT_TOKEN", "").strip()
MRKT_REFERER = os.environ.get("MRKT_REFERER", "https://cdn.tgmrkt.io/").strip()

app = FastAPI(title="NEVEX API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local development only
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def connect() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS gifts (
                id INTEGER PRIMARY KEY,
                gift_id INTEGER,
                title TEXT,
                num INTEGER,
                slug TEXT UNIQUE,
                model TEXT,
                pattern TEXT,
                backdrop TEXT,
                model_rarity REAL,
                pattern_rarity REAL,
                backdrop_rarity REAL,
                price_amount INTEGER,
                price_nanos INTEGER,
                price_currency TEXT,
                owner_address TEXT,
                gift_address TEXT,
                image_url TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_gifts_title ON gifts(title);
            CREATE INDEX IF NOT EXISTS idx_gifts_model ON gifts(model);
            CREATE INDEX IF NOT EXISTS idx_gifts_pattern ON gifts(pattern);
            CREATE INDEX IF NOT EXISTS idx_gifts_backdrop ON gifts(backdrop);
            CREATE INDEX IF NOT EXISTS idx_gifts_price ON gifts(price_amount);
            """
        )


def mrkt_headers() -> dict[str, str]:
    if not MRKT_TOKEN:
        raise HTTPException(status_code=503, detail="MRKT_TOKEN не задан в backend/.env")
    return {
        "Authorization": MRKT_TOKEN,
        "Referer": MRKT_REFERER,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "NEVEX/1.0",
    }


def mrkt_request(payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(MRKT_API_URL, data=json.dumps(payload).encode("utf-8"), headers=mrkt_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=502, detail=f"MRKT HTTP {exc.code}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"MRKT connection error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="MRKT вернул не-JSON ответ") from exc


def first_value(obj: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = obj.get(key)
        if value is not None and value != "":
            return value
    return None


def normalize_mrkt_gift(g: dict[str, Any]) -> dict[str, Any]:
    price_raw = first_value(g, "price", "priceAmount", "price_amount")
    try:
        price = float(price_raw) if price_raw is not None else 0.0
    except (TypeError, ValueError):
        price = 0.0
    slug = str(first_value(g, "slug", "giftSlug") or "").strip()
    title = str(first_value(g, "collectionName", "title", "name") or "Telegram Gift")
    num_raw = first_value(g, "number", "num", "giftNumber")
    try:
        num = int(num_raw) if num_raw is not None else 0
    except (TypeError, ValueError):
        num = 0
    if not slug:
        slug = f"{title.lower().replace(' ', '-')}-{num or first_value(g, 'id', 'giftId') or 'item'}"
    model = first_value(g, "modelName", "model")
    pattern = first_value(g, "symbolName", "pattern", "symbol")
    backdrop = first_value(g, "backdropName", "backdrop")
    return {
        "gift_id": first_value(g, "giftId", "gift_id", "id"),
        "title": title,
        "num": num,
        "slug": slug,
        "model": model,
        "pattern": pattern,
        "backdrop": backdrop,
        "model_rarity": first_value(g, "modelRarity", "model_rarity"),
        "pattern_rarity": first_value(g, "symbolRarity", "patternRarity", "pattern_rarity"),
        "backdrop_rarity": first_value(g, "backdropRarity", "backgroundRarity", "backdrop_rarity"),
        "price_amount": price,
        "price_nanos": 0,
        "price_currency": "TON",
        "owner_address": first_value(g, "ownerAddress", "owner_address") or "",
        "gift_address": first_value(g, "giftAddress", "gift_address") or "",
        "image_url": first_value(g, "imageUrl", "image_url", "image") or "",
    }


def save_mrkt_items(items: list[dict[str, Any]]) -> int:
    init_db()
    with connect() as con:
        for item in items:
            con.execute(
                """
                INSERT INTO gifts (gift_id,title,num,slug,model,pattern,backdrop,model_rarity,pattern_rarity,backdrop_rarity,price_amount,price_nanos,price_currency,owner_address,gift_address,image_url,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                ON CONFLICT(slug) DO UPDATE SET
                  gift_id=excluded.gift_id,title=excluded.title,num=excluded.num,model=excluded.model,pattern=excluded.pattern,backdrop=excluded.backdrop,
                  model_rarity=excluded.model_rarity,pattern_rarity=excluded.pattern_rarity,backdrop_rarity=excluded.backdrop_rarity,
                  price_amount=excluded.price_amount,price_nanos=excluded.price_nanos,price_currency=excluded.price_currency,
                  owner_address=excluded.owner_address,gift_address=excluded.gift_address,image_url=excluded.image_url,updated_at=CURRENT_TIMESTAMP
                """,
                (item["gift_id"],item["title"],item["num"],item["slug"],item["model"],item["pattern"],item["backdrop"],item["model_rarity"],item["pattern_rarity"],item["backdrop_rarity"],item["price_amount"],item["price_nanos"],item["price_currency"],item["owner_address"],item["gift_address"],item["image_url"]),
            )
        con.commit()
    return len(items)



@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "NEVEX API"}


@app.get("/app")
def app_entry():
    index = STATIC / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Frontend build не найден. Выполни npm run build в frontend-app.")
    return FileResponse(index)


@app.get("/api/gifts")
def gifts(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    model: str | None = None,
    pattern: str | None = None,
    backdrop: str | None = None,
) -> dict[str, Any]:
    where = []
    params: list[Any] = []

    if search:
        where.append("(title LIKE ? OR slug LIKE ?)")
        like = f"%{search}%"
        params += [like, like]
    if model:
        where.append("model = ?")
        params.append(model)
    if pattern:
        where.append("pattern = ?")
        params.append(pattern)
    if backdrop:
        where.append("backdrop = ?")
        params.append(backdrop)

    clause = " WHERE " + " AND ".join(where) if where else ""

    with connect() as con:
        total = con.execute(
            f"SELECT COUNT(*) FROM gifts{clause}", params
        ).fetchone()[0]
        rows = con.execute(
            f"SELECT * FROM gifts{clause} ORDER BY price_amount ASC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

    items = []
    for row in rows:
        item = dict(row)
        amount = float(item.get("price_amount") or 0)
        nanos = int(item.get("price_nanos") or 0)
        item["price"] = amount + nanos / 1_000_000_000
        items.append(item)
    return {"total": total, "items": items}


@app.get("/api/gifts/{slug}")
def gift(slug: str) -> dict[str, Any]:
    with connect() as con:
        row = con.execute(
            "SELECT * FROM gifts WHERE slug = ?", (slug,)
        ).fetchone()
    if not row:
        return {"found": False}
    return {"found": True, "item": dict(row)}


@app.get("/api/stats")
def stats() -> dict[str, Any]:
    """Small catalog summary used by the frontend/admin checks."""
    with connect() as con:
        total = con.execute("SELECT COUNT(*) FROM gifts").fetchone()[0]
        row = con.execute(
            "SELECT MIN(price_amount), MAX(price_amount), AVG(price_amount) FROM gifts WHERE price_amount > 0"
        ).fetchone()
    return {
        "total": int(total),
        "min_price": float(row[0]) if row[0] is not None else None,
        "max_price": float(row[1]) if row[1] is not None else None,
        "avg_price": float(row[2]) if row[2] is not None else None,
        "source": "MRKT" if MRKT_TOKEN else "not-configured",
    }


@app.get("/api/catalog")
def catalog() -> dict[str, Any]:
    if JSON_FILE.exists():
        return json.loads(JSON_FILE.read_text(encoding="utf-8"))
    return {"gift_types": [], "resale": [], "attributes": []}


@app.get("/api/mrkt/status")
def mrkt_status() -> dict[str, Any]:
    return {
        "configured": bool(MRKT_TOKEN),
        "source": "MRKT" if MRKT_TOKEN else "not-configured",
        "api_url": MRKT_API_URL,
    }


@app.post("/api/mrkt/sync")
def mrkt_sync(count: int = Query(20, ge=1, le=20)) -> dict[str, Any]:
    payload = {
        "collectionNames": [],
        "modelNames": [],
        "backdropNames": [],
        "symbolNames": [],
        "ordering": "Price",
        "lowToHigh": True,
        "maxPrice": None,
        "minPrice": None,
        "mintable": None,
        "number": None,
        "count": count,
        "cursor": "",
        "query": None,
        "promotedFirst": False,
    }
    response = mrkt_request(payload)
    raw_items = response.get("gifts") or response.get("items") or []
    items = [normalize_mrkt_gift(x) for x in raw_items if isinstance(x, dict)]
    items = [x for x in items if x["price_amount"] > 0]
    saved = save_mrkt_items(items)
    return {"ok": True, "received": len(items), "saved": saved, "cursor": response.get("cursor")}


# Production frontend: after `npm run build`, frontend-app/dist is copied to backend/static.
# API routes above keep working on the same origin, so public hosting does not depend on localhost:8000.
if STATIC.exists():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def frontend(full_path: str):
        if full_path.startswith("api/") or full_path == "health":
            raise HTTPException(status_code=404, detail="Not Found")
        target = STATIC / full_path
        if target.is_file():
            return FileResponse(target)
        index = STATIC / "index.html"
        if index.exists():
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Frontend build не найден")
