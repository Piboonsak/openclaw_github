# OCR confidence on RRL scanned bills — Thai language pack effect

Folder: `private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL`
Sample: 8 PDFs, `random.seed=42`, fresh cache.

## Root cause

The bundled Tesseract install (`C:/Program Files/Tesseract-OCR/tessdata/`) shipped only
`eng.traineddata` and `osd.traineddata`. PaddleOCR was also unavailable on this machine
(`numpy`/`paddleocr` not installed in `.venv`), so every OCR call silently fell back to
Tesseract with `lang="tha+eng"` running on the English model alone. Thai glyphs were
transliterated into Latin look-alikes (e.g. `AuatvlumAumy`, `sannzeinnnte`), driving
confidence down and tripping `needs_human_review` on every scanned page.

## Fix

- Download `tha.traineddata` (tessdata_best, 7.6 MB) to repo-local `.tessdata/`.
- Pass `--tessdata-dir <repo>/.tessdata` to Tesseract via `pytesseract` `config=`
  whenever `tha.traineddata` is present there.
- Bump PDF render scale from `2.0` → `3.0` (`OCR_RENDER_SCALE` env-configurable)
  so Thai tone/vowel marks survive the bitmap stage.
- Drop the `MedianFilter(size=3)` preprocessing pass that was smearing those marks.
- Compute `avg_conf` as length-weighted mean so 1–2 char noise blocks no longer
  drag the score down.

`.tessdata/` is ignored by git (operators re-download per `evaluation/README` or the
plan in this file).

## Measurement

| file                        | blocks | weighted avg | low(<0.6) % | needs_human_review |
|-----------------------------|-------:|-------------:|------------:|:------------------:|
| 03062026131847.pdf          |    779 |       0.8317 |        9.9% |        False       |
| 03062026130520.pdf          |    881 |       0.8609 |        7.0% |        False       |
| 03062026125316.pdf          |   1381 |       0.9092 |        2.6% |        False       |
| 03062026130835.pdf          |    868 |       0.8752 |        5.1% |        False       |
| 03062026130752.pdf          |    920 |       0.8889 |        3.8% |        False       |
| 03062026130738.pdf          |   1147 |       0.8927 |        3.1% |        False       |
| 03062026130532.pdf          |    862 |       0.8343 |        9.9% |        False       |
| 03062026130503.pdf          |    899 |       0.8599 |        8.0% |        False       |
| **aggregate (n=8)**         |        |   **0.8691** |             |    **0/8 flagged** |

Baseline (before Thai pack, before render-scale bump): mean weighted ≈ 0.35,
`needs_human_review` 5/5 on the first 5-file sample.

## Reproduce

```powershell
# one-time setup: download Thai/English/OSD trained data to repo-local .tessdata/
$tessdata = 'D:/01_gitrepo/ai-accounting-copilot/.tessdata'
New-Item -ItemType Directory -Force -Path $tessdata | Out-Null
foreach ($lang in @('tha','eng','osd')) {
    Invoke-WebRequest -Uri "https://github.com/tesseract-ocr/tessdata_best/raw/main/$lang.traineddata" `
        -OutFile "$tessdata/$lang.traineddata" -UseBasicParsing
}

# clear cache for the sample folder, then re-run diag
./.venv/Scripts/python.exe scripts/diag_ocr_confidence.py `
    "private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL" --n 8 --seed 42 --no-cache
```
