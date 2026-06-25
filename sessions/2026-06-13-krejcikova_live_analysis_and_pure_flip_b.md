# Session: Krejcikova Live Analysis & PURE_FLIP_B
**Date:** 2026-06-13  
**UUID:** `d048a2ac-0e61-449f-85ca-2b2dcae3338c`  
**Messages:** 22

---

## 👤 User  _2026-06-11 11:50_

dangerously

---

## 🤖 Claude  _2026-06-11 11:51_

Could you clarify what you mean by "dangerously"? Are you asking me to:

- Run Claude Code with `--dangerously-skip-permissions`?
- Operate more autonomously without confirmation prompts?
- Something specific to the falcon project?

---

## 👤 User  _2026-06-11 11:51_

get the most recent context last time we were speaking

---

## 🤖 Claude  _2026-06-11 12:04_

The claude-mem search is having an ONNX model error. Let me pull context from the memory file and recent code instead.

---

## 🤖 Claude  _2026-06-11 12:07_

Here's where we left off last session:

**Last work:** Built `expand_cluster.py` to find non-cluster wallets co-appearing in the same Jun-10 markets as the 14 cluster wallets. It ran and produced `market_sessions/expansion_2026-06-10.json`.

**Results:**
- Cluster was active in **45 markets** on Jun-10
- Found **362 wallets in 3+ of the same markets** (strongest signal)
- Top candidates by market count: `0xf7f0b0b1e9c0fe02ccad926916ee31aef74b912c` (19 markets, $5,774), `0x98db8cca55c32b24cfb414b5b43d273f4e1fdd17` (15 markets, $13,121 — highest spend among top 10)

**`g2_results.txt`** just has `DONE:0` — looks like a test/placeholder.

**Pending next steps from MEMORY.md:**
1. Analyze the expansion candidates — which ones look like genuine signal vs noise (high market count but tiny spend)
2. Run `today_tennis.py` for Jun-11 (today) — currently hardcoded to Jun-10
3. Live signal tracking (~09:10 UTC cluster fire time)
4. Polygonscan/Etherscan API key for on-chain funding flow

What do you want to tackle?

---

## 👤 User  _2026-06-12 08:42_

we had those winning wallet we tracked wanted to the cluster on find out what they buying today

---

## 🤖 Claude  _2026-06-12 08:42_

Good. Top candidates by spend. Now let me write a script to check all of them (+ original cluster) for today's picks.

---

## 🤖 Claude  _2026-06-12 08:48_

Here's today's picture across the 28 wallets (14 cluster + 14 expansion candidates):

---

## Today's Picks — Jun 12

### Strongest Jun-12 signals (today's dated markets)

| Match | Pick | $ | Wallets | Notes |
|---|---|---|---|---|
| `atp-blan-sanchis` | **David Jorda Sanchis** | $9,535 | 11 exp + 4 cluster | px 0.33–0.41, pre-match |
| `atp-blan-sanchis` | Dali Blanch | $3,238 | 8 exp + 4 cluster | px 0.59–0.68 (both sides!) |
| `atp-zhang-mannari` | **Adrian Mannarino** | $4,858 | 10 cluster + expand | px 0.56–0.60 |
| `atp-zhang-mannari` | Zhizhen Zhang | $3,536 | 6 cluster + expand | px 0.40–0.43 (split) |
| `atp-almeida-rodr` | **Pucinelli de Almeida** | $3,689 | 3 cluster + expand | px **0.79–0.81** (live!) |
| `atp-perrica-bublik` | **Perricard** | $2,341 | Exp#1+#3+#12 | px 0.36–0.39 |
| `atp-bonzi-minaur` | **Alex de Minaur** | $1,228 | All3 #1 + expand | px **0.78–0.79** (live!) |

### Notable carryover (Jun-10/11 slugs, trading today)
- **Elena Rybakina** $7,314 — cluster + Exp#2 at px 0.79–0.81 (live)
- **Dusan Lajovic** $6,008 — RANK16 + Exp#2 + #7/#8 at px 0.51–0.57
- **Donna Vekic** $2,690 — RANK16 + Exp#2/#5/#7 at px 0.47
- **Katie Boulter** $2,738 — Exp#2 dominant at px 0.67
- **Jacob Fearnley** $2,090 — Exp#2 dominates at px 0.66–0.70

### Top performing expansion wallets today
- **Exp#2 ($18k, 9m)** — most active, in 7+ markets (Lajovic, Fearnley, Boulter, Sweeny, Vekic...)
- **Exp#5 ($13k, 15m)** — Mannarino, Sanchis, Tomljanovic, Harris
- **Exp#4 ($17k, 9m)** — heavy on Sanchis ($5k+)
- **Exp#3 ($17k, 13m)** — Sanchis, Perricard

**Bottom line:** Sanchis and Mannarino are the strongest undisputed consensus picks for today's Jun-12 matches. Perricard getting loaded by expansion wallets only (Exp#1/#3/#12) with no core cluster — worth watching but slightly lower confidence. De Minaur + Rybakina + Almeida are at live prices (0.78+), matches already underway.

---

## 👤 User  _2026-06-12 08:50_

those are the winning wallets from the other day, the ones that converged on the 2 and 3+ winning matches i told you?

---

## 🤖 Claude  _2026-06-12 08:50_

Not quite — worth being precise here. The expansion candidates were found by **co-appearing in 2+ of the same markets as the cluster on Jun-10**, not specifically verified as winners.

Here's the chain:

1. **Jun-08** → 63 wallets called all 3 winners (Mertens + Bellucci + Udvardy) → filtered down to **14 cluster wallets** based on size/pattern
2. **Jun-10** → ran `expand_cluster.py` which found wallets appearing in 2+ of the same markets the cluster was active in → **these 14 expansion candidates**

So the expansion candidates were co-locating with the sharp cluster, but we never checked whether the Jun-10 picks **actually won**. We just know they bet alongside the cluster.

To properly validate these as "smart" wallets we'd want to:
- Pull the Jun-10 match results and check how many of their picks won
- See if they specifically agreed with the cluster's side (same outcome) or were on the opposite side

Want me to do that check? I can cross-reference the Jun-10 expansion data against outcomes — matches at px 0.80+ at time of bet are a proxy for "live/won" but ideally we'd look at final prices.

---

## 👤 User  _2026-06-12 08:51_

do it again. tell me where the winning wallets are on... no ones on bublik?

---

## 🤖 Claude  _2026-06-12 08:54_

The Bublik market is **split** — the sharper money is actually on Perricard:

**Perricard side** (px 0.36–0.39, underdog):
- Exp#1 ($21k) — 12 trades
- Exp#3 ($17k) — 12 trades  
- Exp#12 ($3k) — 5 trades
- **BU Sharp#4** (core cluster) — 2 trades

**Bublik side** (px 0.62–0.63, favourite):
- Exp#7 ($9k) — 11 trades (dominant)
- Exp#5 ($13k) — 3 trades
- Exp#8 ($9k) — 2 trades
- Exp#13 ($3k) — 2 trades
- Exp#1 ($21k) — 2 trades (also hedging the other side)

So there IS money on Bublik, but it's the expansion wallets only — no core cluster. The **cluster-side signal is Perricard** (BU Sharp#4 + Exp#1 + Exp#3 all loading the underdog at 0.36–0.39).

Exp#7 is the main Bublik backer — but Exp#7 also took the losing side on other markets before (we haven't validated their hit rate yet). 

Worth noting Exp#1 is hedging both sides which muddies it slightly, but their bigger position is on Perricard.

---

## 👤 User  _2026-06-12 08:58_

difference of expansion wallets vs core cluster?

---

## 🤖 Claude  _2026-06-12 08:59_

**Core cluster (14 wallets)** — validated the hard way:
- Started with 63 wallets that called all 3 Jun-08 winners correctly (Mertens + Bellucci + Udvardy)
- Then filtered for significant bet size and consistent pattern
- These are proven sharp — their accuracy on Jun-08 is the foundation

**Expansion wallets (14 candidates)** — unvalidated:
- Found purely by co-appearing in 2+ of the same markets as the cluster on Jun-10
- We haven't checked if their Jun-10 picks actually won
- They could be sharp co-travellers, or they could just be betting the same popular markets by coincidence
- Some may be betting opposite sides in the same market (e.g. Exp#7 on Bublik when cluster leans Perricard)

**In practice right now:**
- Core cluster signal = high confidence (proven hit rate)
- Expansion signal = directional hint only, needs validation
- When both agree = strongest signal (e.g. Mannarino — core cluster + multiple expansion wallets same side)
- When expansion-only (e.g. Perricard/Bublik) = treat it as noise until we validate their Jun-10 results

Want me to run the Jun-10 validation now? Pull the outcomes from those markets and score each expansion wallet's hit rate — that would tell us which ones are actually worth trusting.

---

## 👤 User  _2026-06-13 09:41_

aight new day tell me what my following wallets are on today show me the rundown

---

## 🤖 Claude  _2026-06-13 10:33_

Here's today's rundown:

---

## Today Jun-13 — Full Rundown

### Tier 1 — Core cluster + expansion aligned, big money

| Match | Pick | $ | Wallets |
|---|---|---|---|
| `wta-krejcik-linette` | **Barbora Krejcikova** | $58,414 | 178 cluster + 247 expand |
| `wta-krejcik-linette` | Magda Linette | $15,326 | (split, Krejcikova dominant) |
| `atp-shelton-shimabu` | **Ben Shelton** | $20,993 | 91 cluster + 135 expand |
| `wta-mcnally-tomljan` | **Ajla Tomljanovic** | $10,179 | 34 cluster + 33 expand |
| `atp-tarvet-romano` | **Oliver Tarvet** | $4,562 | 25 cluster + 71 expand |
| `atp-medvede-cilic` | **Daniil Medvedev** | $1,790 | 13 cluster + 12 expand |

### Tier 2 — Decent cluster presence, clear direction

| Match | Pick | $ | Wallets |
|---|---|---|---|
| `atp-sweeny-samuel` | **Toby Samuel** | $3,929 | 30 cluster + 130 expand |
| `atp-shevche-sachko` | **Alexander Shevchenko** | $2,536 | 15 cluster + 49 expand |
| `atp-blanc-fearnle` | **Darwin Blanch** | $1,875 | 30 cluster + 129 expand (close split though) |

### Tier 3 — Expansion only, cluster light

| Match | Pick | $ |
|---|---|---|
| `atp-bublik-fritz` | **Taylor Fritz** $1,151 vs Bublik $548 | Fritz favoured |
| `atp-sanchis-boyer` | **Boyer** $696 vs Sanchis $597 | near 50/50 |
| `atp-collign-dougaz` | **Collignon** $1,877 | expansion only |

---

**Top signals today:** Krejcikova ($58k, massive cluster consensus), Shelton ($21k), Tomljanovic ($10k all in same direction). Those three are the cluster's clear picks. Tarvet and Medvedev also solid cluster backing.

---

## 👤 User  _2026-06-13 10:59_

that barboa Krejcikova match is disgusting... linette sucks and Krejcikova is taking the piss. never seena worse match in my life. tell me if anything interesting happining in that market like someone keeps buying specific dips or switching positions or anything thats interesting/ proftiabl;e

---

## 🤖 Claude  _2026-06-13 11:04_

This market is wild. Here's what's actually happening:

---

## Krejcikova Market — Interesting Patterns

### Price narrative (match is live, Linette keeps breaking back)

```
Pre-match: ~0.720 flat
09:09      → spike to 0.770 (match starts)
09:17-09:22 → CRASH to 0.570 (Linette wins a set/game)
09:22-09:30 → recovers to 0.750
09:36-09:41 → SECOND DIP to 0.610 (Linette again)
09:45       → 114 trades in one minute, price jumps 0.815 (Krejcikova breaks)
09:49-09:53 → peaks 0.880
10:07-10:10 → THIRD DIP to 0.720
10:22       → FOURTH DIP to 0.750 (64 trades in one minute)
10:39-10:46 → FIFTH DIP to 0.700
11:01       → 0.710 (still going)
```

---

### The Dip Buyers

**All3#4 — the whale loading every dip in size:**
- `09:40` px=0.610 → $608 (hit the lowest print)
- `09:45` px=0.810 → **$2,445 + $1,595** (live recovery)
- `10:22` px=0.770 → $2,871 + $368
- `10:39` px=0.770 → **$8,098**
- `10:43` px=0.770 → **$8,373**
- `10:46` px=0.750 → **$3,802**
- Total ~$28k, and he's specifically targeting 0.75-0.77 as his reload level

**All3#1 — systematic dip buyer, never stops:**
- Bought at 0.590 (lowest), 0.630, 0.670 early
- `10:15` px=0.850 → **$5,856**
- `10:38` px=0.800 → **$7,549**
- `10:46` px=0.750 → **$1,988 + $672 + $284 x3**
- Every single dip, loads up. ~$40k total in this market today

**RANK16 — most consistent dip buyer, almost algorithmic:**
- Hits every dip: 0.640, 0.670, 0.610, 0.680, 0.640 again
- `10:13` px=0.820 → **$4,482** after dip
- `10:41` px=0.640 → **$1,378** (buys the exact same level twice hours apart)
- `10:55` px=0.830 → **$1,787**

---

### Most Interesting Single Trade

**BU Sharp#1 at 10:21 — dropped ~$13k in one minute:**
```
10:21  px=0.800  $4,456
10:21  px=0.800  $4,442
10:21  px=0.800  $2,616
10:21  px=0.800  $1,464
```
Waited all match, then hammered the exact 0.80 level in one burst. Looks like a programmatic trigger — "if price hits 0.80, buy $13k."

---

### Exp#12 — Playing both sides
Loading Linette at 0.27-0.33 during Krejcikova dips, then flipping back to Krejcikova at 0.85+. Small amounts but clearly scalping the volatility both ways.

---

**Bottom line:** The cluster knows Krejcikova wins. They're using every Linette game win as a free reload. All3#4, All3#1, and RANK16 are treating 0.75-0.77 as a buy zone. BU Sharp#1 had a pre-set 0.80 trigger and just fired $13k. The match is still live — price at 0.71 right now is another dip.

---

## 👤 User  _2026-06-13 11:07_

now im also interested in this one given my thesis; barobra takes s1, but despite being a zillion times better shes a mental midget and will throw the rest of the game away.... considering i wanted s1 but there was no liquidity... show me a winning wallet who was positioned for barbora but then cut her and left this market without sunk cost falacy

---

## 🤖 Claude  _2026-06-13 11:15_

Here's the clear breakdown:

---

## Who Executed Your Thesis

### PURE_FLIP_B — `0x360334761e7cebc80ebf0c01a5d70e0c735422ed`
Closest to exactly what you described:
```
09:25  Krejcikova  px=0.630  $63   ← bought the first dip
09:30  Krejcikova  px=0.760  $152  ← added as she recovered
--- SET 1 ENDS ~09:45 ---
10:25  Linette     px=0.170  $1    ← starts buying Linette
10:40  Linette     px=0.239  $24   ← adds
10:48  Linette     px=0.200  $20   ← adds
11:01  Linette     px=0.290  $60   ← still adding
```
Bought Krej during the dip at 0.63, let it ride through set 1, then cleanly flipped to Linette after. No more Krej buys. Zero sunk cost. Small amounts but **the exact thesis executed**.

---

### The $9k / $6k / $5.5k "Ghost" Wallets
These are different — not your thesis:
```
$9k: 09:01-09:02  Krejcikova  px=0.740  → never touched again
$6k: 04:51        Krejcikova  px=0.729  → never touched again  
$5k: 08:59        Krejcikova  px=0.740  → never touched again
```
Pre-match one-shot bets. They haven't bought the dips at 0.570, 0.610, 0.700 — nothing. Either they're pure outright holders, or they positioned for **set 1 specifically** at 0.74 and are sitting on it waiting to resolve. That's actually pretty interesting — $9k at 0.74 pre-match, price never came back below that for long after set 1. If they're set-1 tickets they're already looking good.

---

### `0x38f1...` — $1.6k, stopped at 09:37
```
09:32  Krejcikova  px=0.710  $789
09:37  Krejcikova  px=0.710  $789
← price immediately starts crashing to 0.610
← never traded again
```
Bought during the match, then went completely silent the moment the second dip started. Didn't flip to Linette, just walked. Could be discipline or could be they hit a loss limit.

---

**Bottom line for your thesis:** PURE_FLIP_B is the only one who cleanly executed it in the outright market. The $9k ghost is the most intriguing — if they're sitting on a pure set-1 position at 0.74, they're printing right now and will never touch it again. Worth tracking that wallet.

---

## 👤 User  _2026-06-13 13:31_

can you see anyone on the Lehecka  vs shelton market and can u link it

---

## 🤖 Claude  _2026-06-13 13:37_

No luck — that market isn't showing up in the API under any slug variation I can find. Tried every permutation for Jun-13 through Jun-16.

Most likely it just **hasn't been listed on Polymarket yet** — if Shelton's `atp-shelton-shimabu` match is still live today and Lehecka wrapped up his Tiafoe match yesterday, the QF/SF between them probably gets listed once both results are confirmed.

I can't give you a link because I can't find the slug — and I won't guess a Polymarket URL I'm not sure about. 

Keep an eye out — once it drops I can immediately check if any of the cluster wallets are positioning on it. Want me to set up a quick poll script to detect when it appears?

---
