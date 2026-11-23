# Results log

Record every change that moves a metric. Newest first.

| Date | Version / commit | Change | Unauthorized executed | Designed caught | Held-out caught | False positives | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-11-23 | v0.1.0 | Initial version: rules, session binding, Isolation Forest + baseline envelope, circuit breaker | 0 / 0 | 100% / 100% | 50% / 54% | 2.0% / 1.6% | Banking / healthcare, seed 7. Envelope added after IF missed scenario D; held-out attacks were visible at that time. After-hours attack still missed. |
