# Bybit alternative signals — backtest on 6mo BTCUSDT

After Phase 2 proved streak momentum (ride & fade) is
dead on Bybit 5m perps, three alternative signal
families were implemented and backtested on the same
cached 6-month 5m CSV.

Bet size: $0. P&L includes round-trip fees via `bybit_trade._compute_pnl`.

## Headline results
| Signal | N | WR | P&L | Avg/trade |
|--------|--:|---:|----:|----------:|
| volbreakout | 566 | 24.38% | $-294.20 | $-0.520 |
| vwap_mr_z2p0_h48_s1p0 | 2011 | 36.65% | $-854.17 | $-0.425 |
| vwap_mr_z2p0_h48_s1p5 | 1732 | 42.21% | $-733.65 | $-0.424 |
| vwap_mr_z2p0_h48_s2p0 | 1520 | 46.51% | $-613.99 | $-0.404 |
| vwap_mr_z2p0_h48_s3p0 | 1323 | 51.40% | $-568.19 | $-0.429 |
| vwap_mr_z2p0_h48_snone | 997 | 58.38% | $-523.47 | $-0.525 |
| vwap_mr_z2p0_h96_s1p0 | 1846 | 35.97% | $-815.41 | $-0.442 |
| vwap_mr_z2p0_h96_s1p5 | 1553 | 42.69% | $-634.99 | $-0.409 |
| vwap_mr_z2p0_h96_s2p0 | 1331 | 48.16% | $-523.35 | $-0.393 |
| vwap_mr_z2p0_h96_s3p0 | 1139 | 54.43% | $-458.98 | $-0.403 |
| vwap_mr_z2p0_h96_snone | 753 | 67.73% | $-337.00 | $-0.448 |
| vwap_mr_z2p5_h48_s1p0 | 1017 | 32.74% | $-504.08 | $-0.496 |
| vwap_mr_z2p5_h48_s1p5 | 918 | 38.67% | $-438.25 | $-0.477 |
| vwap_mr_z2p5_h48_s2p0 | 843 | 43.65% | $-344.23 | $-0.408 |
| vwap_mr_z2p5_h48_s3p0 | 753 | 48.74% | $-303.95 | $-0.404 |
| vwap_mr_z2p5_h48_snone | 607 | 54.86% | $-431.83 | $-0.711 |
| vwap_mr_z2p5_h96_s1p0 | 989 | 32.76% | $-502.24 | $-0.508 |
| vwap_mr_z2p5_h96_s1p5 | 885 | 39.10% | $-413.63 | $-0.467 |
| vwap_mr_z2p5_h96_s2p0 | 807 | 44.73% | $-348.83 | $-0.432 |
| vwap_mr_z2p5_h96_s3p0 | 696 | 51.87% | $-229.09 | $-0.329 |
| vwap_mr_z2p5_h96_snone | 513 | 65.50% | $-308.79 | $-0.602 |
| vwap_mr_z3p0_h48_s1p0 | 352 | 29.83% | $-115.84 | $-0.329 |
| vwap_mr_z3p0_h48_s1p5 | 331 | 36.25% | $-101.42 | $-0.306 |
| vwap_mr_z3p0_h48_s2p0 | 319 | 42.01% | $-37.32 | $-0.117 |
| vwap_mr_z3p0_h48_s3p0 | 293 | 47.44% | $-37.89 | $-0.129 |
| vwap_mr_z3p0_h48_snone | 268 | 52.61% | $-108.70 | $-0.406 |
| vwap_mr_z3p0_h96_s1p0 | 351 | 30.20% | $-106.15 | $-0.302 |
| vwap_mr_z3p0_h96_s1p5 | 330 | 36.67% | $-93.22 | $-0.282 |
| vwap_mr_z3p0_h96_s2p0 | 318 | 42.77% | $-17.36 | $-0.055 |
| vwap_mr_z3p0_h96_s3p0 | 288 | 48.96% | $-22.37 | $-0.078 |
| vwap_mr_z3p0_h96_snone | 243 | 60.91% | $-97.81 | $-0.402 |
| xexch_2 | 710 | 19.30% | $-320.67 | $-0.452 |
| xexch_3 | 537 | 18.81% | $-252.92 | $-0.471 |

## Exit-reason breakdown
### volbreakout
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| time_ceiling | 566 | 24.38% | $-294.20 |

### vwap_mr_z2p0_h48_s1p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 619 | 99.35% | $+1649.69 |
| stop_loss | 1204 | 0.00% | $-2633.48 |
| time_ceiling | 188 | 64.89% | $+129.62 |

### vwap_mr_z2p0_h48_s1p5
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 613 | 99.51% | $+1621.39 |
| stop_loss | 904 | 0.00% | $-2444.13 |
| time_ceiling | 215 | 56.28% | $+89.09 |

### vwap_mr_z2p0_h48_s2p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 596 | 99.50% | $+1550.46 |
| stop_loss | 668 | 0.00% | $-2150.77 |
| time_ceiling | 256 | 44.53% | $-13.68 |

### vwap_mr_z2p0_h48_s3p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 572 | 99.48% | $+1401.95 |
| stop_loss | 433 | 0.00% | $-1783.62 |
| time_ceiling | 318 | 34.91% | $-186.51 |

### vwap_mr_z2p0_h48_snone
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 518 | 99.23% | $+1109.15 |
| time_ceiling | 479 | 14.20% | $-1632.62 |

### vwap_mr_z2p0_h96_s1p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 619 | 99.68% | $+1738.86 |
| stop_loss | 1162 | 0.00% | $-2622.30 |
| time_ceiling | 65 | 72.31% | $+68.03 |

### vwap_mr_z2p0_h96_s1p5
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 616 | 99.68% | $+1739.96 |
| stop_loss | 865 | 0.00% | $-2426.45 |
| time_ceiling | 72 | 68.06% | $+51.50 |

### vwap_mr_z2p0_h96_s2p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 595 | 99.66% | $+1659.16 |
| stop_loss | 643 | 0.00% | $-2186.49 |
| time_ceiling | 93 | 51.61% | $+3.98 |

### vwap_mr_z2p0_h96_s3p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 576 | 99.65% | $+1534.03 |
| stop_loss | 437 | 0.00% | $-1889.20 |
| time_ceiling | 126 | 36.51% | $-103.82 |

### vwap_mr_z2p0_h96_snone
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 488 | 99.18% | $+1033.67 |
| time_ceiling | 265 | 9.81% | $-1370.67 |

### vwap_mr_z2p5_h48_s1p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 283 | 100.00% | $+873.29 |
| stop_loss | 652 | 0.00% | $-1431.27 |
| time_ceiling | 82 | 60.98% | $+53.91 |

### vwap_mr_z2p5_h48_s1p5
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 296 | 100.00% | $+892.14 |
| stop_loss | 512 | 0.00% | $-1358.53 |
| time_ceiling | 110 | 53.64% | $+28.14 |

### vwap_mr_z2p5_h48_s2p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 307 | 100.00% | $+916.28 |
| stop_loss | 397 | 0.00% | $-1252.97 |
| time_ceiling | 139 | 43.88% | $-7.54 |

### vwap_mr_z2p5_h48_s3p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 298 | 100.00% | $+864.49 |
| stop_loss | 277 | 0.00% | $-1103.37 |
| time_ceiling | 178 | 38.76% | $-65.07 |

### vwap_mr_z2p5_h48_snone
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 277 | 100.00% | $+686.81 |
| time_ceiling | 330 | 16.97% | $-1118.63 |

### vwap_mr_z2p5_h96_s1p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 304 | 100.00% | $+940.32 |
| stop_loss | 659 | 0.00% | $-1465.83 |
| time_ceiling | 26 | 76.92% | $+23.27 |

### vwap_mr_z2p5_h96_s1p5
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 324 | 100.00% | $+1004.93 |
| stop_loss | 527 | 0.00% | $-1438.15 |
| time_ceiling | 34 | 64.71% | $+19.59 |

### vwap_mr_z2p5_h96_s2p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 337 | 100.00% | $+1017.97 |
| stop_loss | 421 | 0.00% | $-1373.97 |
| time_ceiling | 49 | 48.98% | $+7.17 |

### vwap_mr_z2p5_h96_s3p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 329 | 100.00% | $+992.19 |
| stop_loss | 287 | 0.00% | $-1163.90 |
| time_ceiling | 80 | 40.00% | $-57.38 |

### vwap_mr_z2p5_h96_snone
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 309 | 100.00% | $+765.06 |
| time_ceiling | 204 | 13.24% | $-1073.85 |

### vwap_mr_z3p0_h48_s1p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 87 | 100.00% | $+358.62 |
| stop_loss | 235 | 0.00% | $-507.07 |
| time_ceiling | 30 | 60.00% | $+32.61 |

### vwap_mr_z3p0_h48_s1p5
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 94 | 100.00% | $+380.39 |
| stop_loss | 191 | 0.00% | $-509.45 |
| time_ceiling | 46 | 56.52% | $+27.65 |

### vwap_mr_z3p0_h48_s2p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 102 | 100.00% | $+412.15 |
| stop_loss | 153 | 0.00% | $-470.45 |
| time_ceiling | 64 | 50.00% | $+20.98 |

### vwap_mr_z3p0_h48_s3p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 105 | 100.00% | $+403.74 |
| stop_loss | 114 | 0.00% | $-441.78 |
| time_ceiling | 74 | 45.95% | $+0.15 |

### vwap_mr_z3p0_h48_snone
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 108 | 100.00% | $+405.22 |
| time_ceiling | 160 | 20.62% | $-513.93 |

### vwap_mr_z3p0_h96_s1p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 98 | 100.00% | $+402.83 |
| stop_loss | 242 | 0.00% | $-524.62 |
| time_ceiling | 11 | 72.73% | $+15.64 |

### vwap_mr_z3p0_h96_s1p5
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 110 | 100.00% | $+440.69 |
| stop_loss | 204 | 0.00% | $-549.87 |
| time_ceiling | 16 | 68.75% | $+15.96 |

### vwap_mr_z3p0_h96_s2p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 122 | 100.00% | $+497.34 |
| stop_loss | 171 | 0.00% | $-523.78 |
| time_ceiling | 25 | 56.00% | $+9.08 |

### vwap_mr_z3p0_h96_s3p0
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 126 | 100.00% | $+493.19 |
| stop_loss | 133 | 0.00% | $-517.91 |
| time_ceiling | 29 | 51.72% | $+2.35 |

### vwap_mr_z3p0_h96_snone
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| mean_revert | 131 | 100.00% | $+434.61 |
| time_ceiling | 112 | 15.18% | $-532.42 |

### xexch_2
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| time_ceiling | 710 | 19.30% | $-320.67 |

### xexch_3
| Exit reason | N | WR | P&L |
|---|--:|---:|---:|
| time_ceiling | 537 | 18.81% | $-252.92 |

## Verdict
⚠️ **vwap_mr_z2p0_h48_snone** marginal (58.4% on N=997). Not worth committing to alone.
⚠️ **vwap_mr_z2p0_h96_s3p0** marginal (54.4% on N=1139). Not worth committing to alone.
⚠️ **vwap_mr_z2p0_h96_snone** marginal (67.7% on N=753). Not worth committing to alone.
⚠️ **vwap_mr_z2p5_h48_snone** marginal (54.9% on N=607). Not worth committing to alone.
⚠️ **vwap_mr_z2p5_h96_snone** marginal (65.5% on N=513). Not worth committing to alone.
⚠️ **vwap_mr_z3p0_h48_snone** marginal (52.6% on N=268). Not worth committing to alone.
⚠️ **vwap_mr_z3p0_h96_snone** marginal (60.9% on N=243). Not worth committing to alone.

❌ No alternative signal clears 55% WR. The momentum family was dead; these three families are also dead on this venue at 5m cadence after fees. Options: different bar size, different venue, or fundamentally different data (order book, open interest, funding).

