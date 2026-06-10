# Phase 12 Discussion Log

**Phase:** 12  
**Date:** 2026-06-09  
**Mode:** discuss

## Areas Discussed

### Area 1: CLI Entry Point Design

**Question:** Single `scan` command vs scan + subcommands?
**Options presented:** Single command | Subcommands | Let Claude decide
**Selection:** Claude decides (user selected "Claude 决定")

**Outcome:** Single command with `--plan` (default) and `--run` modes.  
**Notes:** Simpler UX. `--plan` is the safe default. User must explicitly `--run` to execute.

---

### Area 2: Watchlist Validation Timing

**Question:** Immediate fail or complete issue list?
**Options presented:** Immediate fail | Complete list | Let Claude decide
**Selection:** Claude decides (user selected "Claude 决定")

**Outcome:** Immediate fail on first error in `--run` mode; `--plan` shows all issues.  
**Notes:** CLI tool convention (fail fast). `--plan` mode gives complete picture.

---

### Area 3: Scan Plan Format

**Question:** JSON, table, or both?
**Options presented:** JSON only | Table only | Both (default table)
**Selection:** Both with default table (user selected "两者都有")

**Outcome:** `--format table` (default) for human-readable; `--format json` for machine-readable.  
**Notes:** Humans see table by default; scripts use JSON.

---

### Area 4: Output Directory Strategy

**Question:** Timestamp directory, fixed date directory, or user-specified?
**Options presented:** Timestamp directory | Fixed date directory | User-specified
**Selection:** Fixed date directory (user selected "固定日期目录")

**Outcome:** `output/YYYY-MM-DD/` default; `--output` for user override.  
**Notes:** Simple daily workflow. Same-date runs overwrite.

---

### Area 5: Parquet Dependency Declaration

**Question:** Hard dependency, optional dependency, or lazy detection?
**Options presented:** Hard dependency | Optional dependency | Lazy detection
**Selection:** Lazy detection (user selected "懒加载")

**Outcome:** Runtime detection with helpful error message.  
**Notes:** Backward compatibility. Clear message on install.

---

## Summary

All 5 implementation decisions captured for Phase 12. No scope creep. No deferred ideas. Ready for planning.
