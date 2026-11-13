from datetime import datetime, timezone
from statistics import mean

MIN_POINTS = 5
DISCLAIMER = (
    "Statistical hint based on the price history collected so far; "
    "not a guarantee."
)


def to_naive_utc(dt: datetime) -> datetime:
    """MongoDB may hand back naive or aware datetimes; normalise to naive UTC."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def event_for(moment: datetime, events: list):
    """Return the sale event whose date range contains `moment`, else None."""
    day = to_naive_utc(moment).date()
    for ev in events:
        start = to_naive_utc(ev["start_date"]).date()
        end = to_naive_utc(ev["end_date"]).date()
        if start <= day <= end:
            return ev
    return None


def moving_average(prices: list, window: int):
    if not prices:
        return None
    recent = prices[-window:]
    return sum(recent) / len(recent)


def trend_slope(prices: list):
    """Least-squares slope (price change per check). None if fewer than 3 points."""
    n = len(prices)
    if n < 3:
        return None
    x_mean = (n - 1) / 2
    y_mean = mean(prices)
    num = sum((x - x_mean) * (y - y_mean) for x, y in enumerate(prices))
    den = sum((x - x_mean) ** 2 for x in range(n))
    return num / den


def _confidence(n: int) -> str:
    if n < 10:
        return "low"
    if n < 30:
        return "medium"
    return "high"


def _cheapest_bucket(rows: list, key_fn):
    """Which bucket (weekday / week of month) has the lowest average price."""
    buckets = {}
    for row in rows:
        key = key_fn(to_naive_utc(row["checked_at"]))
        buckets.setdefault(key, []).append(row["price"])
    averages = {k: mean(v) for k, v in buckets.items() if len(v) >= 2}
    if len(averages) < 2:
        return None
    best = min(averages, key=averages.get)
    overall = mean(r["price"] for r in rows)
    return {
        "bucket": best,
        "average_price": round(averages[best], 2),
        "vs_overall_average_percent": round(
            (averages[best] - overall) / overall * 100, 1
        ),
    }


def build_insights(history: list, events: list, now: datetime | None = None) -> dict:
    """Feature 2: buy now / wait suggestion from the price history."""
    now = now or datetime.now(timezone.utc)
    rows = sorted(history, key=lambda r: to_naive_utc(r["checked_at"]))
    prices = [r["price"] for r in rows]
    active = event_for(now, events)

    result = {
        "data_points": len(prices),
        "confidence": _confidence(len(prices)),
        "active_sale_event": active["name"] if active else None,
        "disclaimer": DISCLAIMER,
    }

    if len(prices) < MIN_POINTS:
        result["recommendation"] = "not_enough_data"
        result["reason"] = (
            f"Need at least {MIN_POINTS} price checks, have {len(prices)}."
        )
        return result

    current = prices[-1]
    lowest, highest, avg = min(prices), max(prices), mean(prices)
    slope = trend_slope(prices)
    slope_pct = (slope / avg * 100) if (slope is not None and avg) else 0.0

    if current <= lowest * 1.02:
        recommendation = "buy_now"
        reason = "Price is at or within 2% of the lowest price recorded."
    elif slope_pct < -0.5:
        recommendation = "wait"
        reason = "Price is trending down and may fall further."
    elif current <= avg * 0.95:
        recommendation = "buy_now"
        reason = "Price is more than 5% below its average and no longer falling."
    elif current >= avg * 1.05:
        recommendation = "wait"
        reason = "Price is more than 5% above its average."
    else:
        recommendation = "neutral"
        reason = "Price is close to its usual average."

    sale_note = None
    if active:
        if current > avg * 0.97:
            sale_note = (
                f"{active['name']} is on, but this price is not clearly "
                "below its usual average."
            )
        else:
            sale_note = (
                f"{active['name']} is on and the price is below its usual average."
            )

    best_time = None
    if len(prices) >= 14:
        best_time = {
            "cheapest_week_of_month": _cheapest_bucket(
                rows, lambda d: (d.day - 1) // 7 + 1
            ),
            "cheapest_weekday": _cheapest_bucket(rows, lambda d: d.strftime("%A")),
        }

    result.update(
        recommendation=recommendation,
        reason=reason,
        sale_note=sale_note,
        current_price=current,
        lowest_price=lowest,
        highest_price=highest,
        average_price=round(avg, 2),
        moving_average_7=round(moving_average(prices, 7), 2),
        trend_percent_per_check=round(slope_pct, 2),
        cheaper_than_percent_of_history=round(
            sum(1 for p in prices if p >= current) / len(prices) * 100
        ),
        best_time_to_buy=best_time,
    )
    return result


def build_drop_report(
    history: list,
    events: list,
    min_drop_percent: float = 3.0,
    now: datetime | None = None,
) -> dict:
    """Feature 6: label each price drop as sale-event or standalone."""
    now = now or datetime.now(timezone.utc)
    rows = sorted(history, key=lambda r: to_naive_utc(r["checked_at"]))

    drops = []
    for prev, cur in zip(rows, rows[1:]):
        if prev["price"] <= 0 or cur["price"] >= prev["price"]:
            continue
        pct = (prev["price"] - cur["price"]) / prev["price"] * 100
        if pct < min_drop_percent:
            continue
        event = event_for(cur["checked_at"], events)
        drops.append(
            {
                "from_price": prev["price"],
                "to_price": cur["price"],
                "drop_percent": round(pct, 1),
                "detected_at": to_naive_utc(cur["checked_at"]),
                "classification": "sale_event" if event else "standalone",
                "sale_event": event["name"] if event else None,
            }
        )

    sale = [d["drop_percent"] for d in drops if d["classification"] == "sale_event"]
    alone = [d["drop_percent"] for d in drops if d["classification"] == "standalone"]
    active = event_for(now, events)

    return {
        "drops": drops,
        "summary": {
            "sale_event_drops": len(sale),
            "standalone_drops": len(alone),
            "average_sale_drop_percent": round(mean(sale), 1) if sale else None,
            "average_standalone_drop_percent": round(mean(alone), 1) if alone else None,
            "currently_in_sale_event": active["name"] if active else None,
        },
    }


def build_budget_plan(
    monthly_budget: float,
    spent: float,
    products: list,
    averages: dict,
) -> dict:
    """Feature 7: pick the best deals that fit in what is left of the budget."""
    budget_left = max(monthly_budget - spent, 0.0)
    priced, waiting = [], []

    for p in products:
        current = p.get("current_price")
        name = p.get("product_name", "Unknown product")
        if current is None:
            waiting.append({"product_id": str(p["_id"]), "product_name": name})
            continue
        avg = averages.get(p["_id"]) or current
        deal = (avg - current) / avg * 100 if avg else 0.0
        priced.append(
            {
                "product_id": str(p["_id"]),
                "product_name": name,
                "current_price": current,
                "average_price": round(avg, 2),
                "deal_score_percent": round(deal, 1),
                "target_hit": current <= p.get("target_price", 0),
            }
        )

    priced.sort(key=lambda x: x["deal_score_percent"], reverse=True)

    recommended, skipped, total = [], [], 0.0
    for item in priced:
        if item["deal_score_percent"] <= 0:
            skipped.append({**item, "reason": "no_deal_yet"})
        elif total + item["current_price"] <= budget_left:
            recommended.append(item)
            total += item["current_price"]
        else:
            skipped.append({**item, "reason": "over_budget"})

    return {
        "monthly_budget": monthly_budget,
        "spent_this_month": spent,
        "budget_left": round(budget_left, 2),
        "recommended": recommended,
        "recommended_total": round(total, 2),
        "left_after_recommended": round(budget_left - total, 2),
        "skipped": skipped,
        "waiting_for_first_price": waiting,
    }