# UI audit: desk-phase3 @ d29c399

`python web/scripts/check/shot.py audit-all` · 2026-11-27 15:16 – 15:22 (three runs, one per width, each with a fresh Chrome) · llm_mode `fake` · dense retrieval `False` · Four Ledgers `on` · sample `migrant_text` · Chrome/158.0.8127.88 · http://localhost:3001

Rules: `web/scripts/check/audit_js.py`. Bytes are a first visit (cache off), since the page was opened, decoded and on the wire. axe-core: WCAG 2.0/2.1/2.2 A + AA tags. "Running" is the photo sample paused at its salary check. Δ is the change from `accuracy`.

| state | width | theme | axe | Δ | axe nodes | targets <24 | Δ | <44 (phone) | inline links <24 | text <14 | Δ | Latin <14 | Δ | Bangla <16 | Δ | Bangla <14 | sideways | height | Δ | fonts KB | Δ | fonts KB wire | CSS KB | Δ | CSS KB wire |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Citizen · home | 390 | light | 0 |  | 0 | 2 | -1 | 3 | 0 | 0 |  | 0 |  | 0 | -9 | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · salary check (photo OCR confirm) | 390 | light | 0 |  | 0 | 0 |  | 0 | 0 | 0 |  | 0 |  | 1 |  | 0 |  | 923 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · promise form | 390 | light | 0 |  | 0 | 0 |  | 0 | 0 | 0 | -5 | 0 | -1 | 14 |  | 0 |  | 4,056 | +4 | 495 |  | 500 | 135 | +74 | 27 |
| Citizen · result (bn) | 390 | light | 0 |  | 0 | 0 |  | 0 | 0 | 0 | -5 | 0 | -1 | 24 |  | 0 |  | 4,264 | +4 | 495 |  | 500 | 135 | +74 | 27 |
| Citizen · result (en) | 390 | light | 0 |  | 0 | 0 |  | 0 | 0 | 5 |  | 5 |  | 1 | -1 | 0 |  | 4,415 |  | 495 |  | 500 | 135 | +1 | 27 |
| Citizen · result gone | 390 | light | 0 |  | 0 | 0 |  | 0 | 0 | 0 |  | 0 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 63 | +2 | 13 |
| Citizen · upload error | 390 | light | 0 |  | 0 | 1 |  | 1 | 0 | 0 |  | 0 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · start | 390 | light | 0 |  | 0 | 0 |  | 4 | 0 | 15 |  | 12 |  | 6 |  | 0 |  | 3,042 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · running | 390 | light | 0 |  | 0 | 1 |  | 5 | 0 | 11 |  | 8 |  | 0 |  | 0 |  | 1,105 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · Case Desk (bn) | 390 | light | 0 |  | 0 | 0 | -2 | 9 | 0 | 7 | -118 | 4 | -1 | 157 | -34 | 0 |  | 5,797 | +1,140 | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Case Desk (en) | 390 | light | 0 |  | 0 | 0 |  | 9 | 0 | 105 | -20 | 102 | -20 | 3 |  | 0 |  | 5,809 | +753 | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Memo | 390 | light | 0 |  | 0 | 1 |  | 34 | 0 | 155 |  | 120 |  | 12 |  | 1 |  | 10,443 |  | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Council after a question | 390 | light | 0 |  | 0 | 0 |  | 14 | 0 | 64 |  | 60 |  | 1 |  | 1 |  | 3,016 |  | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Checks | 390 | light | 0 |  | 0 | 1 |  | 30 | 0 | 333 |  | 261 |  | 10 |  | 8 |  | 13,501 |  | 495 |  | 500 | 135 | +1 | 27 |
| /docs | 390 | light | 0 |  | 0 | 3 |  | 8 | 1 | 213 | +1 | 167 | +1 | 0 |  | 0 |  | 11,742 |  | 467 |  | 472 | 143 | +1 | 29 |
| /login | 390 | light | 0 |  | 0 | 1 |  | 5 | 0 | 2 |  | 2 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · home | 820 | light | 0 |  | 0 | 2 | -1 |  | 0 | 0 |  | 0 |  | 0 | -9 | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · salary check (photo OCR confirm) | 820 | light | 0 |  | 0 | 0 |  |  | 0 | 0 |  | 0 |  | 1 |  | 0 |  | 923 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · promise form | 820 | light | 0 |  | 0 | 0 |  |  | 0 | 0 | -5 | 0 | -1 | 14 |  | 0 |  | 3,917 | +4 | 495 |  | 500 | 135 | +74 | 27 |
| Citizen · result (bn) | 820 | light | 0 |  | 0 | 0 |  |  | 0 | 0 | -5 | 0 | -1 | 24 |  | 0 |  | 4,156 | +4 | 495 |  | 500 | 135 | +74 | 27 |
| Citizen · result (en) | 820 | light | 0 |  | 0 | 0 |  |  | 0 | 5 |  | 5 |  | 1 | -1 | 0 |  | 4,202 |  | 495 |  | 500 | 135 | +1 | 27 |
| Citizen · result gone | 820 | light | 0 |  | 0 | 0 |  |  | 0 | 0 |  | 0 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 63 | +2 | 13 |
| Citizen · upload error | 820 | light | 0 |  | 0 | 1 |  |  | 0 | 0 |  | 0 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · start | 820 | light | 0 |  | 0 | 0 |  |  | 0 | 15 |  | 12 |  | 6 |  | 0 |  | 1,906 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · running | 820 | light | 0 |  | 0 | 1 |  |  | 0 | 11 |  | 8 |  | 0 |  | 0 |  | 916 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · Case Desk (bn) | 820 | light | 0 |  | 0 | 2 |  |  | 0 | 9 | -118 | 4 | -1 | 157 | -34 | 0 |  | 4,521 | +268 | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Case Desk (en) | 820 | light | 0 |  | 0 | 2 |  |  | 0 | 107 | -20 | 102 | -20 | 3 |  | 0 |  | 4,457 | +99 | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Memo | 820 | light | 0 |  | 0 | 1 |  |  | 0 | 157 |  | 120 |  | 12 |  | 1 |  | 6,864 |  | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Council after a question | 820 | light | 0 |  | 0 | 0 |  |  | 0 | 81 |  | 72 |  | 1 |  | 1 |  | 2,242 |  | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Checks | 820 | light | 0 |  | 0 | 23 |  |  | 0 | 335 |  | 261 |  | 10 |  | 8 |  | 7,470 |  | 495 |  | 500 | 135 | +1 | 27 |
| /docs | 820 | light | 0 |  | 0 | 3 |  |  | 1 | 213 | +1 | 167 | +1 | 0 |  | 0 |  | 7,372 |  | 467 |  | 472 | 143 | +1 | 29 |
| /login | 820 | light | 0 |  | 0 | 1 |  |  | 0 | 2 |  | 2 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · home | 1440 | light | 0 |  | 0 | 2 | -1 |  | 0 | 0 |  | 0 |  | 0 | -9 | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · salary check (photo OCR confirm) | 1440 | light | 0 |  | 0 | 0 |  |  | 0 | 0 |  | 0 |  | 1 |  | 0 |  | 923 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · promise form | 1440 | light | 0 |  | 0 | 0 |  |  | 0 | 0 | -5 | 0 | -1 | 14 |  | 0 |  | 3,917 | +4 | 495 |  | 500 | 135 | +74 | 27 |
| Citizen · result (bn) | 1440 | light | 0 |  | 0 | 0 |  |  | 0 | 0 | -5 | 0 | -1 | 24 |  | 0 |  | 4,156 | +4 | 495 |  | 500 | 135 | +74 | 27 |
| Citizen · result (en) | 1440 | light | 0 |  | 0 | 0 |  |  | 0 | 5 |  | 5 |  | 1 | -1 | 0 |  | 4,202 |  | 495 |  | 500 | 135 | +1 | 27 |
| Citizen · result gone | 1440 | light | 0 |  | 0 | 0 |  |  | 0 | 0 |  | 0 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 63 | +2 | 13 |
| Citizen · upload error | 1440 | light | 0 |  | 0 | 1 |  |  | 0 | 0 |  | 0 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · start | 1440 | light | 0 |  | 0 | 0 |  |  | 0 | 15 |  | 12 |  | 6 |  | 0 |  | 1,687 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · running | 1440 | light | 0 |  | 0 | 1 |  |  | 0 | 11 |  | 8 |  | 0 |  | 0 |  | 916 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · Case Desk (bn) | 1440 | light | 0 |  | 0 | 0 | -2 |  | 0 | 9 | -118 | 4 | -1 | 160 | -34 | 0 |  | 2,687 | +160 | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Case Desk (en) | 1440 | light | 0 |  | 0 | 1 |  |  | 0 | 107 | -20 | 102 | -20 | 5 |  | 0 |  | 2,648 | +18 | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Memo | 1440 | light | 0 |  | 0 | 1 |  |  | 0 | 180 |  | 132 |  | 12 |  | 1 |  | 6,548 |  | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Council after a question | 1440 | light | 0 |  | 0 | 0 |  |  | 0 | 93 |  | 84 |  | 1 |  | 1 |  | 1,622 |  | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Checks | 1440 | light | 0 |  | 0 | 27 |  |  | 0 | 335 |  | 261 |  | 10 |  | 8 |  | 6,289 |  | 495 |  | 500 | 135 | +1 | 27 |
| /docs | 1440 | light | 0 |  | 0 | 3 |  |  | 1 | 213 | +1 | 167 | +1 | 0 |  | 0 |  | 6,300 |  | 467 |  | 472 | 143 | +1 | 29 |
| /login | 1440 | light | 0 |  | 0 | 1 |  |  | 0 | 2 |  | 2 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · home | 390 | dark | 0 |  | 0 | 2 | -1 | 3 | 0 | 0 |  | 0 |  | 0 | -9 | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · salary check (photo OCR confirm) | 390 | dark | 0 |  | 0 | 0 |  | 0 | 0 | 0 |  | 0 |  | 1 |  | 0 |  | 923 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · promise form | 390 | dark | 0 |  | 0 | 0 |  | 0 | 0 | 0 | -5 | 0 | -1 | 14 |  | 0 |  | 4,056 | +4 | 495 |  | 500 | 135 | +74 | 27 |
| Citizen · result (bn) | 390 | dark | 0 |  | 0 | 0 |  | 0 | 0 | 0 | -5 | 0 | -1 | 24 |  | 0 |  | 4,264 | +4 | 495 |  | 500 | 135 | +74 | 27 |
| Citizen · result (en) | 390 | dark | 0 |  | 0 | 0 |  | 0 | 0 | 5 |  | 5 |  | 1 | -1 | 0 |  | 4,415 |  | 495 |  | 500 | 135 | +1 | 27 |
| Citizen · result gone | 390 | dark | 0 |  | 0 | 0 |  | 0 | 0 | 0 |  | 0 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 63 | +2 | 13 |
| Citizen · upload error | 390 | dark | 0 |  | 0 | 1 |  | 1 | 0 | 0 |  | 0 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · start | 390 | dark | 0 |  | 0 | 0 |  | 4 | 0 | 15 |  | 12 |  | 6 |  | 0 |  | 3,042 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · running | 390 | dark | 0 |  | 0 | 1 |  | 5 | 0 | 11 |  | 8 |  | 0 |  | 0 |  | 1,105 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · Case Desk (bn) | 390 | dark | 0 |  | 0 | 0 | -2 | 9 | 0 | 7 | -118 | 4 | -1 | 157 | -34 | 0 |  | 5,797 | +1,140 | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Case Desk (en) | 390 | dark | 0 |  | 0 | 0 |  | 9 | 0 | 105 | -20 | 102 | -20 | 3 |  | 0 |  | 5,809 | +753 | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Memo | 390 | dark | 0 |  | 0 | 1 |  | 34 | 0 | 155 |  | 120 |  | 12 |  | 1 |  | 10,443 |  | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Council after a question | 390 | dark | 0 |  | 0 | 0 |  | 14 | 0 | 64 |  | 60 |  | 1 |  | 1 |  | 3,016 |  | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Checks | 390 | dark | 0 |  | 0 | 1 |  | 30 | 0 | 333 |  | 261 |  | 10 |  | 8 |  | 13,501 |  | 495 |  | 500 | 135 | +1 | 27 |
| /docs | 390 | dark | 0 |  | 0 | 3 |  | 8 | 1 | 213 | +1 | 167 | +1 | 0 |  | 0 |  | 11,742 | +21 | 467 |  | 472 | 143 | +1 | 29 |
| /login | 390 | dark | 0 |  | 0 | 1 |  | 5 | 0 | 2 |  | 2 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · home | 820 | dark | 0 |  | 0 | 2 | -1 |  | 0 | 0 |  | 0 |  | 0 | -9 | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · salary check (photo OCR confirm) | 820 | dark | 0 |  | 0 | 0 |  |  | 0 | 0 |  | 0 |  | 1 |  | 0 |  | 923 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · promise form | 820 | dark | 0 |  | 0 | 0 |  |  | 0 | 0 | -5 | 0 | -1 | 14 |  | 0 |  | 3,917 | +4 | 495 |  | 500 | 135 | +74 | 27 |
| Citizen · result (bn) | 820 | dark | 0 |  | 0 | 0 |  |  | 0 | 0 | -5 | 0 | -1 | 24 |  | 0 |  | 4,156 | +4 | 495 |  | 500 | 135 | +74 | 27 |
| Citizen · result (en) | 820 | dark | 0 |  | 0 | 0 |  |  | 0 | 5 |  | 5 |  | 1 | -1 | 0 |  | 4,202 |  | 495 |  | 500 | 135 | +1 | 27 |
| Citizen · result gone | 820 | dark | 0 |  | 0 | 0 |  |  | 0 | 0 |  | 0 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 63 | +2 | 13 |
| Citizen · upload error | 820 | dark | 0 |  | 0 | 1 |  |  | 0 | 0 |  | 0 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · start | 820 | dark | 0 |  | 0 | 0 |  |  | 0 | 15 |  | 12 |  | 6 |  | 0 |  | 1,906 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · running | 820 | dark | 0 |  | 0 | 1 |  |  | 0 | 11 |  | 8 |  | 0 |  | 0 |  | 916 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · Case Desk (bn) | 820 | dark | 0 |  | 0 | 2 |  |  | 0 | 9 | -118 | 4 | -1 | 157 | -34 | 0 |  | 4,521 | +268 | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Case Desk (en) | 820 | dark | 0 |  | 0 | 2 |  |  | 0 | 107 | -20 | 102 | -20 | 3 |  | 0 |  | 4,457 | +99 | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Memo | 820 | dark | 0 |  | 0 | 1 |  |  | 0 | 157 |  | 120 |  | 12 |  | 1 |  | 6,864 |  | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Council after a question | 820 | dark | 0 |  | 0 | 0 |  |  | 0 | 81 |  | 72 |  | 1 |  | 1 |  | 2,242 |  | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Checks | 820 | dark | 0 |  | 0 | 23 |  |  | 0 | 335 |  | 261 |  | 10 |  | 8 |  | 7,470 |  | 495 |  | 500 | 135 | +1 | 27 |
| /docs | 820 | dark | 0 |  | 0 | 3 |  |  | 1 | 213 | +1 | 167 | +1 | 0 |  | 0 |  | 7,372 |  | 467 |  | 472 | 143 | +1 | 29 |
| /login | 820 | dark | 0 |  | 0 | 1 |  |  | 0 | 2 |  | 2 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · home | 1440 | dark | 0 |  | 0 | 2 | -1 |  | 0 | 0 |  | 0 |  | 0 | -9 | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · salary check (photo OCR confirm) | 1440 | dark | 0 |  | 0 | 0 |  |  | 0 | 0 |  | 0 |  | 1 |  | 0 |  | 923 |  | 467 |  | 472 | 135 | +1 | 27 |
| Citizen · promise form | 1440 | dark | 0 |  | 0 | 0 |  |  | 0 | 0 | -5 | 0 | -1 | 14 |  | 0 |  | 3,917 | +4 | 495 |  | 500 | 135 | +74 | 27 |
| Citizen · result (bn) | 1440 | dark | 0 |  | 0 | 0 |  |  | 0 | 0 | -5 | 0 | -1 | 24 |  | 0 |  | 4,156 | +4 | 495 |  | 500 | 135 | +74 | 27 |
| Citizen · result (en) | 1440 | dark | 0 |  | 0 | 0 |  |  | 0 | 5 |  | 5 |  | 1 | -1 | 0 |  | 4,202 |  | 495 |  | 500 | 135 | +1 | 27 |
| Citizen · result gone | 1440 | dark | 0 |  | 0 | 0 |  |  | 0 | 0 |  | 0 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 63 | +2 | 13 |
| Citizen · upload error | 1440 | dark | 0 |  | 0 | 1 |  |  | 0 | 0 |  | 0 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · start | 1440 | dark | 0 |  | 0 | 0 |  |  | 0 | 15 |  | 12 |  | 6 |  | 0 |  | 1,687 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · running | 1440 | dark | 0 |  | 0 | 1 |  |  | 0 | 11 |  | 8 |  | 0 |  | 0 |  | 916 |  | 467 |  | 472 | 135 | +1 | 27 |
| Counsel · Case Desk (bn) | 1440 | dark | 0 |  | 0 | 0 | -2 |  | 0 | 9 | -118 | 4 | -1 | 160 | -34 | 0 |  | 2,687 | +160 | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Case Desk (en) | 1440 | dark | 0 |  | 0 | 1 |  |  | 0 | 107 | -20 | 102 | -20 | 5 |  | 0 |  | 2,648 | +18 | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Memo | 1440 | dark | 0 |  | 0 | 1 |  |  | 0 | 180 |  | 132 |  | 12 |  | 1 |  | 6,548 |  | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Council after a question | 1440 | dark | 0 |  | 0 | 0 |  |  | 0 | 93 |  | 84 |  | 1 |  | 1 |  | 1,622 |  | 495 |  | 500 | 135 | +1 | 27 |
| Counsel · Checks | 1440 | dark | 0 |  | 0 | 27 |  |  | 0 | 335 |  | 261 |  | 10 |  | 8 |  | 6,289 |  | 495 |  | 500 | 135 | +1 | 27 |
| /docs | 1440 | dark | 0 |  | 0 | 3 |  |  | 1 | 213 | +1 | 167 | +1 | 0 |  | 0 |  | 6,300 |  | 467 |  | 472 | 143 | +1 | 29 |
| /login | 1440 | dark | 0 |  | 0 | 1 |  |  | 0 | 2 |  | 2 |  | 0 |  | 0 |  | 900 |  | 467 |  | 472 | 135 | +1 | 27 |

## axe violations

None.

## Examples (widest light run of each state)

### Citizen · home · 1440
Reached: আপনার চুক্তিপত্র কি নিরাপদ?
- Latin sizes: 14px×1, 16px×2
- Bangla sizes: 16px×18, 20px×3, 28px×2
- small target: input.visuallyHidden 1×1 ""
- small target: input.visuallyHidden 1×1 ""
- CSS: 11u5x8lnvjk82.css (73 KB), 1ybx2fb9khdrs.css (45 KB), 25g_1sup70ux9.css (13 KB), 0kfz0zyaojuy2.css (5 KB)
- fonts: 11 files: 187, 50, 47, 39, 39, 39, 35, 8, 8, 8, 8 KB

### Citizen · salary check (photo OCR confirm) · 1440
Reached: এই লেখাটি দেখে নিন
- Latin sizes: 14px×3, 28px×1
- Bangla sizes: 14px×1, 16px×11, 20px×1, 28px×1
- small text: bn 14px p.hint "ফলাফল দেখার আগে উপরের বেতনটি নিশ্চিত করু"
- CSS: 11u5x8lnvjk82.css (73 KB), 1ybx2fb9khdrs.css (45 KB), 25g_1sup70ux9.css (13 KB), 0kfz0zyaojuy2.css (5 KB)
- fonts: 11 files: 187, 50, 47, 39, 39, 39, 35, 8, 8, 8, 8 KB

### Citizen · promise form · 1440
Reached: উত্তর বদলান
- Latin sizes: 14px×6, 20px×3, 28px×1
- Bangla sizes: 14px×14, 16px×36, 20px×36, 28px×4
- small text: bn 14px span.eyebrow "মালয়েশিয়া · ৩৬ মাসের চুক্তি"
- small text: bn 14px span.chip "বড় বিপদ"
- small text: bn 14px span.chip "কথা আর কাগজে অমিল"
- small text: bn 14px span "এজেন্ট যা বলেছিল"
- small text: bn 14px span "চুক্তিতে লেখা"
- CSS: 11u5x8lnvjk82.css (73 KB), 1ybx2fb9khdrs.css (45 KB), 25g_1sup70ux9.css (13 KB), 0kfz0zyaojuy2.css (5 KB)
- fonts: 12 files: 187, 50, 47, 39, 39, 39, 35, 27, 8, 8, 8, 8 KB

### Citizen · result (bn) · 1440
Reached: আপনাকে যা বলা হয়েছিল তার চেয়ে মাসে RM 1,250 কম হাতে আসবে
- Latin sizes: 14px×6, 20px×3, 28px×1
- Bangla sizes: 14px×24, 16px×30, 20px×32, 28px×4
- small text: bn 14px span.eyebrow "মালয়েশিয়া · ৩৬ মাসের চুক্তি"
- small text: bn 14px span.chip "বড় বিপদ"
- small text: bn 14px span.chip "কথা আর কাগজে অমিল"
- small text: bn 14px span "এজেন্ট যা বলেছিল"
- small text: bn 14px span "চুক্তিতে লেখা"
- CSS: 11u5x8lnvjk82.css (73 KB), 1ybx2fb9khdrs.css (45 KB), 25g_1sup70ux9.css (13 KB), 0kfz0zyaojuy2.css (5 KB)
- fonts: 12 files: 187, 50, 47, 39, 39, 39, 35, 27, 8, 8, 8, 8 KB

### Citizen · result (en) · 1440
Reached: On paper, you take home RM 1,250 a month less than you were told
- Latin sizes: 12px×5, 14px×23, 16px×28, 20px×24, 28px×5
- Bangla sizes: 14px×1, 16px×1
- small text: en 12px span "what the agent said"
- small text: en 12px span "written in the contract"
- small text: en 12px span "on paper, not a payslip"
- small text: en 12px span.minTag "Law · minimum"
- small text: en 12px span.minTag "RM 1,700"
- CSS: 11u5x8lnvjk82.css (73 KB), 1ybx2fb9khdrs.css (45 KB), 25g_1sup70ux9.css (13 KB), 0kfz0zyaojuy2.css (5 KB)
- fonts: 12 files: 187, 50, 47, 39, 39, 39, 35, 27, 8, 8, 8, 8 KB

### Citizen · result gone · 1440
Reached: এই ফলাফলটি আর নেই
- Latin sizes: –
- Bangla sizes: 16px×2, 28px×1
- CSS: 1ybx2fb9khdrs.css (45 KB), 25g_1sup70ux9.css (13 KB), 0kfz0zyaojuy2.css (5 KB)
- fonts: 11 files: 187, 50, 47, 39, 39, 39, 35, 8, 8, 8, 8 KB

### Citizen · upload error · 1440
Reached: এই ধরনের ফাইল পড়া যায় না
- Latin sizes: –
- Bangla sizes: 16px×4, 28px×1
- small target: input.visuallyHidden 1×1 ""
- CSS: 11u5x8lnvjk82.css (73 KB), 1ybx2fb9khdrs.css (45 KB), 25g_1sup70ux9.css (13 KB), 0kfz0zyaojuy2.css (5 KB)
- fonts: 11 files: 187, 50, 47, 39, 39, 39, 35, 8, 8, 8, 8 KB

### Counsel · start · 1440
Reached: Review a contract for legal risk, with every citation verified.
- Latin sizes: 11.5px×6, 12px×2, 12.5px×2, 13px×2, 14px×24, 15px×3, 16px×1, 17px×1, 18px×1, 19px×6, 52px×1
- Bangla sizes: 14.5px×6, 16px×1
- small text: en 12px span.chip "Offline demo"
- small text: en 13px span.avatar "D"
- small text: en 12px p.kicker "Counsel mode · Bangladesh & migrant labo"
- small text: en 12.5px h2#samples-title "Or try a sample contract"
- small text: en 13px span.sectionMeta "Real-world patterns, no personal data"
- CSS: 11u5x8lnvjk82.css (73 KB), 1ybx2fb9khdrs.css (45 KB), 25g_1sup70ux9.css (13 KB), 0kfz0zyaojuy2.css (5 KB)
- fonts: 11 files: 187, 50, 47, 39, 39, 39, 35, 8, 8, 8, 8 KB

### Counsel · running · 1440
Reached: running, paused at the salary check
- Latin sizes: 12px×3, 13px×1, 13.5px×4, 14px×4, 15px×4, 16px×3, 22px×1, 26px×1
- Bangla sizes: 16px×1
- small text: en 13px span.avatar "D"
- small text: en 12px p.kicker "Analysis in progress"
- small text: en 12px span.chip "Read with"
- small text: en 12px span.chip "% confidence"
- small text: en 13.5px span "Text extraction and clause splitting"
- small target: summary 116×22 "Live agent log"
- CSS: 11u5x8lnvjk82.css (73 KB), 1ybx2fb9khdrs.css (45 KB), 25g_1sup70ux9.css (13 KB), 0kfz0zyaojuy2.css (5 KB)
- fonts: 11 files: 187, 50, 47, 39, 39, 39, 35, 8, 8, 8, 8 KB

### Counsel · Case Desk (bn) · 1440
Reached: Case Desk
- Latin sizes: 12px×3, 13px×1, 14px×36, 16px×1, 20px×2, 28px×3, 40px×1
- Bangla sizes: 14px×160, 16px×21, 20px×4, 28px×2, 40px×2
- small text: en 12px span.hideSm "Offline demo"
- small text: en 13px span.avatar "D"
- small text: bn 14px span.eyebrow "মালয়েশিয়া · ৩৬ মাসের চুক্তি"
- small text: bn 14px button "বাংলা"
- small text: bn 14px span.chip "শর্ত মেলানো"
- CSS: 11u5x8lnvjk82.css (73 KB), 1ybx2fb9khdrs.css (45 KB), 25g_1sup70ux9.css (13 KB), 0kfz0zyaojuy2.css (5 KB)
- fonts: 12 files: 187, 50, 47, 39, 39, 39, 35, 27, 8, 8, 8, 8 KB

### Counsel · Case Desk (en) · 1440
Reached: Case Desk
- Latin sizes: 12px×101, 13px×1, 14px×92, 16px×18, 20px×4, 28px×5, 40px×3
- Bangla sizes: 14px×5, 16px×1
- small text: en 12px span.hideSm "Offline demo"
- small text: en 13px span.avatar "D"
- small text: bn 14px button "বাংলা"
- small text: en 12px span "what the agent said"
- small text: en 12px span "written in the contract"
- small target: a 295×18 "Minimum Wages Order 2024 (Malaysia) · pa"
- CSS: 11u5x8lnvjk82.css (73 KB), 1ybx2fb9khdrs.css (45 KB), 25g_1sup70ux9.css (13 KB), 0kfz0zyaojuy2.css (5 KB)
- fonts: 12 files: 187, 50, 47, 39, 39, 39, 35, 27, 8, 8, 8, 8 KB

### Counsel · Memo · 1440
Reached: Memo11
- Latin sizes: 12px×68, 12.5px×8, 13px×31, 13.5px×25, 14px×34, 14.5px×12, 15px×11, 16px×2, 19px×1, 20px×4, 21px×11, 36px×1
- Bangla sizes: 11.5px×1, 14.5px×11, 16px×2
- small text: en 12px span.hideSm "Offline demo"
- small text: en 13px span.avatar "D"
- small text: en 12px p.kicker "Legal risk memo · Prepared for"
- small text: en 12px p.kicker "Migrant worker and caseworker"
- small text: en 12px span.sev "Critical"
- small target: summary 154×22 "Limits of this memo"
- CSS: 11u5x8lnvjk82.css (73 KB), 1ybx2fb9khdrs.css (45 KB), 25g_1sup70ux9.css (13 KB), 0kfz0zyaojuy2.css (5 KB)
- fonts: 12 files: 187, 50, 47, 39, 39, 39, 35, 27, 8, 8, 8, 8 KB

### Counsel · Council after a question · 1440
Reached: Council
- Latin sizes: 11px×4, 11.5px×14, 12px×8, 12.5px×45, 13px×9, 13.5px×4, 14px×23, 14.5px×8, 15px×1, 16px×1, 16.5px×3, 32px×1
- Bangla sizes: 13.5px×1, 16px×1
- small text: en 12px span.hideSm "Offline demo"
- small text: en 13px span.avatar "D"
- small text: en 12px p#council-who "Who answers"
- small text: en 12.5px span "All three answer, then they can delibera"
- small text: en 11.5px em "Sunny"
- CSS: 11u5x8lnvjk82.css (73 KB), 1ybx2fb9khdrs.css (45 KB), 25g_1sup70ux9.css (13 KB), 0kfz0zyaojuy2.css (5 KB)
- fonts: 12 files: 187, 50, 47, 39, 39, 39, 35, 27, 8, 8, 8, 8 KB

### Counsel · Checks · 1440
Reached: Checks26/27
- Latin sizes: 11.5px×27, 12px×196, 12.5px×8, 13px×9, 13.5px×21, 14px×42, 14.5px×25, 15px×1, 16px×1, 28px×1, 32px×1
- Bangla sizes: 13.5px×8, 14.5px×2, 16px×1
- small text: en 12px span.hideSm "Offline demo"
- small text: en 13px span.avatar "D"
- small text: en 13px span.statLabel "legal claims checked"
- small text: en 13px span.statLabel "passed every check"
- small text: en 13px span.statLabel "passed with a warning"
- small target: a.citeLink 346×22 "Overseas Employment and Migrants Act 201"
- small target: a.citeLink 323×22 "Forced Labour Convention 1930 (No. 29) ·"
- small target: a.citeLink 328×22 "Employment Act 1955 (Act 265) Malaysia ·"
- small target: a.citeLink 748×22 "ILO General Principles and Operational G"
- small target: a.citeLink 583×22 "Responsible Business Alliance Code of Co"
- CSS: 11u5x8lnvjk82.css (73 KB), 1ybx2fb9khdrs.css (45 KB), 25g_1sup70ux9.css (13 KB), 0kfz0zyaojuy2.css (5 KB)
- fonts: 12 files: 187, 50, 47, 39, 39, 39, 35, 27, 8, 8, 8, 8 KB

### /docs · 1440
Reached: A legal copilot whose citations can't be made up.
- Latin sizes: 11.44px×5, 12px×51, 12.32px×3, 13px×101, 13.2px×7, 14px×21, 15px×46, 16px×34, 26px×2, 28px×8, 48px×1
- Bangla sizes: 16px×1, 18px×1
- small text: en 13px p.eyebrow "Docs · pitch · system status"
- small text: en 13px p.disclaimer "Decision support, not legal advice."
- small text: en 12.32px code "/api/health"
- small text: en 12.32px code "/api/metrics"
- small text: en 13px div.tileLabel "Model mode"
- small target: summary 479×20 "Show as a table"
- small target: summary 479×20 "Show as a table"
- small target: summary 479×20 "Show as a table"
- CSS: 11u5x8lnvjk82.css (73 KB), 1ybx2fb9khdrs.css (45 KB), 25g_1sup70ux9.css (13 KB), 3sw_pei81n09v.css (8 KB), 0kfz0zyaojuy2.css (5 KB)
- fonts: 11 files: 187, 50, 47, 39, 39, 39, 35, 8, 8, 8, 8 KB

### /login · 1440
Reached: Sign in
- Latin sizes: 12.5px×1, 13.5px×1, 14px×4, 15px×1, 16px×1, 26px×1
- Bangla sizes: 16px×1
- small text: en 13.5px button.linkBtn "Show"
- small text: en 12.5px span "Passwords are stored only as a salted ha"
- small target: a 124×17 "Create an account"
- CSS: 11u5x8lnvjk82.css (73 KB), 1ybx2fb9khdrs.css (45 KB), 25g_1sup70ux9.css (13 KB), 0kfz0zyaojuy2.css (5 KB)
- fonts: 11 files: 187, 50, 47, 39, 39, 39, 35, 8, 8, 8, 8 KB

