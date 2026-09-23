from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from telethon import TelegramClient, functions, types

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MEDIA = DATA / "media"
DB = DATA / "nevex.db"
OUT = DATA / "gifts.json"

load_dotenv(ROOT / "backend" / ".env")

API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION = os.environ.get("TELEGRAM_SESSION", str(DATA / "nevex_telegram"))
PAGE_LIMIT = int(os.environ.get("RESALE_PAGE_LIMIT", "100"))


def rarity_value(rarity: Any) -> float | None:
    if rarity is None:
        return None
    if hasattr(rarity, "permille"):
        return rarity.permille / 10.0
    return None


def amount_value(amount: Any) -> tuple[int | None, int | None, str | None]:
    if amount is None:
        return None, None, None
    if isinstance(amount, types.StarsTonAmount):
        return amount.amount, 0, "TON"
    if isinstance(amount, types.StarsAmount):
        return amount.amount, getattr(amount, "nanos", 0), "STARS"
    return None, None, None


def attribute_parts(attributes: list[Any]) -> dict[str, Any]:
    out = {
        "model": None,
        "pattern": None,
        "backdrop": None,
        "model_rarity": None,
        "pattern_rarity": None,
        "backdrop_rarity": None,
    }
    for attr in attributes or []:
        if isinstance(attr, types.StarGiftAttributeModel):
            if getattr(attr, "crafted", False):
                continue
            out["model"] = attr.name
            out["model_rarity"] = rarity_value(attr.rarity)
        elif isinstance(attr, types.StarGiftAttributePattern):
            out["pattern"] = attr.name
            out["pattern_rarity"] = rarity_value(attr.rarity)
        elif isinstance(attr, types.StarGiftAttributeBackdrop):
            out["backdrop"] = attr.name
            out["backdrop_rarity"] = rarity_value(attr.rarity)
    return out


async def main() -> None:
    if not API_ID or not API_HASH:
        raise SystemExit(
            "Не заполнены TELEGRAM_API_ID и TELEGRAM_API_HASH в backend/.env"
        )

    DATA.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(SESSION, API_ID, API_HASH)

    await client.start()
    print("Telegram подключён.")

    # Official list of gift types.
    response = await client(functions.payments.GetStarGiftsRequest(hash=0))
    gift_types = []

    for gift in response.gifts:
        if isinstance(gift, types.StarGift):
            gift_types.append(
                {
                    "gift_id": gift.id,
                    "title": gift.title,
                    "limited": bool(gift.limited),
                    "sold_out": bool(gift.sold_out),
                    "stars": gift.stars,
                    "availability_total": gift.availability_total,
                    "availability_resale": gift.availability_resale,
                    "upgrade_stars": gift.upgrade_stars,
                }
            )

    all_resale: list[dict[str, Any]] = []
    all_attributes: dict[int, list[dict[str, Any]]] = {}

    for idx, gift in enumerate(gift_types, start=1):
        gift_id = gift["gift_id"]
        print(f"[{idx}/{len(gift_types)}] {gift['title']}")

        # Possible collectible attributes.
        try:
            attrs_resp = await client(
                functions.payments.GetStarGiftUpgradeAttributesRequest(
                    gift_id=gift_id
                )
            )
            items = []
            for attr in attrs_resp.attributes:
                item = {
                    "type": attr.__class__.__name__,
                    "name": getattr(attr, "name", None),
                    "rarity": rarity_value(getattr(attr, "rarity", None)),
                }
                if isinstance(attr, types.StarGiftAttributeBackdrop):
                    item.update(
                        {
                            "backdrop_id": attr.backdrop_id,
                            "center_color": attr.center_color,
                            "edge_color": attr.edge_color,
                            "pattern_color": attr.pattern_color,
                            "text_color": attr.text_color,
                        }
                    )
                items.append(item)
            all_attributes[gift_id] = items
        except Exception as exc:
            print(f"  attributes error: {exc}")

        # Resale listings, paginated.
        offset = ""
        while True:
            try:
                resale = await client(
                    functions.payments.GetResaleStarGiftsRequest(
                        gift_id=gift_id,
                        offset=offset,
                        limit=PAGE_LIMIT,
                        sort_by_price=True,
                    )
                )
            except Exception as exc:
                print(f"  resale error: {exc}")
                break

            for item in resale.gifts:
                if not isinstance(item, types.StarGiftUnique):
                    continue

                parts = attribute_parts(item.attributes)
                amount = item.resell_amount[0] if item.resell_amount else None
                price_amount, price_nanos, currency = amount_value(amount)

                all_resale.append(
                    {
                        "gift_id": item.gift_id,
                        "title": item.title,
                        "num": item.num,
                        "slug": item.slug,
                        "owner_address": item.owner_address,
                        "gift_address": item.gift_address,
                        "price_amount": price_amount,
                        "price_nanos": price_nanos,
                        "price_currency": currency,
                        **parts,
                    }
                )

            offset = getattr(resale, "next_offset", None) or ""
            if not offset:
                break

    payload = {
        "gift_types": gift_types,
        "attributes": [
            {"gift_id": gift_id, "items": items}
            for gift_id, items in all_attributes.items()
        ],
        "resale": all_resale,
    }

    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with sqlite3.connect(DB) as con:
        con.execute(
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
            )
            """
        )

        for item in all_resale:
            con.execute(
                """
                INSERT INTO gifts (
                    gift_id, title, num, slug, model, pattern, backdrop,
                    model_rarity, pattern_rarity, backdrop_rarity,
                    price_amount, price_nanos, price_currency,
                    owner_address, gift_address, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(slug) DO UPDATE SET
                    title=excluded.title,
                    num=excluded.num,
                    model=excluded.model,
                    pattern=excluded.pattern,
                    backdrop=excluded.backdrop,
                    model_rarity=excluded.model_rarity,
                    pattern_rarity=excluded.pattern_rarity,
                    backdrop_rarity=excluded.backdrop_rarity,
                    price_amount=excluded.price_amount,
                    price_nanos=excluded.price_nanos,
                    price_currency=excluded.price_currency,
                    owner_address=excluded.owner_address,
                    gift_address=excluded.gift_address,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    item["gift_id"],
                    item["title"],
                    item["num"],
                    item["slug"],
                    item["model"],
                    item["pattern"],
                    item["backdrop"],
                    item["model_rarity"],
                    item["pattern_rarity"],
                    item["backdrop_rarity"],
                    item["price_amount"],
                    item["price_nanos"],
                    item["price_currency"],
                    item["owner_address"],
                    item["gift_address"],
                ),
            )
        con.commit()

    print()
    print(f"Готово. Типов Gifts: {len(gift_types)}")
    print(f"Resale NFT: {len(all_resale)}")
    print(f"JSON: {OUT}")
    print(f"SQLite: {DB}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
