#!/usr/bin/env python3
"""
Google Maps Review Scraper
--------------------------
Usage:
    python google_reviews.py --place "Starbucks Toronto" --period "3h"
    python google_reviews.py --place "Myungga Waterloo" --period "4m"
    python google_reviews.py --place "Tim Hortons" --period "1y"

Period shorthand:  <number><unit>   e.g.  3h  2d  1w  4m  1y
  h=hour  d=day  w=week  m=month  y=year
Verbose format also accepted:  "3 hours", "1 month", "2 weeks", …

Output (in ./output/):
    reviews_<place>_<period>.csv  ← 10-column CSV table
"""

import argparse
import asyncio
import csv
import re
import sys
import random
from datetime import datetime, timedelta
from pathlib import Path

try:
    import env
except ImportError:
    env = None

from playwright.async_api import async_playwright


# ─────────────────────────────────────────────────────────────────────────────
# Date helpers
# ─────────────────────────────────────────────────────────────────────────────

def parse_period(s: str) -> timedelta:
    """
    Accept both shorthand and verbose period strings.

    Shorthand  →  verbose equivalent
      3h  →  3 hours
      2d  →  2 days
      1w  →  1 week
      4m  →  4 months
      1y  →  1 year

    Verbose forms ('3 hours', '1 month', '2 weeks', …) still work as-is.
    """
    s = s.strip().lower()

    # ── Expand shorthand (e.g. '4m', '1y', '3h') ──────────────────────────
    _shorthand = {
        "h": "hours",
        "d": "days",
        "w": "weeks",
        "m": "months",
        "y": "years",
    }
    sh = re.fullmatch(r"(\d+)([hdwmy])", s)
    if sh:
        s = f"{sh.group(1)} {_shorthand[sh.group(2)]}"

    # ── Parse verbose form ─────────────────────────────────────────────────
    m = re.match(r"(\d+)\s*(hour|hours|day|days|week|weeks|month|months|year|years)", s)
    if not m:
        raise ValueError(
            f"Cannot parse '{s}'. "
            "Use shorthand like '4m', '1y', '3h' "
            "or verbose like '3 hours', '1 week', '2 months'."
        )
    n, unit = int(m.group(1)), m.group(2).rstrip("s")
    return {
        "hour":  timedelta(hours=n),
        "day":   timedelta(days=n),
        "week":  timedelta(weeks=n),
        "month": timedelta(days=n * 30),
        "year":  timedelta(days=n * 365),
    }[unit]


def parse_relative_date(text: str, now: datetime) -> datetime | None:
    """
    'a month ago' '3 hours ago' → datetime.
    Returns None if unparseable.
    """
    t = text.strip().lower()
    if t in ("just now", "moments ago", "a moment ago"):
        return now

    # normalise "a/an" → "1"
    t = re.sub(r"\ba\b|\ban\b", "1", t)

    # English
    m = re.search(r"(\d+)\s*(second|minute|hour|day|week|month|year)s?\s*ago", t)
    if m:
        return _delta(now, int(m.group(1)), m.group(2))

    return None


def _delta(now: datetime, n: int, unit: str) -> datetime:
    mapping = {
        "second": timedelta(seconds=n),
        "minute": timedelta(minutes=n),
        "hour":   timedelta(hours=n),
        "day":    timedelta(days=n),
        "week":   timedelta(weeks=n),
        "month":  timedelta(days=n * 30),
        "year":   timedelta(days=n * 365),
    }
    return now - mapping.get(unit, timedelta(0))


def is_within_cutoff(date_txt: str, cutoff: datetime, now: datetime):
    """
    Decide inclusion based on the actual cutoff datetime.

    Parses the relative date string (e.g. '3 months ago', '1 year ago') and compares it against *cutoff*.

    Returns:
        True  – review date is on or after cutoff  → include
        False – review date is before cutoff        → exclude / stop
        None  – unparseable                         → include (safe default)
    """
    t = date_txt.strip().lower()
    if not t:
        return None

    # Fast path: clearly very recent (hours/minutes/seconds/days/weeks)
    # These are always within any reasonable cutoff (month or longer)
    if re.search(r'just now|moment|second|minute', t):
        return True

    # Parse the date and compare against the real cutoff
    parsed = parse_relative_date(date_txt, now)
    if parsed is None:
        return None  # unknown → include
    return parsed >= cutoff


def fmt_date(date_iso: str | None) -> str:
    """Return YYYY-MM-DD or empty string."""
    if not date_iso:
        return ""
    try:
        return datetime.fromisoformat(date_iso).strftime("%Y-%m-%d")
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Playwright scraper
# ─────────────────────────────────────────────────────────────────────────────

async def navigate_to_place(
    page,
    place_name: str,
    timeout: int = 60000,
    direct_url: str | None = None,
) -> str:
    """Open Google Maps in English and navigate to the place page."""
    if direct_url:
        print(f"  🔗 Navigating to direct URL")
        sep = "&" if "?" in direct_url else "?"
        url = direct_url + sep + "hl=en" if "hl=" not in direct_url else direct_url
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        await asyncio.sleep(3)
    else:
        print(f"  🔍 Searching: {place_name}")
        url = f"https://www.google.com/maps/search/{place_name.replace(' ', '+')}?hl=en"
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        await asyncio.sleep(3)

        # Click first result if we got a search-results page
        if "/search/" in page.url or "?q=" in page.url:
            try:
                await page.locator('a[href*="/maps/place/"]').first.click(timeout=8000)
                await asyncio.sleep(4)
            except Exception:
                pass

    print(f"  🌐 {page.url[:90]}")
    return page.url


async def get_restaurant_name(page) -> str:
    """Try to extract the place name from the page."""
    selectors = [
        "h1.DUwDvf",
        "h1[class*='fontHeadlineLarge']",
        "h1",
        "[data-item-id='title'] h1",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if await el.count():
                txt = (await el.inner_text(timeout=2000)).strip()
                if txt:
                    return txt
        except Exception:
            continue
    return ""


async def open_reviews_tab(page) -> bool:
    """Click the Reviews tab. Returns True on success."""
    print("  📑 Opening Reviews tab …")
    await asyncio.sleep(2)

    # 1. Try role=tab with "reviews" text
    tabs = await page.get_by_role("tab").all()
    for tab in tabs:
        try:
            txt = (await tab.inner_text(timeout=800)).strip()
            if re.search(r"review|리뷰|评论|opinion|avis|rezension", txt, re.IGNORECASE):
                await tab.click()
                await asyncio.sleep(3)
                print(f"     ✅ '{txt}'")
                return True
        except Exception:
            continue

    # 2. JavaScript click by text / fallback to 3rd tab
    result = await page.evaluate("""
        () => {
            const all = [...document.querySelectorAll('[role="tab"]')];
            for (const t of all) {
                const txt = t.textContent.trim();
                if (/^reviews?$/i.test(txt)) { t.click(); return txt; }
            }
            if (all.length >= 3) { all[2].click(); return 'tab[2]: ' + all[2].textContent.trim(); }
            return null;
        }
    """)
    if result:
        await asyncio.sleep(3)
        print(f"     ✅ JS clicked: '{result}'")
        return True

    print("     ⚠️  Reviews tab not found — scraping from current view (limited view)")
    return False


async def sort_by_newest(page) -> bool:
    """Sort reviews newest-first. Returns True on success."""
    print("  📅 Sorting by newest …")
    try:
        sort_btn = page.locator(
            'button[aria-label*="Sort"], button[jsaction*="sort"], [data-sort-id]'
        ).first
        if await sort_btn.count() > 0:
            await sort_btn.click()
            await asyncio.sleep(1.5)
            # "Newest" is usually the 2nd option (index 1)
            options = await page.locator('[role="menuitemradio"], [role="option"]').all()
            if len(options) >= 2:
                await options[1].click()
                await asyncio.sleep(2)
                print("     ✅ Sorted newest")
                return True
    except Exception as e:
        print(f"     ⚠️  Sort failed: {e}")
    return False


async def scrape_reviews(
    page,
    cutoff: datetime,
    now: datetime,
    restaurant_name: str,
    page_url: str,
    max_scrolls: int = 400,
    max_reviews: int = 0,
) -> list[dict]:
    """
    Scroll the reviews panel and collect reviews.

    Stop condition (cutoff-aware):
      • Review date >= cutoff  → INCLUDE
      • Review date <  cutoff  → EXCLUDE and count toward stop streak

    The cutoff is derived from the --period argument (e.g. 4m = 4 months ago),
    so '1 month ago' reviews ARE collected when the period is 4m, 6m, 1y, etc.
    """
    reviews: list[dict] = []
    seen: set[str] = set()
    # How many consecutive reviews whose raw date text says "month" / "year"
    # must we see before we stop scrolling entirely?
    TEXT_STREAK_LIMIT = 5
    text_streak = 0

    # Zero-new-card idle counter – stop after this many scrolls with no new cards
    IDLE_SCROLL_LIMIT = 15
    idle = 0

    if max_reviews > 0:
        print(f"  📜 Collecting top {max_reviews} reviews …")
    else:
        print(f"  📜 Collecting reviews until {cutoff.strftime('%Y-%m-%d')} …")

    for i in range(max_scrolls):
        # ── Scroll the reviews container ──────────────────────────────────────
        # Try increasingly broad selectors until one scrolls successfully.
        scrolled = False
        for sel in [
            "div.m6QErb.DxyBCb",
            "div.m6QErb.dS8AEf",
            "div.m6QErb.XiKgde",
            "div.m6QErb",
        ]:
            containers = await page.locator(sel).all()
            for container in reversed(containers):   # rightmost/last first
                try:
                    before = await container.evaluate("el => el.scrollTop")
                    await container.evaluate("el => { el.scrollTop += 1500; }")
                    after = await container.evaluate("el => el.scrollTop")
                    if after > before:
                        scrolled = True
                        break
                except Exception:
                    continue
            if scrolled:
                break

        if not scrolled:
            # Fall back: focus the panel area and send keyboard End
            try:
                await page.keyboard.press("End")
            except Exception:
                pass

        await asyncio.sleep(random.uniform(1.2, 2.2))

        # ── Grab all review cards ──────────────────────────────────────────────
        cards = await page.locator("div.jftiEf").all()
        if not cards:
            cards = await page.locator("div[data-review-id]").all()

        new_count = 0
        for card in cards:
            try:
                # ── Review ID ─────────────────────────────────────────────
                rid = (await card.get_attribute("data-review-id")) or ""

                # ── Reviewer name ─────────────────────────────────────────
                name_el = card.locator(".d4r55").first
                name = (await name_el.inner_text(timeout=1500)).strip() if await name_el.count() else ""

                # ── Date text ─────────────────────────────────────────────
                date_el = card.locator(".rsqaWe").first
                date_txt = (await date_el.inner_text(timeout=1500)).strip() if await date_el.count() else ""

                key = rid or f"{name}::{date_txt}"
                if key in seen or not (name or date_txt):
                    continue
                seen.add(key)
                new_count += 1

                # ── Cutoff-aware date window check ─────────────────────────
                within = is_within_cutoff(date_txt, cutoff, now)

                if within is False:
                    # Review is older than the requested period → skip & streak
                    text_streak += 1
                    continue

                # Reset streak: review is within the period (or unknown)
                if within is True:
                    text_streak = 0

                # ── Expand truncated review ───────────────────────────────
                more = card.locator("button.w8nwRe")
                if await more.count():
                    try:
                        await more.first.click(timeout=1500)
                        await asyncio.sleep(0.3)
                    except Exception:
                        pass

                # ── Review text ──────────────────────────────────────────
                text_el = card.locator(".wiNNm, .wiI7pd, .MyEned").first
                review_text = (await text_el.inner_text(timeout=1500)).strip() if await text_el.count() else ""

                # ── Rating ───────────────────────────────────────────────
                rating = ""
                star_el = card.locator(".kvMYJc").first
                if await star_el.count():
                    aria = (await star_el.get_attribute("aria-label")) or ""
                    m = re.search(r"(\d+(?:\.\d+)?)", aria)
                    if m:
                        try:
                            rating = str(int(float(m.group(1))))
                        except Exception:
                            rating = m.group(1)

                # ── Owner reply ──────────────────────────────────────────
                owner_replied = "No"
                owner_response = ""
                response_date = ""

                for reply_sel in [
                    ".CDe7pd",
                    "div[class*='CDe7pd']",
                    "div.bfPHte",
                    "div[class*='bfPHte']",
                ]:
                    reply_block = card.locator(reply_sel).first
                    if await reply_block.count():
                        owner_replied = "Yes"
                        resp_text_el = reply_block.locator(".wiI7pd, .MyEned, .CDe7pd").first
                        if await resp_text_el.count():
                            owner_response = (await resp_text_el.inner_text(timeout=1500)).strip()
                        else:
                            owner_response = (await reply_block.inner_text(timeout=1500)).strip()
                        resp_date_el = reply_block.locator(".rsqaWe, [class*='rsqaWe']").first
                        if await resp_date_el.count():
                            resp_date_txt = (await resp_date_el.inner_text(timeout=1500)).strip()
                            resp_dt = parse_relative_date(resp_date_txt, now)
                            if resp_dt:
                                response_date = resp_dt.strftime("%Y-%m-%d")
                        break

                # ── Review link ──────────────────────────────────────────
                review_link = ""
                if rid:
                    base_url = re.sub(r"\?.*$", "", page_url)
                    review_link = f"{base_url}?hl=en#lrd=review:{rid}"

                # ── Parse review date for the record ─────────────────────
                rev_date = parse_relative_date(date_txt, now)
                rev_date_str = rev_date.strftime("%Y-%m-%d") if rev_date else ""

                rec = {
                    "review_id":       rid,
                    "restaurant_name": restaurant_name,
                    "category":        getattr(args, "category", "Unknown"),
                    "rating":          rating,
                    "review_text":     review_text,
                    "review_date":     rev_date_str,
                    "author_name":     name,
                    "owner_replied":   owner_replied,
                    "owner_response":  owner_response,
                    "response_date":   response_date,
                    "review_link":     review_link,
                    "_date_iso":       rev_date.isoformat() if rev_date else None,
                    "_date_text":      date_txt,
                }
                reviews.append(rec)

                if max_reviews > 0 and len(reviews) >= max_reviews:
                    break

            except Exception:
                continue

        # ── Progress line ─────────────────────────────────────────────────────
        print(
            f"\r  [Scroll {i+1:3d}]  Collected: {len(reviews)}"
            f"  text_streak_old: {text_streak}  idle: {idle}   ",
            end="",
        )

        # ── Stop conditions ───────────────────────────────────────────────────
        if max_reviews > 0 and len(reviews) >= max_reviews:
            print(f"\n  ✅ Reached target of {max_reviews} reviews — stopping.")
            break
        if text_streak >= TEXT_STREAK_LIMIT:
            print(f"\n  ✅ Saw {TEXT_STREAK_LIMIT} consecutive 'month/year ago' reviews — stopping.")
            break

        if new_count == 0:
            idle += 1
        else:
            idle = 0

        if idle >= IDLE_SCROLL_LIMIT:
            print(f"\n  ✅ No new review cards after {IDLE_SCROLL_LIMIT} scrolls — stopping.")
            break

    print()
    return reviews


# ─────────────────────────────────────────────────────────────────────────────
# CSV output
# ─────────────────────────────────────────────────────────────────────────────

COLUMNS = [
    # (header, field_key, width)
    ("Review ID",       "review_id",       28),
    ("Restaurant Name", "restaurant_name", 28),
    ("Category",        "category",        16),
    ("Rating",          "rating",          10),
    ("Review Text",     "review_text",     60),
    ("Review Date",     "review_date",     16),
    ("Author Name",     "author_name",     22),
    ("Owner Replied?",  "owner_replied",   16),
    ("Owner Response",  "owner_response",  55),
    ("Response Date",   "response_date",   16),
    ("Review Link",     "review_link",     45),
]


def _base_name(place: str, period: str, output_dir: Path) -> Path:
    safe_place  = re.sub(r"[^\w\s-]", "", place).strip().replace(" ", "_")
    safe_period = re.sub(r"\s+", "_", period.strip())
    return output_dir / f"reviews_{safe_place}_{safe_period}"


def save_csv(
    reviews: list[dict],
    base: Path,
    place_name: str,
    period_str: str,
    now: datetime,
    cutoff: datetime,
) -> Path:
    """Create a CSV file matching the column spec."""
    path = base.with_suffix(".csv")
    with open(path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Write headers
        headers = [c[0] for c in COLUMNS]
        writer.writerow(headers)
        
        for r in reviews:
            row = []
            for hdr, field, _w in COLUMNS:
                val = r.get(field, "")
                if val is None:
                    val = ""
                row.append(str(val))
            writer.writerow(row)
            
    return path


def print_terminal_summary(
    reviews: list[dict],
    place: str,
    period: str,
    now: datetime,
    cutoff: datetime,
    output_path: Path,
):
    sep = "═" * 64
    replied = sum(1 for r in reviews if r.get("owner_replied") == "Yes")
    print(f"\n{sep}")
    print(f"  📍  {place}")
    print(f"  🕐  Last {period}  ({cutoff.strftime('%Y-%m-%d')} → {now.strftime('%Y-%m-%d')})")
    print(f"  📊  {len(reviews)} review(s) found  |  {replied} with owner reply")
    print(sep)

    rated = [r for r in reviews if r.get("rating") and re.match(r"^\d", str(r.get("rating", "")))]
    if rated:
        avg = sum(float(r["rating"]) for r in rated) / len(rated)
        print(f"  ⭐  Average rating: {avg:.2f} / 5.00  ({len(rated)} rated)")

        dist = {str(i): 0 for i in range(1, 6)}
        for r in rated:
            k = str(int(float(r["rating"])))
            dist[k] = dist.get(k, 0) + 1
        for star in ["5", "4", "3", "2", "1"]:
            cnt = dist[star]
            bar = "█" * cnt + "░" * max(0, 20 - cnt)
            print(f"  {star}★  {bar}  {cnt}")

    if reviews:
        print(f"\n  📝  Latest reviews:\n")
        for r in reviews[:5]:
            stars = "⭐" * int(float(r["rating"])) if r.get("rating") else "?"
            print(f"  {stars}  {r.get('review_date', '')}  —  {r.get('author_name', '')}")
            snippet = (r.get("review_text") or "")[:180].replace("\n", " ")
            if len(r.get("review_text", "") or "") > 180:
                snippet += "…"
            print(f"  💬 {snippet}")
            if r.get("owner_replied") == "Yes":
                resp = (r.get("owner_response") or "")[:120].replace("\n", " ")
                print(f"  🏪 Owner: {resp}")
            print()

    print(sep)
    print(f"  💾  Saved → {output_path}")
    print(f"{sep}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="Scrape Google Maps reviews · outputs 10-column CSV"
    )
    parser.add_argument("--place",  "-p", default="",
                        help='Place to search (optional if env.URL is set)')
    parser.add_argument("--period", "-t", required=False,
                        help='Time window — shorthand: 4m, 1y, 3h, 2d, 1w')
    parser.add_argument("--count", "-c", type=int, default=0,
                        help='Number of reviews to fetch (e.g. 1000). Overrides --period if provided.')
    parser.add_argument("--output", "-o", default="./output",
                        help="Output directory (default: ./output)")
    parser.add_argument("--category", "-cg", default="Cafe",
                        help="Place category (e.g. Cafe, F&B, Bar)")
    parser.add_argument("--headless", action="store_true", default=False,
                        help="Run headless (default: visible browser)")
    parser.add_argument("--timeout", type=int, default=60000,
                        help="Navigation timeout ms (default: 60000)")
    parser.add_argument("--max-scrolls", type=int, default=400,
                        help="Max scroll iterations (default: 400)")
    args = parser.parse_args()

    now = datetime.now()
    sub_day_note = ""

    if args.count > 0:
        cutoff = datetime.min
        period_label = f"{args.count}_reviews"
    elif args.period:
        try:
            delta = parse_period(args.period)
        except ValueError as e:
            print(f"❌  {e}")
            sys.exit(1)
        cutoff = now - delta
        period_label = args.period
        
        # Google Maps date resolution note
        if delta < timedelta(hours=24):
            sub_day_note = (
                f"\n  ⚠️   NOTE: Google Maps date precision is day-level, not hour-level.\n"
                f"       Showing all reviews from the last 24 h (best available).\n"
            )
            cutoff = now - timedelta(hours=24)
    else:
        print("❌  Please provide either --period or --count")
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    direct_url = getattr(env, "URL", None) if env else None
    if not args.place and not direct_url:
        print("❌  Please provide --place or set URL in env.py")
        sys.exit(1)

    print(f"\n🚀  Google Maps Review Scraper")
    if direct_url:
        print(f"    URL    : {direct_url[:80]}...")
    if args.place:
        print(f"    Place  : {args.place}")
    
    if args.count > 0:
        print(f"    Count  : fetching {args.count} reviews")
    else:
        print(f"    Period : last {args.period}  (since {cutoff.strftime('%Y-%m-%d %H:%M')})")
    if sub_day_note:
        print(sub_day_note, end="")
    print(f"    Output : {output_dir.resolve()}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=args.headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page = await ctx.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )

        try:
            page_url = await navigate_to_place(
                page,
                args.place,
                timeout=args.timeout,
                direct_url=direct_url,
            )
            restaurant_name = await get_restaurant_name(page)
            if not restaurant_name:
                restaurant_name = args.place or "Unknown"
            print(f"  🏪 Restaurant: {restaurant_name}")

            await open_reviews_tab(page)
            await sort_by_newest(page)
            await asyncio.sleep(2)
            reviews = await scrape_reviews(
                page, cutoff, now,
                restaurant_name=restaurant_name,
                page_url=page_url,
                max_scrolls=args.max_scrolls,
                max_reviews=args.count,
            )
        except Exception as e:
            print(f"\n❌  Scraping error: {e}")
            import traceback; traceback.print_exc()
            await browser.close()
            sys.exit(1)

        await browser.close()

    # Filter & sort
    def _keep(r):
        within = is_within_cutoff(r.get("_date_text", ""), cutoff, now)
        if within is True:
            return True
        if within is False:
            return False
        # within is None (ambiguous) → fall back to datetime comparison
        iso = r.get("_date_iso")
        return (not iso) or iso >= cutoff.isoformat()

    final = [r for r in reviews if _keep(r)]
    final.sort(key=lambda r: r.get("_date_iso") or "", reverse=True)

    if not final:
        print("\n⚠️   No reviews found in this period.")
        if sub_day_note:
            print("    Google Maps does not expose hour-level dates — 24h window was used.")
        print("    Try a different place name or a longer period.\n")
        sys.exit(0)

    label      = args.place or restaurant_name
    safe_place = re.sub(r"[^\w\s-]", "", label).strip().replace(" ", "_")

    print()
    # ── Delete old data for this place ────────────────────────────────────────
    for old_file in output_dir.glob(f"reviews_{safe_place}_*.*"):
        try:
            old_file.unlink()
            print(f"  🗑️  Deleted old data: {old_file.name}")
        except Exception:
            pass

    base      = _base_name(label, period_label, output_dir)
    csv_path  = save_csv(final, base, label, period_label, now, cutoff)

    print_terminal_summary(final, label, period_label, now, cutoff, csv_path)


if __name__ == "__main__":
    asyncio.run(main())
