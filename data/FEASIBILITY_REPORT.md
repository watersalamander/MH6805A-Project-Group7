# Feasibility report: forward realized volatility vs scheduled token emissions (dataset_v1)

Generated 2026-09-14 from `scripts/tok_pull.py` -> `scripts/build_dataset.py` -> `scripts/make_report.py`. Raw API dumps live only under `data/raw/` (git-ignored); `data/dataset_v1.csv` contains engineered features only.

## 0. Run assumptions (read first)

- **Budget**: two passes. Pass 1 (placeholders in the brief) used a self-imposed 40-call ceiling and 12 tokens. Pass 2, after the budget was confirmed as 5M calls/month at 120/min, pulled every token that passes the free filters, paced at <= 100 calls/min. `scripts/tok_pull.py` is idempotent (`--budget`, `--max-tokens`, `--probe-all`, `--include-fully-unlocked`).
- **Plan history window discovered from an API error**: emission data is only served for **2024-09-14 to 2027-06-30** (exactly 2 years back from today). Requests starting earlier are rejected (`Invalid Date Range`). All per-token pulls therefore use `--start 2024-09-14 --end 2027-06-30`.
- **TGE proxy**: the token list has no TGE/launch date field. The 180-day age filter uses the Binance first daily candle (free); `tge_proxy_date` = min(Binance listing, first emission row). For coins older than their Binance listing (LTC, DOGE, ZEC, ATOM ...) `days_since_tge` is a lower bound.
- **Universe filter**: Binance USDT spot pair (exact `SYMBOL+USDT`, status TRADING), Binance listing >= 180 days before today, and Daily Emission non-empty on the spent call. Fully-unlocked tokens (`totalLockedAmount == 0`) were included in pass 2 so the panel also contains no-forward-unlock observations. A free symbol-collision guard (Binance last price vs token-list marketCap/circulatingSupply, factor 3) excludes tokens whose Binance ticker is a different asset.
- **Centrifuge was removed after the alignment audit**: Tokenomist's entry is 'Centrifuge [OLD]' while Binance CFGUSDT is the migrated token, so price and supply described different assets.
- **BTC and ETH were excluded from the target universe** because they are the market-vol controls (`btc_rv_past_14d`, `eth_rv_past_14d`).
- The universe is now *every* eligible token, not a market-cap top-M. It therefore mixes PoW/PoS issuance coins (smooth block/staking emission: SOL, ZEC, DOGE, LTC, ATOM ...) with VC-vesting tokens that have real cliffs. Section 4 separates them; use `has_unlock_events` and the per-token step counts to subset at modelling time.
- Schedules that end before 2027-06-29 are extended with zero-unlock days (`emission_schedule_ended` flag) so `emis_next_*` is 0 rather than NaN once Tokenomist knows of no further scheduled unlocks.

## 1. Universe

- Tokens in Tokenomist registry (token list): **629**
- Selected (all 3 endpoints pulled): **176**. Excluded: **453**. Tokens pulled but contributing 0 panel rows (no overlap between emission dates <= today-30d and Binance price history): **0** (none).

Exclusion reasons (count):

| reason | tokens |
|---|---|
| no_binance_usdt_spot_pair | 412 |
| no_emission_data (Daily Emission empty) | 31 |
| too_young_binance_listing_<date> | 3 |
| used_as_market_control_btc_eth | 2 |
| entity_mismatch (Tokenomist entry is 'Centrifuge [OLD]', schedule ended 2025-07; Binance CFGUSDT listed 2026-03-16 is the migrated token) | 1 |
| binance_symbol_price_mismatch (binance=0.2034 implied=1.9787 ratio=0.10) | 1 |
| binance_symbol_price_mismatch (binance=0.293 implied=1.11942 ratio=0.26) | 1 |
| binance_symbol_price_mismatch (binance=8.336e-05 implied=0.00699594 ratio=0.01) | 1 |
| binance_symbol_price_mismatch (binance=0.0081 implied=0.00154492 ratio=5.24) | 1 |

Notes: `no_emission_data` = Daily Emission returned `[]` after a spent call (31 tokens: binancecoin, cardano, shiba-inu, pepe, algorand, injective-protocol, virtual-protocol, raydium, lido-dao, compound-governance-token, dogwifcoin, chiliz, golem, stp-network, qtum, 0x, orca, rif-token, yearn-finance, superfarm, livepeer, sushi, enjincoin, venus, mask-network, api3, bancor, kyber-network-crystal, aevo-exchange, joe, gitcoin). `binance_symbol_price_mismatch` = the Binance ticker price differs from marketCap/circulatingSupply by more than 3x. For NEIRO and MOVE the Binance symbol is genuinely a different asset; for FTT and CYBER it is more likely a stale Tokenomist market-cap snapshot, so those two could be re-admitted by hand (`--price-band 20`).

| token_id | symbol | reason |
|---|---|---|
| ftx-token | FTT | binance_symbol_price_mismatch (binance=0.2034 implied=1.9787 ratio=0.10) |
| cyberconnect | CYBER | binance_symbol_price_mismatch (binance=0.293 implied=1.11942 ratio=0.26) |
| neiro-on-eth | NEIRO | binance_symbol_price_mismatch (binance=8.336e-05 implied=0.00699594 ratio=0.01) |
| bluemove | MOVE | binance_symbol_price_mismatch (binance=0.0081 implied=0.00154492 ratio=5.24) |


Selected universe (rank = market-cap order among eligible tokens):

| rank | token_id | symbol | marketCap | listedMethod | binance_listing_date | emission_first_date | emission_last_date | emission_rows |
|---|---|---|---|---|---|---|---|---|
| 1 | solana | SOL | 59709513709 | INTERNAL | 2020-08-11 | 2024-09-14 | 2027-06-29 | 1019 |
| 2 | zcash | ZEC | 19277635934 | INTERNAL | 2019-03-21 | 2024-09-14 | 2027-06-29 | 1019 |
| 3 | dogecoin | DOGE | 13168535203 | INTERNAL | 2019-07-05 | 2024-09-14 | 2027-06-29 | 1019 |
| 4 | chainlink | LINK | 8534051434 | INTERNAL | 2019-01-16 | 2024-09-14 | 2024-12-21 | 99 |
| 5 | litecoin | LTC | 4208358966 | INTERNAL | 2017-12-13 | 2024-09-14 | 2027-06-29 | 1019 |
| 6 | uniswap | UNI | 3982737420 | INTERNAL | 2020-09-17 | 2024-09-14 | 2024-09-21 | 8 |
| 7 | avalanche-2 | AVAX | 3290129349 | INTERNAL | 2020-09-22 | 2024-09-14 | 2027-06-29 | 1019 |
| 8 | near | NEAR | 3176117702 | INTERNAL | 2020-10-14 | 2024-09-14 | 2027-06-29 | 1019 |
| 9 | sui | SUI | 2963766065 | INTERNAL | 2023-05-03 | 2024-09-14 | 2027-06-29 | 1019 |
| 10 | bittensor | TAO | 2251690887 | INTERNAL | 2024-04-11 | 2024-09-14 | 2027-06-29 | 1019 |
| 11 | aave | AAVE | 1946909418 | INTERNAL | 2020-10-15 | 2024-09-14 | 2027-06-29 | 1019 |
| 12 | cosmos | ATOM | 1914435977 | INTERNAL | 2019-04-29 | 2024-09-14 | 2027-06-29 | 1019 |
| 13 | aster-2 | ASTER | 1885571538 | INTERNAL | 2025-10-06 | 2025-09-14 | 2027-06-29 | 654 |
| 14 | world-liberty-financial | WLFI | 1842686710 | INTERNAL | 2025-09-01 | 2025-08-31 | 2027-06-29 | 668 |
| 15 | polkadot | DOT | 1733265981 | INTERNAL | 2020-08-18 | 2024-09-14 | 2027-06-29 | 1019 |
| 16 | ondo-finance | ONDO | 1715897894 | INTERNAL | 2025-04-11 | 2024-09-14 | 2027-06-29 | 1019 |
| 17 | pump-fun | PUMP | 1702670973 | INTERNAL | 2025-09-11 | 2025-07-06 | 2027-06-29 | 724 |
| 18 | morpho | MORPHO | 1516700814 | INTERNAL | 2025-10-03 | 2024-11-17 | 2027-06-29 | 955 |
| 19 | ethena | ENA | 1417369720 | INTERNAL | 2024-04-02 | 2024-09-14 | 2027-06-29 | 1019 |
| 20 | worldcoin-wld | WLD | 1389660124 | INTERNAL | 2023-07-24 | 2024-09-14 | 2027-06-29 | 1019 |
| 21 | polygon-ecosystem-token | POL | 1030045392 | INTERNAL | 2024-09-13 | 2024-09-14 | 2027-06-29 | 1019 |
| 22 | arbitrum | ARB | 923039452 | INTERNAL | 2023-03-23 | 2024-09-14 | 2027-04-17 | 946 |
| 23 | filecoin | FIL | 819833106 | INTERNAL | 2020-10-15 | 2024-09-14 | 2027-06-29 | 1019 |
| 24 | jupiter-exchange-solana | JUP | 784397257 | INTERNAL | 2024-01-31 | 2024-09-14 | 2026-02-28 | 533 |
| 25 | render-token | RENDER | 720433321 | INTERNAL | 2024-07-26 | 2024-09-14 | 2027-06-29 | 1019 |
| 26 | ether-fi | ETHFI | 642738601 | INTERNAL | 2024-03-18 | 2024-09-14 | 2027-03-20 | 918 |
| 27 | curve-dao-token | CRV | 564557849 | INTERNAL | 2020-08-15 | 2024-09-14 | 2027-06-29 | 1019 |
| 28 | official-trump | TRUMP | 545014951 | AI | 2025-01-19 | 2025-01-12 | 2027-06-29 | 899 |
| 29 | aptos | APT | 518084562 | INTERNAL | 2022-10-19 | 2024-09-14 | 2027-06-29 | 1019 |
| 30 | pyth-network | PYTH | 455018234 | INTERNAL | 2024-02-02 | 2024-09-14 | 2027-05-22 | 981 |
| 31 | falcon-finance-ff | FF | 447909138 | EXTERNAL | 2025-09-29 | 2025-09-28 | 2027-06-29 | 640 |
| 32 | pudgy-penguins | PENGU | 447737787 | INTERNAL | 2024-12-17 | 2024-12-15 | 2027-06-29 | 927 |
| 33 | fetch-ai | FET | 392017867 | INTERNAL | 2019-02-28 | 2024-09-14 | 2027-06-29 | 1019 |
| 34 | pendle | PENDLE | 385044257 | INTERNAL | 2023-07-03 | 2024-09-14 | 2027-06-29 | 1019 |
| 35 | layerzero | ZRO | 373157174 | INTERNAL | 2024-06-20 | 2024-09-14 | 2027-06-26 | 1016 |
| 36 | celestia | TIA | 348102867 | INTERNAL | 2023-10-31 | 2024-09-14 | 2027-06-29 | 1019 |
| 37 | sei-network | SEI | 301827921 | INTERNAL | 2023-08-15 | 2024-09-14 | 2027-06-29 | 1019 |
| 38 | kite-2 | KITE | 257283634 | INTERNAL | 2025-11-03 | 2025-11-02 | 2027-06-29 | 605 |
| 39 | conflux-token | CFX | 250827207 | INTERNAL | 2021-03-29 | 2024-09-14 | 2024-11-02 | 50 |
| 40 | syrup | SYRUP | 249081182 | INTERNAL | 2025-05-06 | 2024-11-10 | 2026-09-19 | 679 |
| 41 | bonk | BONK | 243497159 | INTERNAL | 2023-12-15 | 2024-09-14 | 2026-01-03 | 477 |
| 42 | ethereum-name-service | ENS | 240911997 | INTERNAL | 2021-11-10 | 2024-09-14 | 2025-11-08 | 421 |
| 43 | jito-governance-token | JTO | 229778954 | INTERNAL | 2023-12-07 | 2024-09-14 | 2026-12-12 | 820 |
| 44 | plasma | XPL | 222216354 | INTERNAL | 2025-09-25 | 2025-09-21 | 2027-06-29 | 647 |
| 45 | optimism | OP | 221701170 | INTERNAL | 2022-06-01 | 2024-09-14 | 2027-06-29 | 1019 |
| 46 | starknet | STRK | 205374340 | INTERNAL | 2024-02-20 | 2024-09-14 | 2027-03-20 | 918 |
| 47 | the-graph | GRT | 205230741 | INTERNAL | 2020-12-17 | 2024-09-14 | 2027-06-29 | 1019 |
| 48 | convex-finance | CVX | 195446656 | AI | 2021-12-23 | 2024-09-14 | 2025-04-26 | 225 |
| 49 | iota | IOTA | 194376549 | INTERNAL | 2018-05-31 | 2024-09-14 | 2027-06-29 | 1019 |
| 50 | kaia | KAIA | 193418468 | INTERNAL | 2024-10-31 | 2024-10-27 | 2027-06-29 | 976 |
| 51 | eigenlayer | EIGEN | 191250936 | INTERNAL | 2024-10-01 | 2024-09-29 | 2027-06-29 | 1004 |
| 52 | axie-infinity | AXS | 165617758 | INTERNAL | 2020-11-04 | 2024-09-14 | 2026-03-14 | 547 |
| 53 | doublezero | 2Z | 165328877 | INTERNAL | 2025-10-02 | 2025-09-28 | 2027-06-29 | 640 |
| 54 | decentraland | MANA | 149034467 | INTERNAL | 2020-08-06 | 2024-09-14 | 2027-06-29 | 1019 |
| 55 | kamino | KMNO | 137477515 | INTERNAL | 2025-05-06 | 2024-09-14 | 2027-05-01 | 960 |
| 56 | apecoin | APE | 134853858 | INTERNAL | 2022-03-17 | 2024-09-14 | 2026-02-21 | 526 |
| 57 | 1inch | 1INCH | 131123223 | INTERNAL | 2020-12-25 | 2024-09-14 | 2025-12-13 | 456 |
| 58 | elrond-erd-2 | EGLD | 129949329 | INTERNAL | 2020-09-03 | 2024-09-14 | 2027-06-29 | 1019 |
| 59 | meteora | MET | 123252096 | EXTERNAL | 2025-11-13 | 2025-10-19 | 2027-06-29 | 619 |
| 60 | zama | ZAMA | 120926256 | INTERNAL | 2026-02-02 | 2026-02-01 | 2027-06-29 | 514 |
| 61 | mina-protocol | MINA | 113522315 | INTERNAL | 2021-08-10 | 2024-09-14 | 2027-06-29 | 1019 |
| 62 | immutable-x | IMX | 109600628 | INTERNAL | 2022-01-10 | 2024-09-14 | 2025-11-01 | 414 |
| 63 | sentient | SENT | 107456356 | INTERNAL | 2026-01-22 | 2026-01-18 | 2027-06-29 | 528 |
| 64 | sonic-3 | S | 105625724 | INTERNAL | 2025-01-16 | 2024-12-15 | 2027-06-29 | 927 |
| 65 | the-sandbox | SAND | 104561306 | INTERNAL | 2020-08-14 | 2024-09-14 | 2025-02-15 | 155 |
| 66 | zksync | ZK | 99369571 | INTERNAL | 2024-06-17 | 2024-09-14 | 2027-06-29 | 1019 |
| 67 | dydx | DYDX | 96296699 | INTERNAL | 2021-09-09 | 2024-09-14 | 2026-08-08 | 694 |
| 68 | plume | PLUME | 83489329 | INTERNAL | 2025-08-18 | 2025-01-19 | 2027-06-29 | 892 |
| 69 | gmx | GMX | 82627222 | INTERNAL | 2022-10-05 | 2024-09-14 | 2027-06-29 | 1019 |
| 70 | cow-protocol | COW | 80075217 | INTERNAL | 2024-11-06 | 2024-09-14 | 2026-01-03 | 477 |
| 71 | kaito | KAITO | 73466919 | INTERNAL | 2025-02-20 | 2025-02-16 | 2027-06-29 | 864 |
| 72 | arkham | ARKM | 72513813 | INTERNAL | 2023-07-18 | 2024-09-14 | 2027-06-29 | 1019 |
| 73 | redstone-oracles | RED | 68805876 | INTERNAL | 2025-02-28 | 2025-03-02 | 2027-06-29 | 850 |
| 74 | wormhole | W | 66141891 | INTERNAL | 2024-04-03 | 2024-09-14 | 2027-06-29 | 1019 |
| 75 | linea | LINEA | 64532391 | INTERNAL | 2025-09-10 | 2025-09-07 | 2027-06-29 | 661 |
| 76 | berachain-bera | BERA | 63424470 | INTERNAL | 2025-02-06 | 2025-02-02 | 2027-06-29 | 878 |
| 77 | spark-2 | SPK | 62706639 | INTERNAL | 2025-06-17 | 2025-06-15 | 2027-06-29 | 745 |
| 78 | goplus-security | GPS | 60380279 | INTERNAL | 2025-03-04 | 2025-01-12 | 2027-06-29 | 899 |
| 79 | nervos-network | CKB | 59177726 | INTERNAL | 2021-01-26 | 2024-09-14 | 2027-06-29 | 1019 |
| 80 | babylon | BABY | 58198576 | INTERNAL | 2025-04-10 | 2025-04-06 | 2027-06-29 | 815 |
| 81 | axelar | AXL | 55622997 | INTERNAL | 2024-03-01 | 2024-09-14 | 2027-01-02 | 841 |
| 82 | oasis-network | ROSE | 55611987 | INTERNAL | 2020-11-19 | 2024-09-14 | 2027-06-29 | 1019 |
| 83 | astar | ASTR | 55246758 | INTERNAL | 2022-02-28 | 2024-09-14 | 2027-01-23 | 862 |
| 84 | bio-protocol | BIO | 54847201 | EXTERNAL | 2025-01-03 | 2024-12-29 | 2027-06-29 | 913 |
| 85 | blur | BLUR | 52833492 | INTERNAL | 2023-11-24 | 2024-09-14 | 2027-02-20 | 890 |
| 86 | io | IO | 51553499 | INTERNAL | 2024-06-11 | 2024-09-14 | 2027-06-29 | 1019 |
| 87 | celo | CELO | 50477452 | INTERNAL | 2021-01-05 | 2024-09-14 | 2027-06-29 | 1019 |
| 88 | space-id | ID | 49392320 | INTERNAL | 2023-03-22 | 2024-09-14 | 2027-06-29 | 1019 |
| 89 | flow | FLOW | 48788529 | INTERNAL | 2021-07-30 | 2024-09-14 | 2027-06-29 | 1019 |
| 90 | altlayer | ALT | 48216532 | INTERNAL | 2024-01-25 | 2024-09-14 | 2027-06-29 | 1019 |
| 91 | lombard-protocol | BARD | 45197377 | AI | 2025-09-18 | 2025-09-14 | 2027-06-29 | 654 |
| 92 | catizen | CATI | 43702005 | AI | 2024-09-20 | 2024-09-15 | 2027-06-29 | 1018 |
| 93 | zero-gravity | 0G | 42196639 | INTERNAL | 2025-09-22 | 2025-09-21 | 2027-06-29 | 647 |
| 94 | edu-coin | EDU | 41309955 | INTERNAL | 2023-04-28 | 2024-09-14 | 2027-06-29 | 1019 |
| 95 | magic-eden | ME | 41264272 | EXTERNAL | 2024-12-10 | 2024-12-08 | 2027-06-29 | 934 |
| 96 | rocket-pool | RPL | 40496463 | INTERNAL | 2023-01-18 | 2024-09-14 | 2027-06-29 | 1019 |
| 97 | huma-finance | HUMA | 40363519 | INTERNAL | 2025-05-26 | 2025-05-25 | 2027-06-29 | 766 |
| 98 | renzo | REZ | 40008461 | INTERNAL | 2024-04-30 | 2024-09-14 | 2027-04-03 | 932 |
| 99 | space-and-time | SXT | 39257842 | INTERNAL | 2025-05-08 | 2025-05-04 | 2027-06-29 | 787 |
| 100 | movement | MOVE | 36607369 | INTERNAL | 2024-12-09 | 2024-12-08 | 2027-06-29 | 934 |
| 101 | succinct | PROVE | 35512128 | INTERNAL | 2025-08-05 | 2025-08-03 | 2027-06-29 | 696 |
| 102 | avantis | AVNT | 35022176 | INTERNAL | 2025-09-15 | 2025-09-07 | 2027-06-29 | 661 |
| 103 | memecoin-2 | MEME | 34880250 | INTERNAL | 2023-11-03 | 2024-09-14 | 2027-06-29 | 1019 |
| 104 | lista | LISTA | 33164252 | INTERNAL | 2024-06-20 | 2024-09-14 | 2027-06-29 | 1019 |
| 105 | terra-luna-2 | LUNA | 32937492 | INTERNAL | 2020-08-21 | 2024-09-14 | 2027-05-29 | 988 |
| 106 | sahara-ai | SAHARA | 32266510 | INTERNAL | 2025-06-26 | 2025-06-22 | 2027-06-29 | 738 |
| 107 | euler | EUL | 31317871 | INTERNAL | 2025-10-13 | 2024-09-14 | 2025-12-20 | 463 |
| 108 | momentum-3 | MMT | 31281079 | AI | 2025-11-04 | 2025-11-02 | 2027-06-29 | 605 |
| 109 | manta-network | MANTA | 29554264 | INTERNAL | 2024-01-18 | 2024-09-14 | 2027-06-29 | 1019 |
| 110 | illuvium | ILV | 29268378 | INTERNAL | 2021-09-22 | 2024-09-14 | 2025-04-05 | 204 |
| 111 | sign-global | SIGN | 29234773 | INTERNAL | 2025-04-28 | 2025-04-27 | 2027-06-29 | 794 |
| 112 | osmosis | OSMO | 26325189 | INTERNAL | 2022-10-28 | 2024-09-14 | 2027-06-29 | 1019 |
| 113 | frax-share | FRAX | 25701908 | INTERNAL | 2026-01-15 | 2024-09-14 | 2027-06-29 | 1019 |
| 114 | tensor | TNSR | 25577481 | INTERNAL | 2024-04-08 | 2024-09-14 | 2027-04-10 | 939 |
| 115 | solv-protocol | SOLV | 25402383 | INTERNAL | 2025-01-17 | 2025-01-12 | 2027-06-29 | 899 |
| 116 | cartesi | CTSI | 24398549 | INTERNAL | 2020-04-23 | 2024-09-14 | 2025-11-29 | 442 |
| 117 | fogo | FOGO | 24310308 | AI | 2026-01-15 | 2026-01-11 | 2027-06-29 | 535 |
| 118 | metis-token | METIS | 24117361 | INTERNAL | 2024-03-11 | 2024-09-14 | 2027-06-29 | 1019 |
| 119 | stepn | GMT | 23978869 | INTERNAL | 2022-03-09 | 2024-09-14 | 2027-06-29 | 1019 |
| 120 | hyperlane | HYPER | 23737141 | INTERNAL | 2025-04-22 | 2025-04-20 | 2027-06-29 | 801 |
| 121 | home | HOME | 23599063 | INTERNAL | 2025-06-12 | 2025-06-08 | 2027-06-29 | 752 |
| 122 | skale | SKL | 23213130 | INTERNAL | 2020-12-01 | 2024-09-14 | 2027-06-29 | 1019 |
| 123 | usual | USUAL | 22825399 | INTERNAL | 2024-11-19 | 2024-11-10 | 2027-06-29 | 962 |
| 124 | yield-guild-games | YGG | 22600767 | INTERNAL | 2021-09-24 | 2024-09-14 | 2027-02-27 | 897 |
| 125 | stargate-finance | STG | 22251443 | INTERNAL | 2022-08-19 | 2024-09-14 | 2025-03-22 | 190 |
| 126 | liquity | LQTY | 21816075 | INTERNAL | 2023-02-28 | 2024-09-14 | 2027-06-29 | 1019 |
| 127 | big-time | BIGTIME | 21453514 | AI | 2025-04-11 | 2024-09-14 | 2027-06-29 | 1019 |
| 128 | woo | WOO | 21357724 | INTERNAL | 2022-02-08 | 2024-09-14 | 2024-12-28 | 106 |
| 129 | nillion | NIL | 21002723 | INTERNAL | 2025-03-24 | 2025-03-23 | 2027-06-29 | 829 |
| 130 | cetus-protocol | CETUS | 20629458 | AI | 2024-11-06 | 2024-09-14 | 2026-04-04 | 568 |
| 131 | chaingpt | CGPT | 20265391 | AI | 2025-01-10 | 2024-09-14 | 2027-06-29 | 1019 |
| 132 | openeden | EDEN | 20250269 | INTERNAL | 2025-09-30 | 2025-09-28 | 2027-06-29 | 640 |
| 133 | yield-basis | YB | 19453753 | INTERNAL | 2025-10-15 | 2025-10-12 | 2027-06-29 | 626 |
| 134 | bonfida | FIDA | 19211333 | AI | 2021-09-30 | 2024-09-14 | 2024-12-28 | 106 |
| 135 | biconomy | BICO | 19152964 | AI | 2021-12-09 | 2024-09-14 | 2025-09-13 | 365 |
| 136 | dodo | DODO | 17856564 | INTERNAL | 2021-02-19 | 2024-09-14 | 2025-07-05 | 295 |
| 137 | sophon | SOPH | 17821983 | INTERNAL | 2025-05-28 | 2025-05-25 | 2027-06-29 | 766 |
| 138 | anime | ANIME | 17614224 | INTERNAL | 2025-01-23 | 2025-01-19 | 2027-06-29 | 892 |
| 139 | connect-token-wct | WCT | 17043191 | INTERNAL | 2025-04-15 | 2025-04-13 | 2027-06-29 | 808 |
| 140 | portal-2 | PORTAL | 16893026 | INTERNAL | 2024-02-29 | 2024-09-14 | 2027-06-29 | 1019 |
| 141 | synfutures | F | 16768784 | AI | 2025-10-25 | 2024-12-01 | 2027-06-29 | 941 |
| 142 | endurance | ACE | 16434700 | AI | 2023-12-18 | 2024-09-14 | 2027-06-29 | 1019 |
| 143 | banana-gun | BANANA | 15832998 | AI | 2024-07-20 | 2024-09-14 | 2027-06-29 | 1019 |
| 144 | mira-3 | MIRA | 15805248 | INTERNAL | 2025-09-26 | 2025-09-21 | 2027-06-29 | 647 |
| 145 | xai-blockchain | XAI | 15315094 | INTERNAL | 2024-01-09 | 2024-09-14 | 2027-06-29 | 1019 |
| 146 | solayer | LAYER | 14702507 | INTERNAL | 2025-02-11 | 2025-02-09 | 2027-06-29 | 871 |
| 147 | coin98 | C98 | 14331755 | INTERNAL | 2021-07-23 | 2024-09-14 | 2025-06-28 | 288 |
| 148 | spell-token | SPELL | 14244726 | AI | 2021-12-24 | 2024-09-14 | 2027-06-29 | 1019 |
| 149 | katana-network-token | KAT | 14154983 | INTERNAL | 2026-03-18 | 2026-03-15 | 2027-06-29 | 472 |
| 150 | radicle | RAD | 13936138 | AI | 2021-10-07 | 2024-09-14 | 2025-02-15 | 155 |
| 151 | initia | INIT | 13460822 | INTERNAL | 2025-04-24 | 2025-04-20 | 2027-06-29 | 801 |
| 152 | bubblemaps | BMT | 13182310 | INTERNAL | 2025-03-18 | 2025-03-16 | 2027-06-29 | 836 |
| 153 | my-neighbor-alice | ALICE | 13147032 | INTERNAL | 2021-03-15 | 2024-09-14 | 2025-02-15 | 155 |
| 154 | lagrange | LA | 12939771 | INTERNAL | 2025-07-09 | 2025-06-01 | 2027-06-29 | 759 |
| 155 | dolomite | DOLO | 12571058 | AI | 2025-08-27 | 2025-04-20 | 2027-06-29 | 801 |
| 156 | maverick-protocol | MAV | 12511235 | INTERNAL | 2023-06-28 | 2024-09-14 | 2027-06-29 | 1019 |
| 157 | kernel-2 | KERNEL | 11709602 | AI | 2025-04-14 | 2025-04-13 | 2027-06-29 | 808 |
| 158 | superrare | RARE | 9848493 | AI | 2021-10-11 | 2024-09-14 | 2025-06-28 | 288 |
| 159 | newton-protocol | NEWT | 9583796 | AI | 2025-06-24 | 2025-06-22 | 2027-06-29 | 738 |
| 160 | dymension | DYM | 9551135 | INTERNAL | 2024-02-06 | 2024-09-14 | 2027-02-06 | 876 |
| 161 | benqi | QI | 9460300 | AI | 2021-11-15 | 2024-09-14 | 2025-05-10 | 239 |
| 162 | gunz | GUN | 9282872 | INTERNAL | 2025-03-31 | 2025-03-30 | 2027-06-29 | 822 |
| 163 | opinion | OPN | 8679284 | INTERNAL | 2026-03-05 | 2026-03-01 | 2027-06-29 | 486 |
| 164 | cookie | COOKIE | 8480373 | INTERNAL | 2025-01-10 | 2024-09-14 | 2027-06-29 | 1019 |
| 165 | resolv | RESOLV | 8092205 | INTERNAL | 2025-06-11 | 2025-06-08 | 2027-06-29 | 752 |
| 166 | saga-2 | SAGA | 7537343 | INTERNAL | 2024-04-09 | 2024-09-14 | 2027-04-10 | 939 |
| 167 | moonbeam | GLMR | 6972989 | INTERNAL | 2022-01-11 | 2024-09-14 | 2027-06-29 | 1019 |
| 168 | treehouse | TREE | 6654550 | INTERNAL | 2025-07-29 | 2025-07-27 | 2027-06-29 | 703 |
| 169 | quickswap | QUICK | 6169893 | INTERNAL | 2021-08-13 | 2024-09-14 | 2024-10-12 | 29 |
| 170 | myshell | SHELL | 5648616 | INTERNAL | 2025-02-27 | 2025-02-09 | 2027-06-29 | 871 |
| 171 | particle-network | PARTI | 5366043 | INTERNAL | 2025-03-25 | 2025-03-23 | 2027-06-29 | 829 |
| 172 | scroll | SCR | 4175754 | INTERNAL | 2024-10-11 | 2024-10-20 | 2027-06-29 | 983 |
| 173 | haedal | HAEDAL | 3848975 | INTERNAL | 2025-05-21 | 2025-04-27 | 2027-06-29 | 794 |
| 174 | pixels | PIXEL | 3801575 | INTERNAL | 2024-02-19 | 2024-09-14 | 2027-06-29 | 1019 |
| 175 | bouncebit | BB | 3783994 | AI | 2024-05-13 | 2024-09-14 | 2027-06-29 | 1019 |
| 176 | sleepless-ai | AI | 2293781 | INTERNAL | 2024-01-04 | 2024-09-14 | 2027-06-29 | 1019 |

## 2. Dataset shape

- Rows: **103685**; tokens: **176**; columns: **47** (44 non-key columns, of which 5 are targets).
- Rows per token: min **151**, median **701**, max **701**; 3 tokens have fewer than 200 rows (Binance listing or TGE inside the window).
- Date coverage overall: **2024-09-14 to 2026-08-15** (emission history starts 2024-09-14 by plan limit; last 30 days dropped because `rv_fwd_30d` is not computable).
- Rows dropped: 5280 for the forward-target rule (30 per token), 6 for `float_pit == 0` or null (2 tokens affected). Emission series had 0 missing calendar days in total.

| token_id | rows | first_date | last_date | has_unlock_events |
|---|---|---|---|---|
| 1inch | 701 | 2024-09-14 | 2026-08-15 | True |
| aave | 701 | 2024-09-14 | 2026-08-15 | False |
| altlayer | 701 | 2024-09-14 | 2026-08-15 | True |
| anime | 570 | 2025-01-23 | 2026-08-15 | True |
| apecoin | 701 | 2024-09-14 | 2026-08-15 | True |
| aptos | 701 | 2024-09-14 | 2026-08-15 | True |
| arbitrum | 701 | 2024-09-14 | 2026-08-15 | True |
| arkham | 701 | 2024-09-14 | 2026-08-15 | False |
| astar | 701 | 2024-09-14 | 2026-08-15 | True |
| aster-2 | 314 | 2025-10-06 | 2026-08-15 | True |
| avalanche-2 | 701 | 2024-09-14 | 2026-08-15 | True |
| avantis | 335 | 2025-09-15 | 2026-08-15 | True |
| axelar | 701 | 2024-09-14 | 2026-08-15 | False |
| axie-infinity | 701 | 2024-09-14 | 2026-08-15 | True |
| babylon | 493 | 2025-04-10 | 2026-08-15 | True |
| banana-gun | 701 | 2024-09-14 | 2026-08-15 | True |
| benqi | 701 | 2024-09-14 | 2026-08-15 | True |
| berachain-bera | 556 | 2025-02-06 | 2026-08-15 | True |
| biconomy | 701 | 2024-09-14 | 2026-08-15 | True |
| big-time | 492 | 2025-04-11 | 2026-08-15 | True |
| bio-protocol | 590 | 2025-01-03 | 2026-08-15 | True |
| bittensor | 701 | 2024-09-14 | 2026-08-15 | False |
| blur | 701 | 2024-09-14 | 2026-08-15 | False |
| bonfida | 701 | 2024-09-14 | 2026-08-15 | False |
| bonk | 701 | 2024-09-14 | 2026-08-15 | False |
| bouncebit | 701 | 2024-09-14 | 2026-08-15 | True |
| bubblemaps | 516 | 2025-03-18 | 2026-08-15 | True |
| cartesi | 701 | 2024-09-14 | 2026-08-15 | False |
| catizen | 695 | 2024-09-20 | 2026-08-15 | True |
| celestia | 701 | 2024-09-14 | 2026-08-15 | True |
| celo | 701 | 2024-09-14 | 2026-08-15 | True |
| cetus-protocol | 648 | 2024-11-06 | 2026-08-15 | True |
| chaingpt | 583 | 2025-01-10 | 2026-08-15 | False |
| chainlink | 701 | 2024-09-14 | 2026-08-15 | True |
| coin98 | 701 | 2024-09-14 | 2026-08-15 | True |
| conflux-token | 701 | 2024-09-14 | 2026-08-15 | False |
| connect-token-wct | 488 | 2025-04-15 | 2026-08-15 | True |
| convex-finance | 701 | 2024-09-14 | 2026-08-15 | False |
| cookie | 583 | 2025-01-10 | 2026-08-15 | True |
| cosmos | 701 | 2024-09-14 | 2026-08-15 | False |
| cow-protocol | 648 | 2024-11-06 | 2026-08-15 | False |
| curve-dao-token | 701 | 2024-09-14 | 2026-08-15 | False |
| decentraland | 701 | 2024-09-14 | 2026-08-15 | False |
| dodo | 701 | 2024-09-14 | 2026-08-15 | True |
| dogecoin | 701 | 2024-09-14 | 2026-08-15 | False |
| dolomite | 354 | 2025-08-27 | 2026-08-15 | True |
| doublezero | 318 | 2025-10-02 | 2026-08-15 | True |
| dydx | 701 | 2024-09-14 | 2026-08-15 | True |
| dymension | 701 | 2024-09-14 | 2026-08-15 | False |
| edu-coin | 701 | 2024-09-14 | 2026-08-15 | False |
| eigenlayer | 684 | 2024-10-01 | 2026-08-15 | True |
| elrond-erd-2 | 701 | 2024-09-14 | 2026-08-15 | False |
| endurance | 701 | 2024-09-14 | 2026-08-15 | True |
| ethena | 701 | 2024-09-14 | 2026-08-15 | True |
| ether-fi | 701 | 2024-09-14 | 2026-08-15 | True |
| ethereum-name-service | 701 | 2024-09-14 | 2026-08-15 | False |
| euler | 307 | 2025-10-13 | 2026-08-15 | True |
| falcon-finance-ff | 321 | 2025-09-29 | 2026-08-15 | True |
| fetch-ai | 701 | 2024-09-14 | 2026-08-15 | False |
| filecoin | 701 | 2024-09-14 | 2026-08-15 | False |
| flow | 701 | 2024-09-14 | 2026-08-15 | False |
| fogo | 213 | 2026-01-15 | 2026-08-15 | True |
| frax-share | 213 | 2026-01-15 | 2026-08-15 | False |
| gmx | 701 | 2024-09-14 | 2026-08-15 | False |
| goplus-security | 530 | 2025-03-04 | 2026-08-15 | True |
| gunz | 503 | 2025-03-31 | 2026-08-15 | True |
| haedal | 452 | 2025-05-21 | 2026-08-15 | True |
| home | 430 | 2025-06-12 | 2026-08-15 | True |
| huma-finance | 447 | 2025-05-26 | 2026-08-15 | True |
| hyperlane | 481 | 2025-04-22 | 2026-08-15 | True |
| illuvium | 701 | 2024-09-14 | 2026-08-15 | False |
| immutable-x | 701 | 2024-09-14 | 2026-08-15 | True |
| initia | 479 | 2025-04-24 | 2026-08-15 | True |
| io | 701 | 2024-09-14 | 2026-08-15 | True |
| iota | 701 | 2024-09-14 | 2026-08-15 | True |
| jito-governance-token | 701 | 2024-09-14 | 2026-08-15 | True |
| jupiter-exchange-solana | 701 | 2024-09-14 | 2026-08-15 | True |
| kaia | 654 | 2024-10-31 | 2026-08-15 | True |
| kaito | 542 | 2025-02-20 | 2026-08-15 | True |
| kamino | 467 | 2025-05-06 | 2026-08-15 | True |
| katana-network-token | 151 | 2026-03-18 | 2026-08-15 | True |
| kernel-2 | 489 | 2025-04-14 | 2026-08-15 | True |
| kite-2 | 286 | 2025-11-03 | 2026-08-15 | True |
| lagrange | 403 | 2025-07-09 | 2026-08-15 | True |
| layerzero | 701 | 2024-09-14 | 2026-08-15 | True |
| linea | 340 | 2025-09-10 | 2026-08-15 | True |
| liquity | 701 | 2024-09-14 | 2026-08-15 | True |
| lista | 701 | 2024-09-14 | 2026-08-15 | True |
| litecoin | 701 | 2024-09-14 | 2026-08-15 | False |
| lombard-protocol | 332 | 2025-09-18 | 2026-08-15 | True |
| magic-eden | 614 | 2024-12-10 | 2026-08-15 | True |
| manta-network | 701 | 2024-09-14 | 2026-08-15 | True |
| maverick-protocol | 701 | 2024-09-14 | 2026-08-15 | True |
| memecoin-2 | 701 | 2024-09-14 | 2026-08-15 | True |
| meteora | 276 | 2025-11-13 | 2026-08-15 | True |
| metis-token | 701 | 2024-09-14 | 2026-08-15 | False |
| mina-protocol | 701 | 2024-09-14 | 2026-08-15 | False |
| mira-3 | 324 | 2025-09-26 | 2026-08-15 | True |
| momentum-3 | 285 | 2025-11-04 | 2026-08-15 | True |
| moonbeam | 701 | 2024-09-14 | 2026-08-15 | True |
| morpho | 317 | 2025-10-03 | 2026-08-15 | True |
| movement | 615 | 2024-12-09 | 2026-08-15 | True |
| my-neighbor-alice | 701 | 2024-09-14 | 2026-08-15 | True |
| myshell | 535 | 2025-02-27 | 2026-08-15 | True |
| near | 701 | 2024-09-14 | 2026-08-15 | False |
| nervos-network | 701 | 2024-09-14 | 2026-08-15 | False |
| newton-protocol | 418 | 2025-06-24 | 2026-08-15 | True |
| nillion | 510 | 2025-03-24 | 2026-08-15 | True |
| oasis-network | 701 | 2024-09-14 | 2026-08-15 | True |
| official-trump | 574 | 2025-01-19 | 2026-08-15 | True |
| ondo-finance | 492 | 2025-04-11 | 2026-08-15 | True |
| openeden | 320 | 2025-09-30 | 2026-08-15 | True |
| opinion | 164 | 2026-03-05 | 2026-08-15 | True |
| optimism | 701 | 2024-09-14 | 2026-08-15 | True |
| osmosis | 701 | 2024-09-14 | 2026-08-15 | False |
| particle-network | 509 | 2025-03-25 | 2026-08-15 | True |
| pendle | 701 | 2024-09-14 | 2026-08-15 | False |
| pixels | 701 | 2024-09-14 | 2026-08-15 | True |
| plasma | 325 | 2025-09-25 | 2026-08-15 | True |
| plume | 363 | 2025-08-18 | 2026-08-15 | True |
| polkadot | 701 | 2024-09-14 | 2026-08-15 | False |
| polygon-ecosystem-token | 701 | 2024-09-14 | 2026-08-15 | False |
| portal-2 | 701 | 2024-09-14 | 2026-08-15 | False |
| pudgy-penguins | 607 | 2024-12-17 | 2026-08-15 | True |
| pump-fun | 339 | 2025-09-11 | 2026-08-15 | True |
| pyth-network | 701 | 2024-09-14 | 2026-08-15 | True |
| quickswap | 701 | 2024-09-14 | 2026-08-15 | False |
| radicle | 701 | 2024-09-14 | 2026-08-15 | False |
| redstone-oracles | 528 | 2025-03-06 | 2026-08-15 | True |
| render-token | 701 | 2024-09-14 | 2026-08-15 | False |
| renzo | 701 | 2024-09-14 | 2026-08-15 | True |
| resolv | 431 | 2025-06-11 | 2026-08-15 | True |
| rocket-pool | 701 | 2024-09-14 | 2026-08-15 | False |
| saga-2 | 701 | 2024-09-14 | 2026-08-15 | True |
| sahara-ai | 416 | 2025-06-26 | 2026-08-15 | True |
| scroll | 663 | 2024-10-22 | 2026-08-15 | True |
| sei-network | 701 | 2024-09-14 | 2026-08-15 | True |
| sentient | 206 | 2026-01-22 | 2026-08-15 | True |
| sign-global | 475 | 2025-04-28 | 2026-08-15 | True |
| skale | 701 | 2024-09-14 | 2026-08-15 | True |
| sleepless-ai | 701 | 2024-09-14 | 2026-08-15 | True |
| solana | 701 | 2024-09-14 | 2026-08-15 | False |
| solayer | 551 | 2025-02-11 | 2026-08-15 | True |
| solv-protocol | 576 | 2025-01-17 | 2026-08-15 | True |
| sonic-3 | 577 | 2025-01-16 | 2026-08-15 | True |
| sophon | 445 | 2025-05-28 | 2026-08-15 | True |
| space-and-time | 465 | 2025-05-08 | 2026-08-15 | True |
| space-id | 701 | 2024-09-14 | 2026-08-15 | True |
| spark-2 | 425 | 2025-06-17 | 2026-08-15 | True |
| spell-token | 701 | 2024-09-14 | 2026-08-15 | True |
| stargate-finance | 701 | 2024-09-14 | 2026-08-15 | False |
| starknet | 701 | 2024-09-14 | 2026-08-15 | True |
| stepn | 701 | 2024-09-14 | 2026-08-15 | False |
| succinct | 376 | 2025-08-05 | 2026-08-15 | True |
| sui | 701 | 2024-09-14 | 2026-08-15 | True |
| superrare | 701 | 2024-09-14 | 2026-08-15 | True |
| synfutures | 295 | 2025-10-25 | 2026-08-15 | True |
| syrup | 467 | 2025-05-06 | 2026-08-15 | True |
| tensor | 701 | 2024-09-14 | 2026-08-15 | True |
| terra-luna-2 | 701 | 2024-09-14 | 2026-08-15 | False |
| the-graph | 701 | 2024-09-14 | 2026-08-15 | False |
| the-sandbox | 701 | 2024-09-14 | 2026-08-15 | True |
| treehouse | 383 | 2025-07-29 | 2026-08-15 | True |
| uniswap | 701 | 2024-09-14 | 2026-08-15 | False |
| usual | 635 | 2024-11-19 | 2026-08-15 | True |
| woo | 701 | 2024-09-14 | 2026-08-15 | False |
| world-liberty-financial | 349 | 2025-09-01 | 2026-08-15 | True |
| worldcoin-wld | 701 | 2024-09-14 | 2026-08-15 | False |
| wormhole | 701 | 2024-09-14 | 2026-08-15 | True |
| xai-blockchain | 701 | 2024-09-14 | 2026-08-15 | False |
| yield-basis | 305 | 2025-10-15 | 2026-08-15 | True |
| yield-guild-games | 701 | 2024-09-14 | 2026-08-15 | True |
| zama | 195 | 2026-02-02 | 2026-08-15 | True |
| zcash | 701 | 2024-09-14 | 2026-08-15 | False |
| zero-gravity | 328 | 2025-09-22 | 2026-08-15 | True |
| zksync | 701 | 2024-09-14 | 2026-08-15 | True |

## 3. Null rate per column (descending)

| column | null_rate | flag |
|---|---|---|
| days_to_next_cliff | 0.511 | **>30% NULL** |
| next_cliff_pct_float | 0.511 | **>30% NULL** |
| unlockPrecision | 0.332 | **>30% NULL** |
| rv_past_30d | 0.022 |  |
| ret_past_30d | 0.022 |  |
| rv_past_14d | 0.010 |  |
| rv_past_7d | 0.005 |  |
| ret_past_7d | 0.005 |  |

- 39 columns have zero nulls and are omitted from the table.
- `days_to_next_cliff`, `next_cliff_pct_float` and `unlockPrecision` are null where `has_unlock_events` is false (50 of 176 tokens) or no future event exists in the pulled window; this is structural, not missing-at-random. `rv_past_*`/`ret_past_*` nulls are the first days after a token's Binance listing. No imputation was done.

## 4. Descriptive statistics of the key feature and target

| column | mean | median | p5 | p95 | min | max | std | n |
|---|---|---|---|---|---|---|---|---|
| emis_next_30d_pct_float | 0.02775 | 0.01124 | 0 | 0.08536 | 0 | 2.403 | 0.07095 | 1.037e+05 |
| rv_fwd_14d | 1.01 | 0.9018 | 0.452 | 1.94 | 0.1263 | 8.78 | 0.514 | 1.037e+05 |

- Rows with `emis_next_30d_pct_float == 0`: **19962** of 103685 (19.3%), spread over 93 tokens: dates where the next 30 days carry no scheduled unlock (lumpy schedules, or the schedule has ended: 11354 rows flagged `emission_schedule_ended`).
- Rows with `emis_next_30d_pct_float > 1` (next-30-day unlock larger than the whole current float): **90**, all in the first weeks after TGE of hyperlane, saga-2, succinct. Genuine, not an error; a log or rank transform is advisable.

Within-token variation of the feature (this is what matters for a panel model; pooled variation is mostly cross-sectional):

| token_id | mean | std | min | max | n_distinct | share_zero | cv_within | day_jumps_gt10pct | spearman_vs_time |
|---|---|---|---|---|---|---|---|---|---|
| 1inch | 0.003379 | 0.01553 | 0 | 0.07682 | 80 | 0.3823 | 4.597 | 53 | -0.8785 |
| aave | 0.002434 | 3.998e-05 | 0.002366 | 0.002504 | 701 | 0 | 0.01643 | 0 | -1 |
| altlayer | 0.04923 | 0.02906 | 0 | 0.1882 | 23 | 0.1626 | 0.5903 | 27 | -0.2244 |
| anime | 0.01823 | 0.02894 | 0 | 0.1384 | 22 | 0.0193 | 1.588 | 25 | 0.7331 |
| apecoin | 0.01327 | 0.008324 | 0 | 0.03903 | 20 | 0.271 | 0.6273 | 23 | -0.9656 |
| aptos | 0.02699 | 0.02665 | 0 | 0.09323 | 279 | 0.008559 | 0.9874 | 21 | -0.9367 |
| arbitrum | 0.02387 | 0.005091 | 0.00251 | 0.05243 | 701 | 0 | 0.2133 | 30 | -0.9534 |
| arkham | 0.03842 | 0.0101 | 0.02537 | 0.06217 | 701 | 0 | 0.2629 | 0 | -1 |
| astar | 0.00219 | 0.0003464 | 0 | 0.004505 | 27 | 0.01854 | 0.1582 | 30 | -0.9523 |
| aster-2 | 0.01185 | 0.0004253 | 0.01115 | 0.01262 | 314 | 0 | 0.03588 | 0 | -1 |
| avalanche-2 | 0.007046 | 0.001587 | 0.005455 | 0.009927 | 701 | 0 | 0.2252 | 16 | -0.5033 |
| avantis | 0.04857 | 0.007554 | 0.03776 | 0.0643 | 335 | 0 | 0.1555 | 0 | -0.9931 |
| axelar | 0.01921 | 0.007626 | 0.01114 | 0.04155 | 701 | 0 | 0.397 | 0 | -1 |
| axie-infinity | 0.005029 | 0.009913 | 0 | 0.03849 | 19 | 0.2297 | 1.971 | 4 | -0.979 |
| babylon | 0.04826 | 0.07308 | 0 | 0.2474 | 160 | 0.6187 | 1.514 | 20 | 0.6125 |
| banana-gun | 0.009941 | 0.01807 | 0 | 0.06329 | 7 | 0.7504 | 1.818 | 3 | -0.6311 |
| benqi | 0.005546 | 0.01421 | 0 | 0.04512 | 10 | 0.8631 | 2.561 | 12 | -0.4468 |
| berachain-bera | 0.06643 | 0.1032 | 0.02233 | 0.5272 | 556 | 0 | 1.553 | 3 | 0.4128 |
| biconomy | 0.005335 | 0.00664 | 0 | 0.02605 | 77 | 0.4836 | 1.245 | 1 | -0.9414 |
| big-time | 0.02912 | 0.05981 | 0.005597 | 0.21 | 492 | 0 | 2.054 | 4 | -0.8081 |
| bio-protocol | 0.02432 | 0.02731 | 0.008979 | 0.145 | 590 | 0 | 1.123 | 2 | -0.5318 |
| bittensor | 0.01649 | 0.007039 | 0.009193 | 0.02715 | 701 | 0 | 0.4269 | 0 | -1 |
| blur | 0.01778 | 0.008287 | 0.007566 | 0.03458 | 701 | 0 | 0.4662 | 0 | -1 |
| bonfida | 0.003272 | 0.008623 | 0 | 0.02855 | 99 | 0.8602 | 2.635 | 10 | -0.6029 |
| bonk | 0.003957 | 0.002841 | 0 | 0.006338 | 474 | 0.3252 | 0.718 | 10 | -0.9826 |
| bouncebit | 0.04716 | 0.03474 | 0.01282 | 0.1253 | 701 | 0 | 0.7367 | 4 | 0.3093 |
| bubblemaps | 0.06177 | 0.02646 | 0 | 0.1154 | 19 | 0.01938 | 0.4284 | 22 | -0.9416 |
| cartesi | 0.002617 | 0.002081 | 0 | 0.004436 | 441 | 0.3723 | 0.7954 | 10 | -0.9735 |
| catizen | 0.02493 | 0.02214 | 0 | 0.07223 | 366 | 0.3496 | 0.8881 | 14 | 0.501 |
| celestia | 0.05633 | 0.1111 | 0.01349 | 0.6086 | 701 | 0 | 1.973 | 2 | -0.9563 |
| celo | 0.004318 | 0.001106 | 0.000345 | 0.01027 | 68 | 0 | 0.2562 | 61 | -0.9086 |
| cetus-protocol | 0.0244 | 0.01338 | 0 | 0.04 | 18 | 0.213 | 0.5483 | 1 | -0.9943 |
| chaingpt | 0.01069 | 0.003511 | 0.008049 | 0.01864 | 583 | 0 | 0.3283 | 0 | -1 |
| chainlink | 0.001122 | 0.004971 | 0 | 0.0336 | 3 | 0.9486 | 4.43 | 3 | -0.3244 |
| coin98 | 0.00721 | 0.008994 | 0 | 0.03603 | 12 | 0.6049 | 1.248 | 13 | -0.873 |
| conflux-token | 0.0007256 | 0.00317 | 0 | 0.01769 | 45 | 0.9372 | 4.369 | 10 | -0.4204 |
| connect-token-wct | 0.06375 | 0.1534 | 0.002695 | 0.6596 | 488 | 0 | 2.406 | 15 | 0.5248 |
| convex-finance | 0.001582 | 0.002393 | 0 | 0.005418 | 224 | 0.6819 | 1.513 | 10 | -0.8264 |
| cookie | 0.05245 | 0.04456 | 0.01656 | 0.1777 | 583 | 0 | 0.8496 | 9 | -0.9983 |
| cosmos | 0.006852 | 0.001418 | 0.004834 | 0.008217 | 701 | 0 | 0.207 | 0 | 0.6183 |
| cow-protocol | 0.01247 | 0.00961 | 0 | 0.02287 | 421 | 0.3519 | 0.7704 | 10 | -0.978 |
| curve-dao-token | 0.004468 | 0.0005347 | 0.003299 | 0.005182 | 701 | 0 | 0.1197 | 0 | -1 |
| decentraland | 0.002129 | 0.0001171 | 0.002043 | 0.002463 | 701 | 0 | 0.05499 | 0 | -1 |
| dodo | 0.005299 | 0.006903 | 0 | 0.02174 | 12 | 0.5934 | 1.303 | 13 | -0.802 |
| dogecoin | 0.002717 | 4.984e-05 | 0.002633 | 0.002805 | 701 | 0 | 0.01834 | 0 | -1 |
| dolomite | 0.02502 | 0.02468 | 0 | 0.06092 | 14 | 0.01695 | 0.9866 | 14 | 0.4481 |
| doublezero | 0 | 0 | 0 | 0 | 1 | 1 | NaN | 0 | NaN |
| dydx | 0.009896 | 0.004774 | 0 | 0.02818 | 689 | 0.01854 | 0.4825 | 40 | -0.9695 |
| dymension | 0.04848 | 0.0193 | 0.01961 | 0.09234 | 701 | 0 | 0.398 | 2 | -0.1156 |
| edu-coin | 0.03458 | 0.007736 | 0.02124 | 0.04849 | 701 | 0 | 0.2237 | 0 | -0.8503 |
| eigenlayer | 0.05509 | 0.03784 | 0 | 0.1776 | 101 | 0.02924 | 0.687 | 103 | 0.4585 |
| elrond-erd-2 | 0.002243 | 0.0004592 | 0.001533 | 0.00291 | 701 | 0 | 0.2047 | 0 | -1 |
| endurance | 0.04452 | 0.01435 | 0.02746 | 0.07968 | 69 | 0 | 0.3223 | 1 | -0.841 |
| ethena | 0.06804 | 0.1453 | 0.004565 | 0.6869 | 119 | 0 | 2.135 | 88 | -0.3254 |
| ether-fi | 0.06188 | 0.0484 | 0 | 0.1963 | 552 | 0.07418 | 0.7822 | 10 | -0.2763 |
| ethereum-name-service | 0.008348 | 0.007176 | 0 | 0.01613 | 416 | 0.408 | 0.8596 | 10 | -0.9654 |
| euler | 0.001054 | 0.002286 | 0 | 0.007888 | 60 | 0.7785 | 2.17 | 11 | -0.7263 |
| falcon-finance-ff | 0.02489 | 0.01178 | 0 | 0.04016 | 12 | 0.1121 | 0.4731 | 11 | 0.6129 |
| fetch-ai | 0.002536 | 0.0005929 | 0.0006835 | 0.003957 | 701 | 0 | 0.2337 | 30 | -0.8705 |
| filecoin | 0.01299 | 0.001141 | 0.0112 | 0.01517 | 701 | 0 | 0.08781 | 0 | -1 |
| flow | 0.003743 | 0.0003817 | 0.003526 | 0.006563 | 701 | 0 | 0.102 | 0 | -1 |
| fogo | 0 | 0 | 0 | 0 | 1 | 1 | NaN | 0 | NaN |
| frax-share | 0.000588 | 7.103e-07 | 0.0005868 | 0.0005892 | 213 | 0 | 0.001208 | 0 | -1 |
| gmx | 0.0009634 | 2.154e-05 | 0.000935 | 0.001047 | 698 | 0 | 0.02236 | 0 | -0.4571 |
| goplus-security | 0.07049 | 0.08458 | 0 | 0.3175 | 16 | 0.2415 | 1.2 | 20 | 0.2034 |
| gunz | 0.1051 | 0.05271 | 0 | 0.3033 | 22 | 0.0159 | 0.5017 | 24 | 0.2417 |
| haedal | 0.04096 | 0.02821 | 0 | 0.07613 | 322 | 0.2898 | 0.6888 | 11 | 0.8301 |
| home | 0.05224 | 0.06037 | 0 | 0.2494 | 341 | 0.2093 | 1.156 | 4 | 0.3708 |
| huma-finance | 0.04618 | 0.07872 | 0 | 0.2338 | 6 | 0.6868 | 1.705 | 9 | 0.08807 |
| hyperlane | 0.09555 | 0.2474 | 0 | 1.089 | 421 | 0.1268 | 2.589 | 15 | 0.8704 |
| illuvium | 0.001085 | 0.001796 | 0 | 0.00422 | 198 | 0.719 | 1.656 | 10 | -0.7927 |
| immutable-x | 0.008903 | 0.008156 | 0 | 0.04018 | 30 | 0.4123 | 0.916 | 29 | -0.9389 |
| initia | 0.04959 | 0.1088 | 0.008338 | 0.4713 | 479 | 0 | 2.194 | 9 | 0.2046 |
| io | 0.05379 | 0.01634 | 0.006201 | 0.1023 | 701 | 0 | 0.3038 | 33 | 0.1389 |
| iota | 0.009653 | 0.002915 | 0.006217 | 0.01869 | 120 | 0 | 0.302 | 115 | -0.9281 |
| jito-governance-token | 0.07182 | 0.1597 | 0.02614 | 0.8364 | 701 | 0 | 2.224 | 2 | -0.968 |
| jupiter-exchange-solana | 0.04648 | 0.1494 | 0 | 0.8232 | 24 | 0.3923 | 3.215 | 26 | -0.3567 |
| kaia | 0.004083 | 0.000105 | 0.003907 | 0.00427 | 654 | 0 | 0.02572 | 0 | -1 |
| kaito | 0.03622 | 0.03203 | 0 | 0.1638 | 15 | 0.2915 | 0.8844 | 17 | 0.6958 |
| kamino | 0.04514 | 0.02533 | 0 | 0.1466 | 24 | 0.01499 | 0.5613 | 23 | -0.8335 |
| katana-network-token | 0.06208 | 0.0293 | 0 | 0.1022 | 6 | 0.01987 | 0.4719 | 7 | -0.6313 |
| kernel-2 | 0.06609 | 0.1162 | 0.001163 | 0.4543 | 489 | 0 | 1.759 | 20 | 0.02509 |
| kite-2 | 0.02822 | 0.002198 | 0.02475 | 0.03236 | 286 | 0 | 0.07789 | 0 | -1 |
| lagrange | 0.05394 | 0.01237 | 0.03781 | 0.08104 | 403 | 0 | 0.2292 | 0 | 0.7691 |
| layerzero | 0.03926 | 0.03555 | 0 | 0.1196 | 16 | 0.4094 | 0.9055 | 19 | 0.5175 |
| linea | 0.06131 | 0.03524 | 0 | 0.1644 | 14 | 0.02059 | 0.5748 | 17 | -0.9295 |
| liquity | 0.002739 | 0.002908 | 0.0004145 | 0.01204 | 701 | 0 | 1.062 | 11 | -0.9978 |
| lista | 0.03814 | 0.03111 | 0.007517 | 0.132 | 701 | 0 | 0.8156 | 15 | -0.4928 |
| litecoin | 0.001423 | 2.727e-05 | 0.001367 | 0.001504 | 701 | 0 | 0.01917 | 0 | -0.7657 |
| lombard-protocol | 0.04814 | 0.03332 | 0.02923 | 0.1547 | 332 | 0 | 0.6922 | 2 | -0.8656 |
| magic-eden | 0.08086 | 0.1764 | 0 | 0.7988 | 24 | 0.02117 | 2.181 | 31 | -0.6452 |
| manta-network | 0.02743 | 0.004814 | 0.01363 | 0.03935 | 701 | 0 | 0.1755 | 31 | -0.1611 |
| maverick-protocol | 0.03863 | 0.0298 | 0.01287 | 0.1277 | 701 | 0 | 0.7714 | 15 | -0.5916 |
| memecoin-2 | 0.03536 | 0.03927 | 0.005003 | 0.1707 | 701 | 0 | 1.111 | 6 | -0.914 |
| meteora | 0.0141 | 0.002359 | 0 | 0.02919 | 12 | 0.01812 | 0.1673 | 12 | -0.9532 |
| metis-token | 0.003846 | 9.984e-05 | 0.003678 | 0.004023 | 701 | 0 | 0.02596 | 0 | -1 |
| mina-protocol | 0.004441 | 0.002965 | 0.002642 | 0.009954 | 701 | 0 | 0.6677 | 0 | -1 |
| mira-3 | 0.03641 | 0.008477 | 0 | 0.07693 | 13 | 0.01852 | 0.2328 | 14 | 0.4845 |
| momentum-3 | 0.09982 | 0.03338 | 0 | 0.2376 | 12 | 0.02105 | 0.3344 | 14 | -0.951 |
| moonbeam | 0.007847 | 0.001778 | 0.005197 | 0.01301 | 701 | 0 | 0.2266 | 21 | -0.973 |
| morpho | 0.03679 | 0.009012 | 0.009655 | 0.04748 | 317 | 0 | 0.245 | 3 | -0.3295 |
| movement | 0.03102 | 0.01562 | 0 | 0.1092 | 24 | 0.02114 | 0.5037 | 29 | 0.4272 |
| my-neighbor-alice | 0.002412 | 0.005223 | 0 | 0.02183 | 7 | 0.7846 | 2.165 | 8 | -0.7141 |
| myshell | 0.03247 | 0.02285 | 0.01475 | 0.1097 | 535 | 0 | 0.7037 | 2 | 0.3673 |
| near | 0.008222 | 0.003496 | 0.004311 | 0.0122 | 701 | 0 | 0.4252 | 0 | -0.9996 |
| nervos-network | 0.003774 | 9.614e-05 | 0.003612 | 0.003945 | 701 | 0 | 0.02548 | 0 | -1 |
| newton-protocol | 0.04564 | 0.09112 | 0 | 0.3722 | 16 | 0.01914 | 1.997 | 19 | -0.02512 |
| nillion | 0.06412 | 0.1064 | 0 | 0.4127 | 14 | 0.3137 | 1.66 | 16 | 0.5827 |
| oasis-network | 0.003797 | 0.006569 | 0 | 0.02871 | 9 | 0.6605 | 1.73 | 15 | -0.08492 |
| official-trump | 0.07008 | 0.1098 | 0 | 0.5548 | 425 | 0.2613 | 1.567 | 4 | 0.2106 |
| ondo-finance | 0.0349 | 0.1371 | 0 | 0.5723 | 2 | 0.939 | 3.928 | 2 | 0.03768 |
| openeden | 0.06135 | 0.04432 | 0 | 0.1521 | 290 | 0.09688 | 0.7224 | 21 | -0.5949 |
| opinion | 0.1081 | 0.02422 | 0 | 0.1391 | 7 | 0.02439 | 0.224 | 8 | -0.8707 |
| optimism | 0.0222 | 0.01589 | 0 | 0.09011 | 55 | 0.05991 | 0.7155 | 48 | -0.7428 |
| osmosis | 0.005925 | 0.001413 | 0.004655 | 0.008028 | 701 | 0 | 0.2386 | 0 | -1 |
| particle-network | 0.06785 | 0.1851 | 0 | 0.7844 | 14 | 0.3143 | 2.728 | 16 | 0.6318 |
| pendle | 0.00204 | 0.0006436 | 0.001304 | 0.003421 | 701 | 0 | 0.3155 | 0 | -1 |
| pixels | 0.04361 | 0.01235 | 0 | 0.1332 | 27 | 0.01854 | 0.2831 | 30 | -0.7476 |
| plasma | 0.04063 | 0.007951 | 0 | 0.08296 | 16 | 0.01538 | 0.1957 | 16 | -0.8954 |
| plume | 0.07162 | 0.1181 | 0.02942 | 0.4868 | 363 | 0 | 1.649 | 2 | 0.2943 |
| polkadot | 0.005998 | 0.0005916 | 0.005535 | 0.01129 | 701 | 0 | 0.09863 | 0 | -1 |
| polygon-ecosystem-token | 0.001629 | 8.545e-06 | 0.00161 | 0.001644 | 496 | 0 | 0.005244 | 0 | -0.2497 |
| portal-2 | 0.04171 | 0.02129 | 0.005962 | 0.08817 | 701 | 0 | 0.5103 | 0 | -0.99 |
| pudgy-penguins | 0.004603 | 0.00528 | 0 | 0.01133 | 273 | 0.5519 | 1.147 | 11 | 0.7703 |
| pump-fun | 0.01903 | 0.05653 | 0 | 0.2073 | 66 | 0.8083 | 2.971 | 2 | 0.6685 |
| pyth-network | 0.0409 | 0.1375 | 0 | 0.5862 | 3 | 0.9144 | 3.362 | 4 | 0.08487 |
| quickswap | 0.000256 | 0.001583 | 0 | 0.01477 | 25 | 0.9658 | 6.184 | 10 | -0.315 |
| radicle | 0.00315 | 0.006481 | 0 | 0.01774 | 148 | 0.7903 | 2.057 | 13 | -0.7116 |
| redstone-oracles | 0.0338 | 0.03438 | 0 | 0.09951 | 375 | 0.2917 | 1.017 | 15 | 0.8676 |
| render-token | 0.001657 | 0.000602 | 0 | 0.004355 | 41 | 0.05278 | 0.3633 | 39 | -0.5081 |
| renzo | 0.07445 | 0.05647 | 0 | 0.2454 | 217 | 0.01141 | 0.7585 | 54 | -0.3601 |
| resolv | 0.06501 | 0.02584 | 0.0342 | 0.1148 | 431 | 0 | 0.3975 | 7 | -0.5356 |
| rocket-pool | 0.004333 | 0.0001267 | 0.004121 | 0.004559 | 701 | 0 | 0.02925 | 0 | -1 |
| saga-2 | 0.1273 | 0.4633 | 0 | 2.403 | 525 | 0.2525 | 3.641 | 2 | 0.1499 |
| sahara-ai | 0.06391 | 0.06794 | 0 | 0.301 | 16 | 0.01923 | 1.063 | 21 | -0.02941 |
| scroll | 0.03618 | 0.09474 | 0 | 0.4918 | 329 | 0.5053 | 2.618 | 2 | 0.674 |
| sei-network | 0.03675 | 0.01221 | 0.01363 | 0.0645 | 701 | 0 | 0.3322 | 31 | -0.9543 |
| sentient | 0.03798 | 0.002869 | 0.03345 | 0.04336 | 206 | 0 | 0.07555 | 0 | -1 |
| sign-global | 0.06299 | 0.08085 | 0 | 0.2148 | 9 | 0.52 | 1.284 | 13 | 0.3787 |
| skale | 0.004648 | 0.004807 | 0 | 0.02888 | 27 | 0.01997 | 1.034 | 35 | -0.7537 |
| sleepless-ai | 0.04414 | 0.01664 | 0 | 0.1321 | 27 | 0.01997 | 0.3771 | 32 | -0.8459 |
| solana | 0.003428 | 0.0002727 | 0.002778 | 0.003927 | 701 | 0 | 0.07955 | 0 | -0.8867 |
| solayer | 0.04529 | 0.04577 | 0 | 0.1401 | 399 | 0.225 | 1.01 | 12 | 0.1976 |
| solv-protocol | 0.07061 | 0.06377 | 0 | 0.315 | 20 | 0.1233 | 0.9031 | 27 | 0.312 |
| sonic-3 | 0.006908 | 0.01201 | 0.002081 | 0.05701 | 577 | 0 | 1.738 | 4 | 0.1766 |
| sophon | 0.04776 | 0.03081 | 0 | 0.1549 | 386 | 0.004494 | 0.645 | 20 | 0.5694 |
| space-and-time | 0.03441 | 0.05277 | 0 | 0.232 | 18 | 0.02151 | 1.534 | 22 | 0.2106 |
| space-id | 0.02977 | 0.02831 | 0 | 0.109 | 27 | 0.01854 | 0.9509 | 36 | -0.5658 |
| spark-2 | 0.0722 | 0.06961 | 0.03485 | 0.3237 | 425 | 0 | 0.9641 | 2 | -0.7133 |
| spell-token | 0.0115 | 0.005526 | 0.007462 | 0.0214 | 701 | 0 | 0.4806 | 1 | -1 |
| stargate-finance | 0.003664 | 0.006362 | 0 | 0.01576 | 186 | 0.7361 | 1.736 | 10 | -0.7753 |
| starknet | 0.05267 | 0.01508 | 0 | 0.09413 | 27 | 0.01997 | 0.2863 | 31 | -0.6159 |
| stepn | 0.01831 | 0.006331 | 0.0104 | 0.02988 | 701 | 0 | 0.3458 | 0 | -0.9969 |
| succinct | 0.08311 | 0.2826 | 0 | 1.042 | 2 | 0.9202 | 3.401 | 2 | 0.4395 |
| sui | 0.01773 | 0.008062 | 0.002081 | 0.04788 | 701 | 0 | 0.4546 | 32 | -0.9572 |
| superrare | 0.002782 | 0.003354 | 0 | 0.007042 | 11 | 0.592 | 1.206 | 1 | -0.8898 |
| synfutures | 0.05357 | 0.008197 | 0.04167 | 0.07043 | 295 | 0 | 0.153 | 0 | -1 |
| syrup | 0.002758 | 3.642e-05 | 0.00252 | 0.002819 | 467 | 0 | 0.0132 | 0 | -1 |
| tensor | 0.03077 | 0.05084 | 0.01297 | 0.2781 | 701 | 0 | 1.652 | 2 | 0.1362 |
| terra-luna-2 | 0.009939 | 0.006156 | 0.00528 | 0.02008 | 701 | 0 | 0.6193 | 0 | -1 |
| the-graph | 0.003781 | 0.00237 | 0.002091 | 0.01052 | 701 | 0 | 0.6267 | 0 | -1 |
| the-sandbox | 0.003149 | 0.0149 | 0 | 0.07357 | 2 | 0.9572 | 4.733 | 2 | -0.222 |
| treehouse | 0.08344 | 0.0914 | 0 | 0.3941 | 24 | 0.01044 | 1.095 | 21 | -0.4842 |
| uniswap | 5.952e-07 | 1.174e-05 | 0 | 0.0002782 | 3 | 0.9971 | 19.72 | 2 | -0.09238 |
| usual | 0.06338 | 0.04358 | 0.04018 | 0.2727 | 635 | 0 | 0.6875 | 2 | -0.3141 |
| woo | 0.0008141 | 0.002561 | 0 | 0.01308 | 104 | 0.8531 | 3.145 | 10 | -0.6158 |
| world-liberty-financial | 0.01576 | 0.05148 | 0 | 0.1834 | 2 | 0.914 | 3.266 | 2 | 0.1933 |
| worldcoin-wld | 0.04501 | 0.01551 | 0.01541 | 0.08174 | 701 | 0 | 0.3447 | 0 | -1 |
| wormhole | 0.04215 | 0.1027 | 0.009422 | 0.53 | 701 | 0 | 2.437 | 50 | 0.448 |
| xai-blockchain | 0.05125 | 0.02441 | 0.009853 | 0.1204 | 701 | 0 | 0.4763 | 0 | -0.9963 |
| yield-basis | 0.1374 | 0.02823 | 0.09382 | 0.207 | 305 | 0 | 0.2054 | 0 | 0.05921 |
| yield-guild-games | 0.01366 | 0.005207 | 0 | 0.0374 | 27 | 0.01854 | 0.3812 | 32 | -0.9559 |
| zama | 0.04437 | 0.003708 | 0.03857 | 0.05138 | 195 | 0 | 0.08358 | 0 | -1 |
| zcash | 0.003224 | 0.00102 | 0.002823 | 0.006931 | 701 | 0 | 0.3164 | 0 | -1 |
| zero-gravity | 0.03645 | 0.00421 | 0.03008 | 0.04474 | 328 | 0 | 0.1155 | 0 | -1 |
| zksync | 0.02784 | 0.04136 | 0 | 0.2091 | 17 | 0.3623 | 1.486 | 20 | 0.4201 |

Reading: `day_jumps_gt10pct` counts day-to-day changes of the feature larger than 10%, i.e. scheduled cliffs entering/leaving the 30-day window. **129 tokens have any such step**; the other 47 have a smooth ratio that drifts with the growing float. For 58 tokens the feature is a strictly monotone function of time (|Spearman vs `days_since_tge`| > 0.95), so any correlation it shows with volatility for those tokens is a time trend, not an unlock signal. Cross-sectionally the token-mean feature spans 0.0000 to 0.1374, so a pooled model without token fixed effects would mostly learn token identity.

## 5. Spearman correlation: `emis_next_30d_pct_float` vs `rv_fwd_14d`

- Pooled Spearman, all rows: **+0.141** (n=103685).
- Within-token Spearman (ranks computed inside each token, then pooled): **+0.315**. For comparison the persistence baseline `rv_past_14d` vs `rv_fwd_14d` is +0.322 on the same basis.
- Within-token Spearman of the feature vs the **change** in vol (`rv_fwd_14d - rv_past_14d`): **+0.121**. This is the honest test: does knowing the next 30 days of unlocks tell you anything beyond the vol you already observe?

| token_id | n | feat_vs_rv_fwd_14d | feat_vs_rv_past_14d | feat_vs_vol_change | rv_past_vs_rv_fwd | days_to_cliff_vs_rv_fwd |
|---|---|---|---|---|---|---|
| 1inch | 701 | +0.371 | +0.337 | +0.023 | +0.324 | -0.282 |
| aave | 701 | +0.318 | +0.326 | -0.005 | +0.071 | NaN |
| altlayer | 701 | +0.240 | +0.220 | +0.038 | +0.413 | +0.217 |
| anime | 570 | -0.509 | -0.428 | -0.072 | +0.366 | -0.023 |
| apecoin | 701 | +0.369 | +0.345 | -0.017 | +0.269 | +0.083 |
| aptos | 701 | +0.337 | +0.292 | +0.046 | +0.053 | -0.063 |
| arbitrum | 701 | +0.428 | +0.393 | +0.026 | +0.143 | -0.028 |
| arkham | 701 | +0.490 | +0.438 | +0.009 | +0.154 | NaN |
| astar | 701 | +0.360 | +0.363 | +0.010 | +0.127 | +0.043 |
| aster-2 | 314 | +0.732 | +0.775 | -0.077 | +0.654 | NaN |
| avalanche-2 | 701 | +0.268 | +0.149 | +0.099 | +0.344 | +0.122 |
| avantis | 335 | +0.630 | +0.711 | -0.294 | +0.388 | NaN |
| axelar | 701 | +0.383 | +0.325 | +0.075 | +0.165 | NaN |
| axie-infinity | 701 | +0.230 | +0.183 | +0.053 | +0.181 | -0.069 |
| babylon | 493 | +0.090 | -0.067 | +0.177 | +0.117 | -0.019 |
| banana-gun | 701 | +0.088 | +0.062 | +0.031 | +0.349 | +0.326 |
| benqi | 701 | +0.054 | -0.001 | +0.093 | -0.031 | +0.203 |
| berachain-bera | 556 | -0.059 | -0.053 | -0.024 | +0.273 | +0.046 |
| biconomy | 701 | +0.280 | +0.298 | +0.002 | +0.125 | +0.169 |
| big-time | 492 | +0.283 | +0.345 | -0.096 | +0.266 | +0.199 |
| bio-protocol | 590 | +0.222 | +0.235 | +0.006 | +0.441 | -0.208 |
| bittensor | 701 | +0.472 | +0.475 | -0.037 | +0.260 | NaN |
| blur | 701 | +0.307 | +0.279 | +0.040 | +0.078 | NaN |
| bonfida | 701 | +0.172 | +0.173 | -0.011 | +0.090 | NaN |
| bonk | 701 | +0.544 | +0.462 | +0.052 | +0.254 | NaN |
| bouncebit | 701 | -0.014 | +0.078 | -0.052 | +0.269 | +0.070 |
| bubblemaps | 516 | +0.397 | +0.504 | -0.029 | +0.399 | +0.080 |
| cartesi | 701 | +0.268 | +0.221 | +0.095 | +0.075 | NaN |
| catizen | 695 | -0.438 | -0.213 | -0.187 | +0.361 | +0.114 |
| celestia | 701 | +0.431 | +0.424 | +0.023 | +0.033 | +0.105 |
| celo | 701 | +0.382 | +0.349 | -0.006 | +0.158 | -0.040 |
| cetus-protocol | 648 | +0.610 | +0.592 | +0.022 | +0.414 | -0.064 |
| chaingpt | 583 | +0.479 | +0.500 | -0.048 | +0.271 | NaN |
| chainlink | 701 | +0.274 | +0.266 | -0.010 | +0.427 | -0.627 |
| coin98 | 701 | +0.256 | +0.207 | +0.038 | +0.265 | +0.056 |
| conflux-token | 701 | +0.145 | +0.067 | +0.044 | +0.026 | NaN |
| connect-token-wct | 488 | -0.013 | +0.051 | -0.068 | +0.320 | +0.239 |
| convex-finance | 701 | +0.264 | +0.211 | +0.037 | +0.406 | NaN |
| cookie | 583 | +0.511 | +0.572 | -0.053 | +0.227 | +0.145 |
| cosmos | 701 | -0.384 | -0.374 | +0.014 | +0.373 | NaN |
| cow-protocol | 648 | +0.647 | +0.719 | -0.060 | +0.477 | NaN |
| curve-dao-token | 701 | +0.446 | +0.452 | +0.012 | +0.397 | NaN |
| decentraland | 701 | +0.539 | +0.462 | +0.037 | +0.382 | NaN |
| dodo | 701 | +0.168 | +0.194 | -0.007 | +0.119 | -0.023 |
| dogecoin | 701 | +0.598 | +0.570 | +0.057 | +0.369 | NaN |
| dolomite | 354 | -0.160 | -0.297 | +0.124 | +0.439 | -0.020 |
| doublezero | 318 | NaN | NaN | NaN | +0.460 | +0.613 |
| dydx | 701 | +0.199 | +0.121 | +0.030 | +0.119 | -0.062 |
| dymension | 701 | +0.172 | +0.161 | +0.015 | +0.262 | NaN |
| edu-coin | 701 | +0.239 | +0.191 | +0.003 | +0.202 | NaN |
| eigenlayer | 684 | -0.232 | -0.229 | +0.066 | +0.376 | -0.309 |
| elrond-erd-2 | 701 | +0.423 | +0.366 | +0.035 | +0.143 | NaN |
| endurance | 701 | +0.191 | +0.298 | -0.118 | +0.251 | -0.009 |
| ethena | 701 | +0.173 | +0.207 | -0.027 | +0.236 | -0.333 |
| ether-fi | 701 | +0.267 | +0.288 | -0.015 | +0.239 | +0.081 |
| ethereum-name-service | 701 | +0.501 | +0.455 | +0.053 | +0.239 | NaN |
| euler | 307 | -0.158 | -0.039 | -0.068 | +0.125 | +0.135 |
| falcon-finance-ff | 321 | -0.026 | -0.021 | +0.182 | +0.181 | +0.450 |
| fetch-ai | 701 | +0.275 | +0.280 | +0.040 | +0.331 | NaN |
| filecoin | 701 | +0.213 | +0.176 | +0.031 | +0.097 | NaN |
| flow | 701 | +0.071 | +0.025 | +0.047 | +0.123 | NaN |
| fogo | 213 | NaN | NaN | NaN | +0.353 | +0.381 |
| frax-share | 213 | +0.415 | +0.415 | -0.359 | -0.074 | NaN |
| gmx | 701 | +0.369 | +0.280 | +0.069 | +0.124 | NaN |
| goplus-security | 530 | -0.127 | -0.109 | +0.004 | +0.015 | +0.110 |
| gunz | 503 | -0.137 | -0.051 | -0.060 | +0.110 | +0.037 |
| haedal | 452 | -0.376 | -0.325 | -0.064 | +0.222 | NaN |
| home | 430 | +0.166 | +0.090 | +0.115 | +0.211 | -0.217 |
| huma-finance | 447 | -0.166 | -0.081 | -0.032 | +0.254 | +0.148 |
| hyperlane | 481 | -0.353 | -0.295 | -0.027 | +0.027 | +0.357 |
| illuvium | 701 | +0.325 | +0.290 | +0.032 | +0.270 | NaN |
| immutable-x | 701 | +0.483 | +0.446 | +0.030 | +0.325 | +0.188 |
| initia | 479 | -0.153 | -0.197 | -0.059 | +0.463 | +0.522 |
| io | 701 | -0.166 | -0.198 | +0.033 | +0.276 | -0.111 |
| iota | 701 | +0.468 | +0.441 | +0.017 | +0.377 | -0.090 |
| jito-governance-token | 701 | -0.023 | -0.025 | +0.045 | +0.186 | -0.275 |
| jupiter-exchange-solana | 701 | +0.397 | +0.427 | -0.036 | +0.245 | -0.065 |
| kaia | 654 | +0.414 | +0.456 | -0.031 | +0.174 | NaN |
| kaito | 542 | -0.301 | -0.273 | +0.087 | +0.445 | +0.246 |
| kamino | 467 | +0.197 | +0.198 | +0.003 | +0.358 | +0.053 |
| katana-network-token | 151 | +0.675 | +0.414 | +0.111 | +0.242 | +0.137 |
| kernel-2 | 489 | -0.127 | -0.037 | -0.063 | +0.441 | +0.261 |
| kite-2 | 286 | +0.233 | +0.179 | -0.028 | +0.441 | +0.233 |
| lagrange | 403 | -0.234 | -0.214 | +0.019 | +0.138 | NaN |
| layerzero | 701 | -0.294 | -0.254 | -0.028 | +0.218 | +0.283 |
| linea | 340 | +0.607 | +0.672 | -0.136 | +0.516 | +0.027 |
| liquity | 701 | +0.556 | +0.547 | -0.033 | +0.394 | -0.307 |
| lista | 701 | +0.154 | +0.217 | -0.114 | +0.382 | +0.019 |
| litecoin | 701 | +0.592 | +0.362 | +0.243 | +0.512 | NaN |
| lombard-protocol | 332 | +0.347 | +0.222 | -0.021 | +0.108 | -0.108 |
| magic-eden | 614 | +0.408 | +0.399 | -0.018 | +0.321 | -0.032 |
| manta-network | 701 | +0.214 | +0.197 | +0.027 | +0.315 | -0.048 |
| maverick-protocol | 701 | +0.143 | +0.224 | -0.137 | +0.369 | +0.100 |
| memecoin-2 | 701 | +0.534 | +0.502 | +0.016 | +0.250 | -0.179 |
| meteora | 276 | -0.043 | -0.087 | -0.047 | +0.012 | -0.190 |
| metis-token | 701 | +0.487 | +0.459 | +0.041 | +0.148 | NaN |
| mina-protocol | 701 | +0.436 | +0.432 | +0.027 | +0.170 | NaN |
| mira-3 | 324 | -0.420 | -0.271 | -0.050 | +0.193 | -0.115 |
| momentum-3 | 285 | -0.033 | -0.017 | -0.145 | +0.233 | +0.024 |
| moonbeam | 701 | +0.188 | +0.176 | +0.036 | +0.013 | -0.155 |
| morpho | 317 | -0.081 | +0.084 | -0.012 | +0.222 | NaN |
| movement | 615 | -0.223 | -0.186 | -0.016 | +0.179 | +0.052 |
| my-neighbor-alice | 701 | +0.126 | +0.099 | +0.058 | -0.049 | -0.126 |
| myshell | 535 | -0.328 | -0.291 | -0.014 | +0.461 | +0.415 |
| near | 701 | +0.287 | +0.268 | +0.017 | +0.178 | NaN |
| nervos-network | 701 | +0.578 | +0.601 | -0.043 | +0.370 | NaN |
| newton-protocol | 418 | -0.149 | -0.133 | -0.030 | +0.059 | -0.136 |
| nillion | 510 | +0.044 | -0.075 | +0.066 | +0.241 | -0.047 |
| oasis-network | 701 | +0.308 | +0.103 | +0.098 | +0.299 | -0.201 |
| official-trump | 574 | -0.374 | -0.454 | +0.134 | +0.396 | +0.414 |
| ondo-finance | 492 | +0.041 | -0.005 | +0.060 | -0.063 | -0.049 |
| openeden | 320 | +0.139 | +0.235 | -0.240 | +0.254 | NaN |
| opinion | 164 | +0.375 | +0.168 | +0.257 | -0.023 | -0.033 |
| optimism | 701 | +0.166 | +0.284 | -0.062 | +0.114 | -0.059 |
| osmosis | 701 | +0.284 | +0.326 | +0.041 | +0.232 | NaN |
| particle-network | 509 | -0.087 | -0.099 | +0.083 | +0.131 | +0.287 |
| pendle | 701 | +0.415 | +0.385 | +0.048 | +0.227 | NaN |
| pixels | 701 | +0.464 | +0.451 | +0.028 | +0.315 | +0.072 |
| plasma | 325 | +0.211 | +0.347 | -0.177 | +0.243 | +0.213 |
| plume | 363 | -0.249 | -0.282 | +0.079 | +0.044 | +0.309 |
| polkadot | 701 | +0.323 | +0.262 | +0.018 | +0.224 | NaN |
| polygon-ecosystem-token | 701 | +0.402 | +0.386 | -0.021 | +0.318 | NaN |
| portal-2 | 701 | +0.207 | +0.229 | +0.069 | -0.004 | NaN |
| pudgy-penguins | 607 | -0.527 | -0.541 | -0.000 | +0.468 | NaN |
| pump-fun | 339 | +0.039 | -0.041 | +0.106 | +0.546 | +0.643 |
| pyth-network | 701 | +0.137 | -0.009 | +0.063 | +0.061 | -0.076 |
| quickswap | 701 | +0.003 | +0.137 | -0.135 | +0.272 | NaN |
| radicle | 701 | +0.334 | +0.300 | +0.091 | +0.161 | NaN |
| redstone-oracles | 528 | -0.428 | -0.370 | -0.029 | +0.261 | NaN |
| render-token | 701 | +0.224 | +0.088 | +0.087 | +0.235 | NaN |
| renzo | 701 | +0.279 | +0.324 | -0.072 | +0.377 | +0.322 |
| resolv | 431 | +0.107 | +0.031 | +0.041 | -0.009 | -0.153 |
| rocket-pool | 701 | +0.410 | +0.399 | +0.018 | +0.248 | NaN |
| saga-2 | 701 | -0.037 | -0.031 | +0.015 | +0.100 | +0.081 |
| sahara-ai | 416 | +0.192 | +0.304 | -0.053 | +0.226 | -0.047 |
| scroll | 663 | -0.312 | -0.315 | +0.023 | +0.326 | +0.282 |
| sei-network | 701 | +0.571 | +0.537 | +0.027 | +0.266 | +0.023 |
| sentient | 206 | +0.310 | +0.245 | -0.139 | +0.028 | +0.310 |
| sign-global | 475 | -0.161 | -0.083 | -0.049 | +0.319 | +0.288 |
| skale | 701 | +0.374 | +0.222 | +0.111 | +0.137 | -0.100 |
| sleepless-ai | 701 | +0.436 | +0.423 | +0.047 | +0.336 | -0.129 |
| solana | 701 | +0.484 | +0.474 | +0.026 | +0.321 | NaN |
| solayer | 551 | +0.007 | -0.091 | +0.087 | +0.336 | +0.043 |
| solv-protocol | 576 | -0.076 | -0.176 | +0.045 | +0.525 | +0.145 |
| sonic-3 | 577 | -0.220 | -0.165 | +0.005 | +0.186 | +0.742 |
| sophon | 445 | -0.252 | -0.262 | +0.105 | +0.349 | +0.045 |
| space-and-time | 465 | -0.003 | -0.054 | +0.017 | +0.172 | -0.056 |
| space-id | 701 | +0.180 | +0.150 | +0.039 | +0.254 | +0.080 |
| spark-2 | 425 | +0.426 | +0.557 | -0.086 | +0.328 | +0.481 |
| spell-token | 701 | +0.608 | +0.556 | +0.063 | +0.407 | -0.142 |
| stargate-finance | 701 | +0.103 | +0.066 | -0.003 | +0.360 | NaN |
| starknet | 701 | +0.321 | +0.307 | +0.017 | +0.296 | +0.011 |
| stepn | 701 | +0.480 | +0.477 | +0.052 | +0.332 | NaN |
| succinct | 376 | -0.324 | -0.325 | +0.062 | +0.242 | +0.503 |
| sui | 701 | +0.563 | +0.589 | +0.019 | +0.291 | -0.072 |
| superrare | 701 | +0.311 | +0.290 | +0.032 | +0.050 | -0.007 |
| synfutures | 295 | +0.384 | +0.458 | -0.217 | +0.239 | NaN |
| syrup | 467 | +0.584 | +0.614 | -0.067 | +0.374 | NaN |
| tensor | 701 | -0.109 | -0.036 | -0.082 | +0.204 | +0.028 |
| terra-luna-2 | 701 | +0.418 | +0.457 | -0.019 | +0.185 | NaN |
| the-graph | 701 | +0.603 | +0.612 | -0.009 | +0.348 | NaN |
| the-sandbox | 701 | +0.131 | +0.210 | -0.049 | +0.255 | -0.316 |
| treehouse | 383 | +0.450 | +0.238 | +0.119 | +0.400 | +0.069 |
| uniswap | 701 | -0.064 | -0.024 | -0.019 | +0.015 | NaN |
| usual | 635 | +0.192 | +0.251 | -0.013 | +0.425 | +0.447 |
| woo | 701 | +0.297 | +0.270 | +0.016 | +0.267 | NaN |
| world-liberty-financial | 349 | +0.170 | +0.102 | +0.051 | +0.579 | +0.418 |
| worldcoin-wld | 701 | +0.313 | +0.279 | +0.068 | +0.026 | NaN |
| wormhole | 701 | -0.157 | -0.088 | -0.039 | +0.172 | +0.310 |
| xai-blockchain | 701 | +0.547 | +0.516 | +0.027 | +0.245 | NaN |
| yield-basis | 305 | +0.141 | +0.118 | -0.056 | +0.051 | NaN |
| yield-guild-games | 701 | +0.490 | +0.503 | -0.000 | +0.206 | +0.095 |
| zama | 195 | +0.181 | +0.252 | -0.327 | -0.078 | +0.181 |
| zcash | 701 | -0.230 | -0.269 | +0.040 | +0.440 | NaN |
| zero-gravity | 328 | +0.394 | +0.420 | -0.094 | +0.288 | NaN |
| zksync | 701 | -0.043 | +0.019 | -0.061 | +0.279 | +0.330 |

Reading: in 150 of 176 tokens the feature correlates with *past* vol almost exactly as much as with *future* vol (columns 3 and 4 differ by < 0.1); 47 tokens have a negative feature-vs-future-vol correlation. Combined with section 4 (the feature is monotone in time for many tokens) this is the signature of slowly drifting series sharing a trend, not of unlocks moving volatility. The vol-change column removes that level effect: across tokens its median is +0.02, interquartile range -0.04 to +0.05, and 2 tokens exceed +0.20 while 5 are below -0.20. With ~700 autocorrelated daily rows per token, individual values of this size are not distinguishable from noise without a block bootstrap; the cross-token distribution being centred slightly above zero is the only thing worth following up.

## 6. Effective sample size

- Daily rows: 103685. One row per token per week (Mondays): **14769** rows (per token min 21, median 100, max 100).
- Mean lag-1 autocorrelation of `rv_fwd_14d` within token: 0.956; lag-14: 0.192. Overlapping 14-day windows make consecutive targets share 13/14 of their data, so weekly sampling still leaves overlap; non-overlapping 14-day blocks would give ~7406 rows.
- Cross-sectional breadth is the binding constraint: **176 tokens**, of which only 129 show step-like unlock variation (section 4). A pooled model is effectively fitting 129 informative time series plus token fixed effects.

## 7. Schema surprises vs SCHEMA_REPORT.md

Field-level diff (2026-08-20 samples vs 2026-09-14 pulls):

- `emission daily`: fields missing vs sample: none; new fields: none.
- `unlock events`: fields missing vs sample: none; new fields: none.
- `allocation detail`: fields missing vs sample: none; new fields: none.
- `token list`: fields missing vs sample: none; new fields: none.

Behavioural / unit surprises (computed over the pulled universe):

- Token list grew from 626 to **629** rows; same 19 fields.
- **Plan-enforced date window** on `emission daily`: `Invalid Date Range: The available range for emission data are 2024-09-14 - 2027-06-30`. The schema report never hit this because it queried 2025. The returned series ends 2027-06-29 (the `--end` day itself is excluded).
- `--page-size 10000` is accepted and returns the full series in one call (max 1019 daily rows); the silent 20-row truncation from the schema report does not apply once `--page-size` is passed explicitly. No pagination calls were needed.
- `unlock events` returns `[]` for **50 of 176** tokens even though `emission daily` is populated for them: continuous issuance and linear vesting are not modelled as cliff events. `has_unlock_events` flags this.
- `emission daily.allocations[]` is **empty** on 50530 of 140695 rows (days with `unlockAmount == 0`); the schema report said it 'normally has 1 element'. Row-level `unlockAmount` is the reliable field; the bucket split is `emis_next_30d_<bucket>` with `emis_next_30d_unattributed` as the residual.
- `unlockPrecision` values observed across all cliff breakdown lines: {'second': 273, 'day': 1525, 'month': 2408, 'week': 317, 'unknown': 811, 'minute': 1, 'hour': 170, 'block': 33}. The schema report only saw `day`.
- `allocation detail.allocationLockedAmount` is **slightly negative** for 51 tokens (e.g. SUI Series B: -5.96e-07) -> floating-point residue, not a data error; do not assert >= 0.
- `allocation detail.maxSupply` is **null for 29 of 176 tokens** (uncapped supply). `emis_next_30d_pct_total` for those uses the sum of `allocationAmount` instead (`total_supply_basis` column).
- `totalCumulativeUnlockedAmount` is cumulative since inception even though the series starts 2024-09-14 (SUI first row = 2.67e9), so `float_pit` is usable from the first row. It is **end-of-day inclusive** (SUI 2024-10-01 cliff appears in the 2024-10-01 row).
- For 74 tokens the emission series starts before the Binance listing (e.g. aster-2: emission 2025-09-14, listing 2025-10-06); rows before listing have no prices and are absent from the panel.
- `emission daily` and `allocation detail` still omit `tokenId`; it is injected from the directory name, as the schema report recommended.

## 8. API credits spent (from `data/call_log.txt`)

- Successful (`exit=0`) Tokenomist calls: **564** (pass 1 ceiling 40, pass 2 ceiling 2000; plan allows 5M/month at 120/min). One of these is a wasted duplicate of `token list` (first attempt returned data but the local decoder crashed on the Windows cp874 codepage; fixed by forcing UTF-8).
- Failed attempts (`exit=1`, `Invalid Date Range`, presumably not billed but listed for completeness): **4**.
- By endpoint (successful): `allocation detail` x177, `emission daily` x208, `token list` x2, `unlock events` x177.
- Failed attempts also include 1 `allocation detail` timeout (ether-fi) that succeeded on retry.
- Binance: roughly 968 public requests (`exchangeInfo`, listing-date probes, ticker prices, daily klines), paced at >= 0.35 s; used weight stayed far below the 6000/min limit.

## 8b. Date-alignment audit (`scripts/audit_alignment.py`)

- Tokenomist emission buckets start at 00:00:00Z and span exactly one day; Binance daily candles use the same UTC day. No missing or duplicate days in either source inside the panel window.
- Tokenomist's own `referencePrice` on day D matches the Binance **open of D / close of D-1** to about 0.15% (median across tokens) versus about 3% for the close of D. The two calendars are therefore aligned with no one-day shift, and the reference price is a start-of-day price.
- Cliff events fall on the same UTC date as the matching spike in the emission series for all but one event.
- Thirteen feature and target columns were recomputed independently by calendar-date lookup for 5 random dates per token; every value equals the dataset value.
- dYdX: Tokenomist's `referencePrice` is frozen at a stale value from 2025 on. The dataset never uses that field.

## 9. Feasibility verdict and what to change for v2

**Feasible as a dataset; the signal question is open.** The panel now holds every token this data source and Binance can jointly support (176 tokens, 103685 daily rows). Joins, point-in-time float, forward emission windows and forward RV targets reconcile by hand (see `build_dataset.py` docstring). What remains are modelling-design issues, not data-access ones:

1. **Heterogeneous universe.** 129 of 176 tokens have scheduled cliffs that move `emis_next_30d_pct_float` day to day; the other 47 are smooth issuance or linear vesting. Subset at modelling time with `has_unlock_events` / the section-4 step counts, or model the two regimes separately; do not pool blindly.
2. **History is capped at 2024-09-14** by the plan, so no token contributes more than ~700 daily rows / ~100 weekly rows, and the whole panel sits inside one market regime. Every token that passes the Binance-pair and age filters is already in; the only ways to grow further are a second price source for the 412 tokens without a Binance USDT pair, or waiting for history to accrue.
3. **Schedule revisions are invisible.** Emission rows carry today's curated schedule; `latestUpdateDate` on unlock events proves schedules get edited after the fact. `emis_next_*` are lookahead-safe in the mechanical sense (window starts D+1, float uses row D) but not in the information sense. Mitigation: snapshot `emission daily` weekly from now on and only use as-of snapshots for dates after the first snapshot.
4. **Signal check:** the feature's within-token correlation with future vol (+0.31) is about the same as the persistence baseline (+0.32), but it correlates just as strongly with *past* vol and only +0.12 with the change in vol, and it is monotone in time for 58 of 176 tokens. The raw correlation is a shared trend, not evidence of an unlock effect. A v2 model must be judged on incremental gain over HAR/GARCH-style baselines built from `rv_past_*` and `btc_rv_past_14d`, with rolling-origin or leave-one-token-out splits, no shuffling, and a block bootstrap for uncertainty.

Re-pull cost to refresh everything from scratch: 1 + 3 x 176 = 529 calls (~6 minutes at 100/min). Recommended cadence for the as-of snapshot mitigation in point 3: weekly `emission daily` only, 176 calls per week.

