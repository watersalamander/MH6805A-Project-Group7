# dataset_v1.csv column guide

One row per token per calendar day (UTC). "Date D" means the row's date. Every feature is computed from information available at the Binance daily close of D; every target is computed from prices *after* D. Realized volatility is annualized with 365 days and expressed as a decimal (1.0 = 100% annualized vol).

## Keys

| Column | Meaning |
|---|---|
| `token_id` | Tokenomist's slug for the token (e.g. `sui`, `avalanche-2`). Use this for joins; symbols are not unique. |
| `symbol` | Ticker symbol from Tokenomist (e.g. `SUI`). The Binance pair used is `symbol + "USDT"`. |
| `date` | Row date, ISO format, UTC. Features are "as of the close of this day". |

## Targets (forward-looking; never use as inputs)

| Column | Meaning |
|---|---|
| `rv_fwd_7d` | Annualized realized volatility of daily close-to-close log returns over the next 7 days (D+1 to D+7). Formula: sqrt(365/7 x sum of squared returns). |
| `rv_fwd_14d` | Same over the next 14 days. This is the primary target. |
| `rv_fwd_30d` | Same over the next 30 days. Rows where this cannot be computed (the last 30 days of price history) are dropped. |
| `rv_fwd_14d_parkinson` | Alternative 14-day forward vol using each day's high and low instead of closes: sqrt(365/(4 x 14 x ln2) x sum of ln(high/low)^2). Less noisy than close-to-close; sensitive to intraday wicks. |
| `fwd_ret_14d` | Log return from the close of D to the close of D+14. Secondary target (direction, not vol). |

## Emission features (forward-looking schedule, known at D)

These come from Tokenomist's Daily Emission endpoint. "Scheduled" means the schedule as Tokenomist curates it today, applied to the calendar. A window "next k days" is D+1 to D+k, so an unlock that happens on D itself is *not* included (it is already known by the close of D).

| Column | Meaning |
|---|---|
| `emis_next_7d` | Total tokens scheduled to unlock in the next 7 days. Unit: tokens. |
| `emis_next_30d` | Total tokens scheduled to unlock in the next 30 days. |
| `emis_next_90d` | Total tokens scheduled to unlock in the next 90 days. |
| `float_pit` | Point-in-time float: cumulative tokens unlocked up to and including D (Tokenomist `totalCumulativeUnlockedAmount`). This is the circulating-supply proxy at D, not today's circulating supply. Rows with 0 or null are dropped. |
| `emis_next_7d_pct_float` | `emis_next_7d / float_pit`. Fraction of the current float that will unlock in the next 7 days. |
| `emis_next_30d_pct_float` | `emis_next_30d / float_pit`. The main unlock-pressure feature. Can exceed 1 in the first weeks after a token launch when the float is tiny. |
| `emis_next_90d_pct_float` | `emis_next_90d / float_pit`. |
| `emis_next_30d_pct_total` | `emis_next_30d / total_supply`. Same pressure measure but normalized by a fixed denominator, so it is comparable across time within a token. |
| `days_to_next_cliff` | Days from D to the next *cliff* unlock event strictly after D (from the Unlock Events endpoint). Null if the token has no cliff events or none remain in the pulled window. |
| `next_cliff_pct_float` | Size of that next cliff as a fraction of `float_pit`. Null when `days_to_next_cliff` is null. |
| `has_unlock_events` | True if Tokenomist lists at least one cliff event for the token. False for coins with only continuous issuance or linear vesting (50 of 177 tokens); their cliff columns are structurally null. |
| `emission_schedule_ended` | True when D is after the last day of the token's published emission schedule. On such rows `emis_next_*` is 0 by construction (no further scheduled unlocks are known) and `float_pit` is carried forward unchanged. |

### 30-day emission split by recipient bucket

Tokenomist tags each allocation with a standard name. These columns split `emis_next_30d` by who receives the tokens. They sum to `emis_next_30d` (plus `emis_next_30d_unattributed`).

| Column | Meaning |
|---|---|
| `emis_next_30d_founderTeam` | Next-30-day unlocks going to the team, founders and advisors. |
| `emis_next_30d_privateInvestors` | Going to seed / private-round investors. |
| `emis_next_30d_community` | Going to community programs: airdrops, staking rewards, ecosystem incentives, mining/staking issuance. |
| `emis_next_30d_publicInvestors` | Going to public-sale participants. |
| `emis_next_30d_reserve` | Going to treasury, foundation or reserve wallets. |
| `emis_next_30d_others` | Any bucket Tokenomist labels "Others" or that does not map to the five above. |
| `emis_next_30d_unattributed` | `emis_next_30d` minus the sum of the six buckets. Non-zero only when a day's row-level unlock amount is not fully broken down by allocation. Effectively 0 in this pull. |

## Backward-looking price controls (known at D)

Computed from Binance daily klines up to and including the close of D.

| Column | Meaning |
|---|---|
| `rv_past_7d` | Annualized realized vol of the last 7 daily log returns (D-6 to D). Null for the first days after Binance listing. |
| `rv_past_14d` | Same over the last 14 days. The natural persistence baseline for `rv_fwd_14d`. |
| `rv_past_30d` | Same over the last 30 days. |
| `ret_past_7d` | Log return from the close of D-7 to the close of D. |
| `ret_past_30d` | Log return from the close of D-30 to the close of D. |
| `btc_rv_past_14d` | `rv_past_14d` of BTCUSDT on the same date. Market-wide vol regime control. |
| `eth_rv_past_14d` | `rv_past_14d` of ETHUSDT on the same date. |
| `log_mcap_pit` | Natural log of (`float_pit` x close price on D), in USDT. A point-in-time market-cap proxy; lets a model condition on size without leaking today's market cap. |

## Static token features (constant within a token)

| Column | Meaning |
|---|---|
| `days_since_tge` | Days from `tge_proxy_date` to D. For coins older than their Binance listing this is a lower bound on true age. |
| `listedMethod` | How Tokenomist curated the token: `INTERNAL` (hand-curated), `AI`, or `EXTERNAL`. A data-quality hint, not an economic feature. Reflects today's status. |
| `unlockPrecision` | Most common time granularity of the token's cliff events (`day`, `month`, `week`, `second`, `hour`, `block`, `unknown`). Null when the token has no cliff events. |
| `alloc_share_founderTeam` | Fraction of the token's total tracked allocation assigned to team/founders/advisors, from the current Allocations snapshot. |
| `alloc_share_privateInvestors` | Same for private investors. |
| `alloc_share_community` | Same for community. |
| `alloc_share_publicInvestors` | Same for public-sale investors. |
| `alloc_share_reserve` | Same for treasury/reserve. |
| `alloc_share_others` | Same for "Others" or unmapped buckets. The six shares sum to 1. |
| `total_supply` | Denominator used for `emis_next_30d_pct_total`: Tokenomist `maxSupply` when it exists, otherwise the sum of all tracked allocation amounts. |
| `total_supply_basis` | Which of the two denominators was used (`maxSupply` or `sum_allocationAmount (maxSupply null)`). Uncapped-supply coins such as SOL, DOGE and ATOM use the second. |
| `tge_proxy_date` | Earliest of the Binance first daily candle and the first emission row. Used as the launch-date proxy because Tokenomist exposes no TGE field. |

## Caveats that apply to several columns

- Allocation shares, `total_supply`, `listedMethod` and `unlockPrecision` are snapshots as of the pull date (2026-09-14). Tokenomist has no history for them, so they are treated as time-invariant.
- Emission schedules are the version curated today. Tokenomist revises schedules after the fact, so `emis_next_*` is lookahead-safe mechanically (windows start at D+1) but not in the information sense: a revision made in 2026 is applied to 2025 rows.
- Nothing is winsorized or imputed. Nulls are structural (no cliff events, first days after listing) and are documented in the feasibility report.
