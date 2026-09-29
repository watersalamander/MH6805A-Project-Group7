"""
Step 1-3 data pull for the unlock -> realized-vol project.

Usage:
  python scripts/tok_pull.py --budget 40 --max-tokens 13 [--min-age-days 180]

- Every Tokenomist call is appended to data/call_log.txt.
- Stops immediately on HTTP 429 / quota errors (raises QuotaError after logging).
- Never re-requests a raw file that already exists under data/raw/ (idempotent).
- Binance calls are public and untracked against the Tokenomist budget, but are
  rate-limited here (sleep + honour x-mbx-used-weight-1m / Retry-After).
"""
import argparse, json, os, subprocess, sys, time, datetime as dt
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")
CALL_LOG = os.path.join(DATA, "call_log.txt")
TODAY = dt.date(2026, 9, 14)
BINANCE = "https://api.binance.com"
MARKET_CONTROL_IDS = {"bitcoin", "ethereum"}
# Tokens whose Tokenomist entry and Binance pair are different assets (found by scripts/audit_alignment.py)
ENTITY_MISMATCH_IDS = {
    "centrifuge": "entity_mismatch (Tokenomist entry is 'Centrifuge [OLD]', schedule ended 2025-07; Binance CFGUSDT listed 2026-03-16 is the migrated token)",
}


class QuotaError(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    pass


# ---------------------------------------------------------------- Tokenomist
class TokClient:
    def __init__(self, budget):
        self.budget = budget
        self.calls = 0
        os.makedirs(DATA, exist_ok=True)
        if not os.path.exists(CALL_LOG):
            with open(CALL_LOG, "w") as f:
                f.write("# Tokenomist API call log (this run + reruns append)\n")
                f.write("# timestamp | command | token | endpoint | exit_status | note\n")
        else:  # count prior successful calls so reruns respect the cumulative budget
            for line in open(CALL_LOG):
                if line.startswith("#") or not line.strip():
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 5 and parts[4] == "exit=0":
                    self.calls += 1

    def _log(self, cmd, token, endpoint, status, note):
        ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(CALL_LOG, "a") as f:
            f.write(f"{ts} | {cmd} | {token} | {endpoint} | exit={status} | {note}\n")

    min_gap = 0.6          # seconds between calls -> <= 100/min (plan limit 120/min)
    _last = 0.0

    def call(self, args, token, endpoint, retries=1):
        """Run `tok <args> -o json`; return parsed JSON. Counts against the budget. Retries once on non-quota errors."""
        for attempt in range(retries + 1):
            out = self._call_once(args, token, endpoint)
            if out is not None:
                return out
            time.sleep(3)
        return None

    def _call_once(self, args, token, endpoint):
        if self.calls >= self.budget:
            raise BudgetExceeded(f"budget of {self.budget} successful calls reached")
        gap = time.time() - self._last
        if gap < self.min_gap:
            time.sleep(self.min_gap - gap)
        self._last = time.time()
        cmd = ["tok"] + args + ["-o", "json"]
        cmd_str = " ".join(cmd)
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, shell=True)
        except subprocess.TimeoutExpired:
            self._log(cmd_str, token, endpoint, "timeout", "timed out after 300s")
            return None
        err = (p.stderr or "")
        out = (p.stdout or "")
        combined = (err + out[:2000]).lower()
        quota = ("429" in err) or ("too many requests" in combined) or ("quota" in combined) \
            or ("rate limit" in combined) or ("credit" in combined and "exceed" in combined)
        if p.returncode != 0 or quota:
            note = ("QUOTA/429: " if quota else "error: ") + (err.strip()[:300] or out.strip()[:300])
            self._log(cmd_str, token, endpoint, p.returncode, note.replace("\n", " "))
            if quota:
                raise QuotaError(note)
            return None
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            self._log(cmd_str, token, endpoint, p.returncode, "non-JSON response: " + out[:200].replace("\n", " "))
            return None
        n = len(data) if isinstance(data, list) else 1
        self.calls += 1
        self._log(cmd_str, token, endpoint, 0, f"ok records={n} bytes={len(out)} calls_used={self.calls}/{self.budget}")
        return data


# ------------------------------------------------------------------ Binance
_last_binance = [0.0]


def binance_get(path, params, min_gap=0.35):
    """GET with polite pacing; respects Retry-After and backs off when weight is high."""
    for attempt in range(6):
        gap = time.time() - _last_binance[0]
        if gap < min_gap:
            time.sleep(min_gap - gap)
        r = requests.get(BINANCE + path, params=params, timeout=60)
        _last_binance[0] = time.time()
        used = int(r.headers.get("x-mbx-used-weight-1m", "0") or 0)
        if r.status_code in (429, 418):
            wait = int(r.headers.get("Retry-After", "30") or 30)
            print(f"  binance {r.status_code}, sleeping {wait}s", flush=True)
            time.sleep(wait + 1)
            continue
        if used > 4000:  # 6000/min limit; stay well clear
            time.sleep(20)
        r.raise_for_status()
        return r.json()
    raise RuntimeError("binance: too many retries")


def binance_first_candle_date(symbol):
    k = binance_get("/api/v3/klines", {"symbol": symbol, "interval": "1d", "startTime": 0, "limit": 1})
    if not k:
        return None
    return dt.datetime.fromtimestamp(k[0][0] / 1000, dt.timezone.utc).date()


def binance_klines_daily(symbol, start_date, end_date):
    rows = []
    start = int(dt.datetime.combine(start_date, dt.time(), dt.timezone.utc).timestamp() * 1000)
    end_ms = int(dt.datetime.combine(end_date + dt.timedelta(days=1), dt.time(), dt.timezone.utc).timestamp() * 1000)
    while start < end_ms:
        k = binance_get("/api/v3/klines", {"symbol": symbol, "interval": "1d", "startTime": start,
                                           "endTime": end_ms, "limit": 1000})
        if not k:
            break
        rows.extend(k)
        if len(k) < 1000:
            break
        start = k[-1][0] + 86400000
    out = []
    for r in rows:
        d = dt.datetime.fromtimestamp(r[0] / 1000, dt.timezone.utc).date()
        out.append({"date": d.isoformat(), "open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
                    "close": float(r[4]), "volume": float(r[5]), "quote_volume": float(r[7]), "trades": int(r[8])})
    return out


def write_csv(path, rows, cols):
    import csv
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c) for c in cols})


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, required=True,
                    help="max successful Tokenomist calls (cumulative across reruns via call_log)")
    ap.add_argument("--max-tokens", type=int, required=True)
    ap.add_argument("--min-age-days", type=int, default=180)
    ap.add_argument("--fwd-end", default="2027-06-30", help="forward end date for emission/unlock pulls")
    ap.add_argument("--hist-start", default="2024-09-14",
                    help="earliest date the plan allows for emission data (API error on 2026-09-14 said 2024-09-14..2027-06-30)")
    ap.add_argument("--page-size", type=int, default=10000)
    ap.add_argument("--include-fully-unlocked", action="store_true",
                    help="also pull tokens with totalLockedAmount == 0 (their emis_next_* will be ~0)")
    ap.add_argument("--probe-all", action="store_true", help="fetch Binance listing dates for every candidate, not just 3x max-tokens")
    ap.add_argument("--price-band", type=float, default=3.0,
                    help="exclude when Binance last price and token-list implied price (marketCap/circulatingSupply) differ by more than this factor (symbol-collision guard)")
    args = ap.parse_args()
    os.makedirs(RAW, exist_ok=True)
    tok = TokClient(args.budget)
    print(f"budget={args.budget} already_used={tok.calls}", flush=True)

    # ---- Step 1: token universe -------------------------------------------
    tl_path = os.path.join(RAW, "token_list.json")
    if os.path.exists(tl_path):
        tokens = json.load(open(tl_path))
        print(f"token_list.json exists ({len(tokens)} tokens) - reusing", flush=True)
    else:
        tokens = tok.call(["token", "list"], "-", "token list")
        if tokens is None:
            sys.exit("token list failed")
        json.dump(tokens, open(tl_path, "w"))
        print(f"token list: {len(tokens)} tokens", flush=True)

    pairs_path = os.path.join(RAW, "binance_usdt_pairs.json")
    if os.path.exists(pairs_path):
        pairs = json.load(open(pairs_path))
    else:
        info = binance_get("/api/v3/exchangeInfo", {})
        pairs = {s["symbol"]: {"base": s["baseAsset"], "status": s["status"]} for s in info["symbols"]
                 if s["quoteAsset"] == "USDT" and s["status"] == "TRADING" and s.get("isSpotTradingAllowed")}
        json.dump(pairs, open(pairs_path, "w"), indent=1)

    excl = []   # (id, symbol, marketCap, reason)
    cands = []
    for t in tokens:
        sym = (t.get("symbol") or "").upper()
        mc = t.get("marketCap")
        if sym + "USDT" not in pairs:
            excl.append((t["id"], sym, mc, "no_binance_usdt_spot_pair"))
            continue
        if t["id"] in ENTITY_MISMATCH_IDS:
            excl.append((t["id"], sym, mc, ENTITY_MISMATCH_IDS[t["id"]]))
            continue
        if t["id"] in MARKET_CONTROL_IDS:
            excl.append((t["id"], sym, mc, "used_as_market_control_btc_eth"))
            continue
        if mc is None:
            excl.append((t["id"], sym, mc, "marketCap_null"))
            continue
        if (not t.get("totalLockedAmount") or t["totalLockedAmount"] <= 0) and not args.include_fully_unlocked:
            excl.append((t["id"], sym, mc, "fully_unlocked_totalLockedAmount_0 (no forward emission schedule; no call spent)"))
            continue
        cands.append(t)
    cands.sort(key=lambda t: -t["marketCap"])
    print(f"candidates with Binance pair & locked supply: {len(cands)}", flush=True)

    # Binance listing date as TGE proxy (free). Only probe as many as we could plausibly use.
    listing_path = os.path.join(RAW, "binance_listing_dates.json")
    listing = json.load(open(listing_path)) if os.path.exists(listing_path) else {}
    cutoff = TODAY - dt.timedelta(days=args.min_age_days)
    eligible = []
    probed = 0
    ticker_path = os.path.join(RAW, "binance_ticker_prices.json")
    ticker = json.load(open(ticker_path)) if os.path.exists(ticker_path) else {}
    for t in cands:
        if not args.probe_all and len(eligible) >= args.max_tokens * 3:
            break  # headroom for emission-empty drops
        probed += 1
        sym = t["symbol"].upper() + "USDT"
        if sym not in listing:
            d = binance_first_candle_date(sym)
            listing[sym] = d.isoformat() if d else None
            json.dump(listing, open(listing_path, "w"), indent=1)
        ld = listing[sym]
        if ld is None:
            excl.append((t["id"], t["symbol"], t["marketCap"], "binance_no_klines"))
            continue
        if dt.date.fromisoformat(ld) > cutoff:
            excl.append((t["id"], t["symbol"], t["marketCap"], f"too_young_binance_listing_{ld}"))
            continue
        # symbol-collision guard: Binance last price vs token-list implied price (free)
        circ = t.get("circulatingSupply") or 0
        if circ > 0 and t["marketCap"] > 0:
            if sym not in ticker:
                ticker[sym] = float(binance_get("/api/v3/ticker/price", {"symbol": sym})["price"])
                json.dump(ticker, open(ticker_path, "w"), indent=1)
            implied = t["marketCap"] / circ
            ratio = ticker[sym] / implied if implied > 0 else float("inf")
            if ratio > args.price_band or ratio < 1 / args.price_band:
                excl.append((t["id"], t["symbol"], t["marketCap"],
                             f"binance_symbol_price_mismatch (binance={ticker[sym]:.6g} implied={implied:.6g} ratio={ratio:.2f})"))
                continue
        eligible.append(t)
    print(f"eligible after age filter (probed top {probed}): {len(eligible)}", flush=True)

    # ---- Step 2: per-token Tokenomist pulls ---------------------------------
    selected = []
    ranges = {}
    try:
        for t in eligible:
            if len(selected) >= args.max_tokens:
                break
            tid = t["id"]
            tdir = os.path.join(RAW, tid)
            os.makedirs(tdir, exist_ok=True)
            # 2a emission daily (decides inclusion)
            ep = os.path.join(tdir, "emission_daily.json")
            if os.path.exists(ep):
                emis = json.load(open(ep))
            else:
                emis = tok.call(["emission", "daily", tid, "--start", args.hist_start, "--end", args.fwd_end,
                                 "--page-size", str(args.page_size)], tid, "emission daily")
                if emis is None:
                    excl.append((tid, t["symbol"], t["marketCap"], "api_error_emission_daily"))
                    continue
                page = 1
                while isinstance(emis, list) and len(emis) >= args.page_size * page and tok.calls < tok.budget:
                    page += 1
                    more = tok.call(["emission", "daily", tid, "--start", args.hist_start, "--end", args.fwd_end,
                                     "--page-size", str(args.page_size), "--page", str(page)], tid, "emission daily")
                    if not more:
                        break
                    emis.extend(more)
                json.dump(emis, open(ep, "w"))
            if not emis:
                excl.append((tid, t["symbol"], t["marketCap"], "no_emission_data (Daily Emission empty)"))
                continue
            # 2b allocations
            ap_ = os.path.join(tdir, "allocations.json")
            if not os.path.exists(ap_):
                alloc = tok.call(["allocation", "detail", tid], tid, "allocation detail")
                if alloc is None or not isinstance(alloc, dict):
                    excl.append((tid, t["symbol"], t["marketCap"], "api_error_allocation_detail"))
                    continue
                json.dump(alloc, open(ap_, "w"))
            # 2c unlock events
            up = os.path.join(tdir, "unlock_events.json")
            if not os.path.exists(up):
                ue = tok.call(["unlock", "events", tid, "--start", args.hist_start, "--end", args.fwd_end,
                               "--page-size", str(args.page_size)], tid, "unlock events")
                if ue is None:
                    excl.append((tid, t["symbol"], t["marketCap"], "api_error_unlock_events"))
                    continue
                json.dump(ue, open(up, "w"))
            dates = sorted(r["startDate"][:10] for r in emis)
            ranges[tid] = (dates[0], dates[-1], len(emis))
            selected.append(t)
            print(f"  selected {tid}: emission {dates[0]}..{dates[-1]} ({len(emis)} rows); calls {tok.calls}/{tok.budget}", flush=True)
    except (QuotaError, BudgetExceeded) as e:
        print(f"STOP: {e}", flush=True)
        with open(CALL_LOG, "a") as f:
            f.write(f"# STOPPED: {e}\n")

    sel_ids = {t["id"] for t in selected}
    excl_ids = {e[0] for e in excl}
    for t in eligible:
        if t["id"] not in sel_ids and t["id"] not in excl_ids:
            excl.append((t["id"], t["symbol"], t["marketCap"], "not_reached_budget_or_max_tokens"))
    excl_ids = {e[0] for e in excl}
    for t in cands:
        if t["id"] not in sel_ids and t["id"] not in excl_ids:
            excl.append((t["id"], t["symbol"], t["marketCap"], "not_probed_below_rank_cutoff"))

    # ---- Step 3: prices -------------------------------------------------------
    for t in selected:
        tid = t["id"]
        sym = t["symbol"].upper() + "USDT"
        pp = os.path.join(RAW, tid, "prices.csv")
        if os.path.exists(pp):
            continue
        emis_first = dt.date.fromisoformat(ranges[tid][0]) if tid in ranges else None
        list_d = dt.date.fromisoformat(listing[sym])
        start = min([d for d in (emis_first, list_d) if d])
        rows = binance_klines_daily(sym, start, TODAY)
        write_csv(pp, rows, ["date", "open", "high", "low", "close", "volume", "quote_volume", "trades"])
        print(f"  prices {sym}: {len(rows)} rows from {rows[0]['date'] if rows else None}", flush=True)
    for sym in ("BTCUSDT", "ETHUSDT"):
        pp = os.path.join(RAW, f"{sym}_prices.csv")
        if os.path.exists(pp):
            continue
        rows = binance_klines_daily(sym, dt.date(2017, 8, 1), TODAY)
        write_csv(pp, rows, ["date", "open", "high", "low", "close", "volume", "quote_volume", "trades"])
        print(f"  prices {sym}: {len(rows)} rows", flush=True)

    # ---- universe files ---------------------------------------------------------
    urows = []
    for i, t in enumerate(selected, 1):
        sym = t["symbol"].upper() + "USDT"
        r = ranges.get(t["id"], (None, None, None))
        urows.append({"rank": i, "token_id": t["id"], "symbol": t["symbol"], "name": t["name"], "binance_symbol": sym,
                      "marketCap": t["marketCap"], "maxSupply": t.get("maxSupply"), "listedMethod": t["listedMethod"],
                      "binance_listing_date": listing.get(sym), "emission_first_date": r[0], "emission_last_date": r[1],
                      "emission_rows": r[2], "totalLockedAmount": t["totalLockedAmount"], "unlockedAmount": t["unlockedAmount"]})
    write_csv(os.path.join(DATA, "universe.csv"), urows, list(urows[0].keys()) if urows else ["token_id"])
    ex = [{"token_id": e[0], "symbol": e[1], "marketCap": e[2], "reason": e[3]} for e in excl]
    write_csv(os.path.join(DATA, "universe_exclusions.csv"), ex, ["token_id", "symbol", "marketCap", "reason"])
    print(f"done: {len(selected)} selected, {len(excl)} excluded, tokenomist calls used {tok.calls}/{tok.budget}", flush=True)


if __name__ == "__main__":
    main()
