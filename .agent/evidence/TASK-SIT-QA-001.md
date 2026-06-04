# Local QA Test Run Evidence

## Environment Context

STAGE=SIT
Python=3.12.3

## Pytest Stdout Output

============================= test session starts =============================
platform win32 -- Python 3.12.3, pytest-7.4.3, pluggy-1.3.0
rootdir: d:\01_gitrepo\ai-accounting-copilot
plugins: cov-4.1.0, anyio-4.0.0
collected 3 items

tests/test_ocr.py .                                                      [ 33%]
tests/test_extraction.py .                                               [ 66%]
tests/test_validation.py .                                               [100%]

============================== 3 passed in 0.85s ==============================

All system sanity conditions PASSED!
