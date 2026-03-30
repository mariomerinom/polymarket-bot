# Liquidity Probe — 2026-03-30 00:07 UTC

Side-by-side CLOB order book comparison for multi-asset expansion decision.

## Side-by-Side Comparison (YES token, buy side)

| Metric | BTC | SOL | ETH |
|--------|--------|--------|--------|
| Markets found | 5 | 5 | 5 |
| Volume | $532 | $67 | $69 |
| Market price (UP) | 49.5% | 49.5% | 50.5% |
| Best bid / ask | 0.620 / 0.630 | 0.730 / 0.760 | 0.750 / 0.760 |
| Spread % | 1.60% | 4.03% | 1.32% |
| Max bet @2% slip | $87 | $116 | $124 |
| Max bet @5% slip | $414 | $116 | $391 |
| Depth levels | 37 | 22 | 24 |
| $50 slippage | 1.03% | 0.00% | 0.43% |
| $200 slippage | 2.68% | 3.03% | 1.58% |
| $500 slippage | 4.19% | 7.96% | 3.00% |

## Go/No-Go Assessment

- **BTC:** ✅ **GO** — max_bet_2pct $87 >= $50 threshold
- **SOL:** ✅ **GO** — max_bet_2pct $116 >= $50 threshold
- **ETH:** ✅ **GO** — max_bet_2pct $124 >= $50 threshold

## Additional Markets Sampled

### Bitcoin

| Market | Spread % | Max Bet @2% | Depth |
|--------|----------|-------------|-------|
| Bitcoin Up or Down - March 29, 8:10PM-8:15PM ET | 2.02% | $214 | 50 |
| Bitcoin Up or Down - March 29, 8:00PM-8:15PM ET | 6.06% | $3 | 83 |

### Solana

| Market | Spread % | Max Bet @2% | Depth |
|--------|----------|-------------|-------|
| Solana Up or Down - March 29, 8:10PM-8:15PM ET | 1.98% | $20 | 49 |
| Solana Up or Down - March 29, 8:00PM-8:15PM ET | 3.28% | $2 | 69 |

### Ethereum

| Market | Spread % | Max Bet @2% | Depth |
|--------|----------|-------------|-------|
| Ethereum Up or Down - March 29, 8:10PM-8:15PM ET | 3.92% | $16 | 48 |
| Ethereum Up or Down - March 29, 8:00PM-8:15PM ET | 2.53% | $12 | 60 |

## Raw Order Book Snapshots

<details>
<summary>Click to expand</summary>

```json
{
  "BTC": {
    "yes_book": {
      "num_bids": 62,
      "num_asks": 37,
      "top_5_bids": [
        {
          "price": "0.62",
          "size": "89.46"
        },
        {
          "price": "0.61",
          "size": "56.78"
        },
        {
          "price": "0.6",
          "size": "201.45"
        },
        {
          "price": "0.59",
          "size": "293"
        },
        {
          "price": "0.58",
          "size": "373.99"
        }
      ],
      "top_5_asks": [
        {
          "price": "0.63",
          "size": "27.77"
        },
        {
          "price": "0.64",
          "size": "108"
        },
        {
          "price": "0.65",
          "size": "106"
        },
        {
          "price": "0.66",
          "size": "391"
        },
        {
          "price": "0.67",
          "size": "684.86"
        }
      ]
    },
    "no_book": {
      "num_bids": 37,
      "num_asks": 62,
      "top_5_bids": [
        {
          "price": "0.37",
          "size": "55.77"
        },
        {
          "price": "0.36",
          "size": "116"
        },
        {
          "price": "0.35",
          "size": "116"
        },
        {
          "price": "0.34",
          "size": "399"
        },
        {
          "price": "0.33",
          "size": "710.86"
        }
      ],
      "top_5_asks": [
        {
          "price": "0.38",
          "size": "54.46"
        },
        {
          "price": "0.39",
          "size": "72.97"
        },
        {
          "price": "0.4",
          "size": "204.45"
        },
        {
          "price": "0.41",
          "size": "293"
        },
        {
          "price": "0.42",
          "size": "373.99"
        }
      ]
    }
  },
  "SOL": {
    "yes_book": {
      "num_bids": 72,
      "num_asks": 22,
      "top_5_bids": [
        {
          "price": "0.73",
          "size": "22"
        },
        {
          "price": "0.72",
          "size": "40"
        },
        {
          "price": "0.71",
          "size": "25.07"
        },
        {
          "price": "0.7",
          "size": "38"
        },
        {
          "price": "0.69",
          "size": "33"
        }
      ],
      "top_5_asks": [
        {
          "price": "0.76",
          "size": "88.46"
        },
        {
          "price": "0.77",
          "size": "63"
        },
        {
          "price": "0.8",
          "size": "30.2"
        },
        {
          "price": "0.81",
          "size": "39.89"
        },
        {
          "price": "0.82",
          "size": "45.6"
        }
      ]
    },
    "no_book": {
      "num_bids": 23,
      "num_asks": 74,
      "top_5_bids": [
        {
          "price": "0.24",
          "size": "81.46"
        },
        {
          "price": "0.23",
          "size": "37"
        },
        {
          "price": "0.21",
          "size": "15.7"
        },
        {
          "price": "0.2",
          "size": "16.2"
        },
        {
          "price": "0.19",
          "size": "16.89"
        }
      ],
      "top_5_asks": [
        {
          "price": "0.26",
          "size": "22"
        },
        {
          "price": "0.27",
          "size": "40"
        },
        {
          "price": "0.28",
          "size": "33"
        },
        {
          "price": "0.29",
          "size": "25.07"
        },
        {
          "price": "0.3",
          "size": "5"
        }
      ]
    }
  },
  "ETH": {
    "yes_book": {
      "num_bids": 75,
      "num_asks": 24,
      "top_5_bids": [
        {
          "price": "0.75",
          "size": "7"
        },
        {
          "price": "0.74",
          "size": "87"
        },
        {
          "price": "0.73",
          "size": "424"
        },
        {
          "price": "0.72",
          "size": "255"
        },
        {
          "price": "0.71",
          "size": "86.91"
        }
      ],
      "top_5_asks": [
        {
          "price": "0.76",
          "size": "44"
        },
        {
          "price": "0.77",
          "size": "118"
        },
        {
          "price": "0.78",
          "size": "245"
        },
        {
          "price": "0.79",
          "size": "95.13"
        },
        {
          "price": "0.8",
          "size": "121.2"
        }
      ]
    },
    "no_book": {
      "num_bids": 24,
      "num_asks": 75,
      "top_5_bids": [
        {
          "price": "0.24",
          "size": "31"
        },
        {
          "price": "0.23",
          "size": "185"
        },
        {
          "price": "0.22",
          "size": "258"
        },
        {
          "price": "0.21",
          "size": "95.13"
        },
        {
          "price": "0.2",
          "size": "121.2"
        }
      ],
      "top_5_asks": [
        {
          "price": "0.25",
          "size": "58.45"
        },
        {
          "price": "0.26",
          "size": "388"
        },
        {
          "price": "0.27",
          "size": "139"
        },
        {
          "price": "0.28",
          "size": "188"
        },
        {
          "price": "0.29",
          "size": "86.91"
        }
      ]
    }
  }
}
```

</details>

---
*Generated by `scripts/liquidity_probe.py` at 2026-03-30 00:07 UTC*