# Template Coverage Assessment (2026-07-04)

Source folders:
- `private_data/poc/Comp_1/template/excelformat/Master`
- `private_data/poc/Comp_1/template/excelformat/Excel format (สร้างเอง)`

Baseline used for comparison:
- `private_data/poc/Comp_1/template/*.csv`

Purpose:
- decide what can enter UAT now
- separate same-family variants from new scope
- support CR / pricing discussion with client

## Executive Summary

- Total files reviewed: `52`
- `UAT now`: `14`
- `UAT after fix / mapping review`: `21`
- `New scope / should not be treated as existing 6-template baseline`: `17`

Repo/runtime note:
- current runtime seed is still only `Express GL` and `Purchase Tax`
- 6-file Express fan-out export job is still not wired end-to-end
- therefore this report is about template-family coverage, not current production readiness

## Recommendation

### No CR

Do not CR for files that are only extra examples of the same already-agreed structure:

- cash purchase / credit purchase files with same 8-column baseline
- expense single-line files with same 9-column baseline
- sales/cash files only if the client confirms the date format expectation is still acceptable

These are examples/data coverage, not new feature families.

### Borderline: minor CR or absorb if needed

Consider small CR only if the team wants to formalize extra effort for same-family variants:

- sales files with added `อ้างอิง`
- WHT files expanded from 11 columns to 16-17 columns
- files that keep same family but drift in date format from earlier baseline
- files with blank padding columns that must be preserved exactly for Express import

This is still near the old scope, but it is no longer just "same file, more rows".

### Should CR

Recommend CR for genuinely new families beyond the original 6-template export baseline:

- PO / RR pull format
- purchase order format
- multi-line sales / purchase variants
- receipt / debt collection (`RE`)
- journal RV format, if it must be exported as a separate Express-compatible file from confirmed DR/CR lines
- vendor master
- customer master
- product master
- bank withdraw / deposit / transfer
- Shopee-Tiktok mixed variant with expanded structure

These are not just sample additions. They imply new mapping rules, possibly new source fields, different business meaning, and more testing.

Journal note:
- `Journal-RV` is different from `PO/RR`. It is not blocked because scan lacks the data.
- If the review screen already lets the user confirm `DR/CR` and balance the entry after scanning, that confirmed journal data can be the source for Journal export.
- The remaining work is to map those confirmed journal lines into the exact `Journal-RV` file format, including voucher fields, detail text, debit/credit columns, account columns, encoding, and import proof.
- Therefore Journal should be positioned as a GL/Journal export extension from confirmed entries, not as an OCR extraction problem.

## Questions To Ask Client Before Final Quote

1. Should all `52` files be supported in Phase UAT, or only the files that match the original 6 Express transaction families?
2. For sales files, should the accepted date format be `DD/MM/YY` or `D/M/YYYY`? Current samples conflict.
3. Is the added `อ้างอิง` column required for import, or optional for user convenience only?
4. For WHT variants with 16-17 columns, are the trailing blank columns required by Express import, or just template layout noise from user-generated files?
5. Are `PO/RR`, `ใบสั่งซื้อ`, `RE`, bank transfer files, and master files part of the paid Phase II scope now, or requested as additional scope?
6. For `Journal-RV`, should the source be the already-confirmed `DR/CR` review screen, and should this be treated as the GL/Journal export format for Phase II?
7. For `Shopee - Tiktok` mixed files, should this be treated as one special template or as two standard templates with preprocessing rules?
8. Is success criterion "match file structure" only, or "client can import into Express without manual edits"?

## UAT Now

These match the existing baseline family closely enough to treat as same-family coverage.

| File | Baseline Family |
| --- | --- |
| `001. ซื้อสด บรรทัดเดียว.csv` | `14 ซื้อเชื่อ บรรทัดเดียว.csv` |
| `002.ซื้อเชื่อ บรรทัดเดียว.csv` | `14 ซื้อเชื่อ บรรทัดเดียว.csv` |
| `003.ค่าใช้จ่ายอื่นๆ บรรทัดเดียว.csv` | `15 ค่าใช้จ่ายอื่นๆ บรรทัดเดียว.csv` |
| `006.ขายสด บรรทัดเดียว.csv` | `24 ขายเชื่อ บรรทัดเดียว.csv` |
| `ซื้อสด 031 ค่าธรรมเนียม ทาโร่.csv` | `14 ซื้อเชื่อ บรรทัดเดียว.csv` |
| `ซื้อสด 031 ค่าธรรมเนียม ใต้ถุน.csv` | `14 ซื้อเชื่อ บรรทัดเดียว.csv` |
| `ซื้อสด 047 บรรทัดเดียว.csv` | `14 ซื้อเชื่อ บรรทัดเดียว.csv` |
| `ซื้อสด 501 บรรทัดเดียว - ค่าธรรมเนียม.csv` | `14 ซื้อเชื่อ บรรทัดเดียว.csv` |
| `ซื้อเชื่อ 004 บรรทัดเดียว.csv` | `14 ซื้อเชื่อ บรรทัดเดียว.csv` |
| `ซื้อเชื่อ 009 บรรทัดเดียว.csv` | `14 ซื้อเชื่อ บรรทัดเดียว.csv` |
| `ซื้อเชื่อ 011 บรรทัดเดียว.csv` | `14 ซื้อเชื่อ บรรทัดเดียว.csv` |
| `ซื้อเชื่อ 023 บรรทัดเดียว.csv` | `14 ซื้อเชื่อ บรรทัดเดียว.csv` |
| `ซื้อเชื่อ 032 บรรทัดเดียว.csv` | `14 ซื้อเชื่อ บรรทัดเดียว.csv` |
| `ซื้อเชื่อ 501 บรรทัดเดียว.csv` | `14 ซื้อเชื่อ บรรทัดเดียว.csv` |

## UAT After Fix

These are same-family or near-family, but should not go in untouched.

| File | Best Baseline | Why Not Immediate |
| --- | --- | --- |
| `001. ซื้อสด มีหัก บรรทัดเดียว.csv` | `15 ค่าใช้จ่ายอื่นๆ(มีหัก)3บรรทัดเดียว.csv` | date drift, `16` cols vs `11`, blank padding cols |
| `003.ค่าใช้จ่ายอื่นๆ(มีหัก)บรรทัดเดียว.csv` | `15 ค่าใช้จ่ายอื่นๆ(มีหัก)3บรรทัดเดียว.csv` | date drift, `17` cols vs `11`, blank padding cols |
| `005.ขายเชื่อ บรรทัดเดียว.csv` | `22 ขายสด บรรทัดเดียว.csv` | date drift, extra column |
| `ขายสด 008 บรรทัดเดียว สดย่อย.csv` | `22 ขายสด บรรทัดเดียว.csv` | date drift |
| `ขายสด 008 บรรทัดเดียว สดเต็ม.csv` | `22 ขายสด บรรทัดเดียว.csv` | date drift |
| `ขายสด 067 บรรทัดเดียว.csv` | `22 ขายสด บรรทัดเดียว.csv` | date drift |
| `ขายเชื่อ 004  บรรทัดเดียว.csv` | `22 ขายสด บรรทัดเดียว.csv` | date drift, extra column |
| `ขายเชื่อ 008  บรรทัดเดียว เต็มรูป.csv` | `22 ขายสด บรรทัดเดียว.csv` | date drift, extra column |
| `ขายเชื่อ 015  บรรทัดเดียว.csv` | `22 ขายสด บรรทัดเดียว.csv` | date drift, extra column |
| `ขายเชื่อ 031 บรรทัดเดียว.csv` | `22 ขายสด บรรทัดเดียว.csv` | date drift, extra column |
| `ขายเชื่อ 050  บรรทัดเดียว.csv` | `22 ขายสด บรรทัดเดียว.csv` | extra column |
| `ขายเชื่อ 067  บรรทัดเดียว.csv` | `22 ขายสด บรรทัดเดียว.csv` | date drift, extra column |
| `ค่าใช้จ่ายอื่นๆ 015 (มีหัก)บรรทัดเดียว.csv` | `15 ค่าใช้จ่ายอื่นๆ(มีหัก)3บรรทัดเดียว.csv` | date drift, `16` cols, blank padding cols |
| `ค่าใช้จ่ายอื่นๆ 501 (มีหัก)บรรทัดเดียว.csv` | `15 ค่าใช้จ่ายอื่นๆ(มีหัก)3บรรทัดเดียว.csv` | date drift, `17` cols, blank padding cols |
| `ซื้อสด 023 บรรทัดเดียว - ค่าทางด่วน.csv` | `12 ซื้อสด บรรทัดเดียว.csv` | date drift |
| `ซื้อสด 067 ค่าธรรมเนียม.csv` | `15 ค่าใช้จ่ายอื่นๆ(มีหัก)3บรรทัดเดียว.csv` | date drift, `16` cols |
| `ซื้อสด 501 บรรทัดเดียว - ค่าทางด่วน.csv` | `12 ซื้อสด บรรทัดเดียว.csv` | `13` cols, blank padding cols |
| `ซื้อสด 501 บรรทัดเดียว -ค่าขนส่งช็อปปี้(SPX).csv` | `12 ซื้อสด บรรทัดเดียว.csv` | `13` cols, blank padding cols |
| `ซื้อสด มีหัก 015 บรรทัดเดียว - 510006.csv` | `15 ค่าใช้จ่ายอื่นๆ(มีหัก)3บรรทัดเดียว.csv` | `16` cols, blank padding cols |
| `ซื้อสด มีหัก 015 บรรทัดเดียว - 510009.csv` | `15 ค่าใช้จ่ายอื่นๆ(มีหัก)3บรรทัดเดียว.csv` | date drift, `16` cols, blank padding cols |
| `ซื้อเชื่อ 050 บรรทัดเดียว.csv` | `12 ซื้อสด บรรทัดเดียว.csv` | date drift |

## New Scope

These should not be counted as the same deliverable as the original 6-file baseline.

| File | Why New Scope |
| --- | --- |
| `002.ซื้อเชื่อ ดึง PO บรรทัดเดียว.csv` | PO/RR family |
| `002.ซื้อเชื่อ หลายบรรทัด.csv` | multi-line purchase family |
| `004.ใบสั่งซื้อ บรรทัดเดียว.csv` | purchase-order family |
| `005.ขายเชื่อ หลายบรรทัดเดียว.csv` | multi-line sales family |
| `006.ขายสด หลายบรรทัด.csv` | multi-line sales family |
| `007.รับชำระหนี้ RE.csv` | receipt / debt collection family |
| `008.เพิ่มผู้จำหน่าย.csv` | vendor master |
| `009.เพิ่มลูกค้า.csv` | customer master |
| `010.เพิ่มสินค้า.csv` | product master |
| `011. Journal-RV  บรรทัดเดียว.csv` | journal export from confirmed DR/CR lines; needs exact file mapping and import proof |
| `012.ถอนเงินสดจากธนาคาร BW.csv` | bank movement family |
| `013.ฝากเงินสดจากธนาคาร BD.csv` | bank movement family |
| `014.โอนเงินระหว่างธนาคาร.csv` | bank movement family |
| `Journal-RV 067 บรรทัดเดียว.csv` | journal export from confirmed DR/CR lines; needs exact file mapping and import proof |
| `ขายเชื่อ 067  บรรทัดเดียว Shopee -Tiktok.csv` | expanded mixed marketplace variant |
| `ซื้อเชื่อ ดึง PO 054 บรรทัดเดียว.csv` | PO/RR family |
| `ใบสั่งซื้อ 054 บรรทัดเดียว.csv` | purchase-order family |

## Commercial Positioning Suggestion

Use this framing with the client:

- The original export baseline covered the known Express transaction templates.
- The newly sent files split into:
  - same-family examples we can absorb or lightly adjust
  - near-family variants needing extra mapping and validation
  - new template families that are outside the original baseline and should be treated as added scope

Practical pricing stance:

- `No extra charge`: `14` same-family UAT-now files
- `Small adjustment / absorb if strategic`: `21` UAT-after-fix files
- `CR / added scope`: new-scope files that require new data source, business flow, or import proof
- `Journal-specific position`: do not say scan has no Journal data if the user confirms `DR/CR`; instead, price it as a Journal/GL export format from confirmed review data if it was not already included in the agreed GL export scope
