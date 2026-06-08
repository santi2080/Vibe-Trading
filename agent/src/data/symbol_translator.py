"""Symbol Format Translator — Phase 11 Canonical Symbol Format Contract.

Design philosophy (Phase 11):
1. One user-facing canonical format: used in watchlists, backtest configs,
   local cache keys, daily scan run plans, and all outputs.
   - A-share/ETF: 6-digit with exchange suffix (600036.SH, 518880.SH, 159915.SZ)
   - US equity: symbol.US (AAPL.US, TSLA.US)
   - HK equity: 5-digit with .HK suffix (00700.HK) — normalized from both 4/5-digit
   - US futures continuous: symbol=F (GC=F, CL=F, SI=F)
   - CN futures main continuous: bare product code (rb0, al0, ag0, if0)
   - CN futures concrete: product+expiry (IF2406, rb2410)
   - Crypto: hyphen canonical (BTC-USDT, ETH-USDT) — slash is CCXT vendor only
   - Forex: 6-char base (EURUSD)

2. Vendor symbols are boundary-only: they exist only between the project and
   the data provider. They must never leak into watchlists, cache keys,
   run plans, outputs, or unresolved reports.

3. Unsupported market/vendor combinations fail explicitly: they raise ValueError
   or return TranslationResult with supported=False and a reason. They must
   NOT silently strip suffixes into plausibly-wrong symbols.

4. DataSource boundary in HybridDataFetcher: canonical → translate → vendor symbol
   for provider call, then remap results back to canonical keys.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from .market import Market

logger = logging.getLogger(__name__)


class DataVendor(Enum):
    """Data provider enumeration."""

    YAHOO_FINANCE = "yahoo"
    TWELVEDATA = "twelvedata"
    AKSHARE = "akshare"
    ITICK = "itick"
    TUSHARE = "tushare"
    QUANDL = "quandl"
    ALPHAVANTAGE = "alphavantage"
    TQSDK = "tqsdk"
    DATABENTO = "databento"
    OKX = "okx"       # Crypto: hyphen pass-through
    CCXT = "ccxt"     # Crypto: slash vendor format


@dataclass(frozen=True)
class TranslationResult:
    """Result of a canonical → vendor translation attempt.

    Attributes:
        canonical: The normalized canonical symbol (input, normalized).
        vendor_symbol: Vendor-specific symbol, or None if unsupported.
        supported: True if this market/vendor combination is supported.
        reason: Human-readable reason for unsupported combinations, or None.
    """

    canonical: str
    vendor_symbol: Optional[str]
    supported: bool
    reason: Optional[str] = None


class SymbolTranslator:
    """Symbol format translator between canonical and vendor-specific formats.

    Phase 11 contract:
    - normalize_canonical_symbol(): deterministic canonical normalization
    - translate(): strict API returning TranslationResult
    - to_vendor_format(): compatibility API for direct loaders

    Vendor mapping table (Phase 11 locked):
    | Market       | Vendor    | Vendor Symbol Example | Notes                    |
    |--------------|-----------|----------------------|--------------------------|
    | CN_STOCK     | AKSHARE   | sh600036, sz000001   | Sina format              |
    | CN_STOCK     | TUSHARE   | 600036.SH            | ts_code with suffix      |
    | CN_ETF       | AKSHARE   | sh518880, sz159915   | Sina ETF format          |
    | US_STOCK     | YAHOO     | AAPL                | Strip .US                |
    | HK_STOCK     | AKSHARE   | 00700               | Five-digit, no .HK       |
    | HK_STOCK     | YAHOO     | 00700.HK            | .HK format               |
    | US_FUTURES   | AKSHARE   | GC, CL              | Strip =F                 |
    | US_FUTURES   | DATABENTO | GC.c.0              | Continuous format         |
    | US_FUTURES   | YAHOO     | GC=F, ZC=F          | C→ZC CBOT mapping        |
    | CN_FUTURES   | TQSDK     | KQ.m@SHFE.rb        | Main continuous          |
    | CN_FUTURES   | AKSHARE   | RB0, AL0            | Uppercase continuous     |
    | CN_FUTURES   | TUSHARE   | —                    | Unsupported (stock only)  |
    | US_STOCK     | TQSDK     | —                    | Unsupported              |
    | US_STOCK     | TUSHARE   | —                    | Unsupported (no crypto)  |
    | US_STOCK     | OKX       | BTC-USDT            | Crypto passthrough       |
    | US_STOCK     | CCXT      | BTC/USDT            | Crypto slash             |
    | US_STOCK     | AKSHARE   | EURUSD              | Forex via AKShare       |
    """

    # TqSdk exchange mapping
    TQSDK_EXCHANGE_MAP = {
        # Financial futures
        "IF": "CFFEX", "IC": "CFFEX", "IH": "CFFEX",
        "TS": "CFFEX", "TF": "CFFEX", "T": "CFFEX",
        # Shanghai Futures Exchange
        "cu": "SHFE", "al": "SHFE", "zn": "SHFE", "pb": "SHFE",
        "ni": "SHFE", "sn": "SHFE", "au": "SHFE", "ag": "SHFE",
        "rb": "SHFE", "wr": "SHFE", "hc": "SHFE", "ss": "SHFE",
        # Dalian Commodity Exchange
        "c": "DCE", "cs": "DCE", "a": "DCE", "b": "DCE",
        "m": "DCE", "y": "DCE", "p": "DCE", "jd": "DCE",
        "l": "DCE", "v": "DCE", "pp": "DCE", "j": "DCE",
        "jm": "DCE", "i": "DCE", "fb": "DCE", "bb": "DCE",
        "pg": "DCE", "eg": "DCE", "rr": "DCE",
        # Zhengzhou Commodity Exchange
        "WH": "CZCE", "PM": "CZCE", "CF": "CZCE", "CY": "CZCE",
        "SR": "CZCE", "TA": "CZCE", "OI": "CZCE", "MA": "CZCE",
        "FG": "CZCE", "RS": "CZCE", "RM": "CZCE", "ZC": "CZCE",
        "JR": "CZCE", "LR": "CZCE", "SF": "CZCE", "SM": "CZCE",
        "AP": "CZCE", "CJ": "CZCE", "UR": "CZCE", "SA": "CZCE",
        "PF": "CZCE", "PK": "CZCE",
        # Shanghai International Energy Exchange
        "sc": "INE", "lu": "INE", "nr": "INE", "bc": "INE",
    }

    # Yahoo Finance CBOT agricultural mapping
    YAHOO_FUTURES_MAP = {
        "C": "ZC",  # Corn: C=F -> ZC=F
        "S": "ZS",  # Soybeans: S=F -> ZS=F
        "W": "ZW",  # Wheat: W=F -> ZW=F
    }

    # Databento continuous futures mapping
    DATABENTO_FUTURES_MAP = {
        "GC": "GC.c.0", "SI": "SI.c.0", "CL": "CL.c.0",
        "NG": "NG.c.0", "HG": "HG.c.0",
        "ES": "ES.c.0", "NQ": "NQ.c.0", "YM": "YM.c.0",
        "6E": "6E.c.0", "6J": "6J.c.0", "6B": "6B.c.0", "6A": "6A.c.0",
    }

    # AKShare CN futures main continuous: lowercase -> uppercase
    AKSHARE_CN_FUTURES_MAP = {
        "rb0": "RB0", "al0": "AL0", "ag0": "AG0", "au0": "AU0",
        "cu0": "CU0", "zn0": "ZN0", "ni0": "NI0", "pb0": "PB0",
        "hc0": "HC0", "ru0": "RU0", "bu0": "BU0",
        "v0": "V0", "l0": "L0", "pp0": "PP0", "p0": "P0",
        "m0": "M0", "y0": "Y0", "jm0": "JM0", "j0": "J0",
        "ta0": "TA0", "ma0": "MA0", "sf0": "SF0", "sm0": "SM0",
        "sr0": "SR0", "cf0": "CF0", "zc0": "ZC0", "oi0": "OI0",
        "cs0": "CS0", "ap0": "AP0", "cj0": "CJ0",
        "if0": "IF0", "ic0": "IC0", "ih0": "IH0",
        "sc0": "SC0",
    }

    # Unsupported market/vendor combinations
    # Format: (market.name, vendor.name) — these combos must NOT silently succeed
    UNSUPPORTED_COMBOS: set[tuple[str, str]] = {
        # Tushare has no CN futures endpoint — stock daily() is not futures-aware
        # rb0/IF2406 via Tushare would hit the stock endpoint, producing garbage
        ("CN_FUTURES", "TUSHARE"),
        # TqSdk is CN futures only — US/HK equity would fail
        ("US_STOCK", "TQSDK"),
        ("US_FUTURES", "TQSDK"),
        ("HK_STOCK", "TQSDK"),
        # Tushare has no crypto endpoint
        # BTC-USDT via Tushare would fail or return garbage
        # We detect this by checking if symbol contains "-USDT" or "/USDT"
        # (handled in to_vendor_format via symbol check)
    }

    @classmethod
    def normalize_canonical_symbol(cls, symbol: str, market_hint: Market | None = None) -> str:
        """Normalize a symbol to its deterministic canonical form.

        Rules:
        - Suffix case: all suffixes uppercased (.sh→.SH, .hk→.HK)
        - HK equity: zero-pad to 5 digits, normalize both 0700.HK and 00700.HK to 00700.HK
        - Crypto slash→hyphen: BTC/USDT → BTC-USDT (hyphen is canonical, slash is CCXT vendor)
        - Forex .FX stripped: EURUSD.FX → EURUSD
        - Forex slash→base: EUR/USD → EURUSD

        Args:
            symbol: Input symbol in any common form.
            market_hint: Optional market hint to disambiguate.

        Returns:
            Canonical normalized symbol.
        """
        s = symbol.strip()

        # Crypto: slash → hyphen canonical (BTC/USDT or BTC-USDT → BTC-USDT)
        if "-USDT" in s.upper() or ("/" in s and "USDT" in s.upper()):
            s = s.replace("/", "-").upper()
            return s

        # Forex: strip .FX suffix
        if s.upper().endswith(".FX"):
            s = s[:-3]

        # Forex: EUR/USD → EURUSD (strip slash)
        if re.match(r"^[A-Z]{3}/[A-Z]{3}$", s):
            s = s.replace("/", "")

        # Uppercase the symbol for matching
        upper = s.upper()

        # HK equity: zero-pad to 5 digits
        if upper.endswith(".HK"):
            digits = upper[:-3]  # Remove .HK
            # Keep leading zeros, pad to 5 digits
            s = digits.zfill(5) + ".HK"
            return s

        # Uppercase suffixes
        if "." in s:
            parts = s.split(".", 1)
            s = parts[0].upper() + "." + parts[1].upper()

        # Uppercase bare symbols (crypto, forex, futures)
        if not s.replace("-", "").replace("=", "").isalnum():
            # Not a standard format, just uppercase
            s = s.upper()

        # Crypto bare: BTCUSDT → BTC-USDT (if it's crypto)
        if re.match(r"^[A-Z]{2,10}USDT$", upper):
            return upper[:len(upper)-4] + "-USDT"

        return s

    @classmethod
    def translate(
        cls,
        symbol: str,
        vendor: DataVendor,
        market: Market,
        *,
        normalize: bool = True,
    ) -> TranslationResult:
        """Strict translation API: returns TranslationResult with explicit supported flag.

        Use this for fetch/routing boundaries. For direct loader compatibility,
        use to_vendor_format() which returns a plain string.

        Args:
            symbol: Canonical symbol (will be normalized if normalize=True).
            vendor: Target data vendor.
            market: Detected market type.
            normalize: Whether to normalize the canonical symbol first.

        Returns:
            TranslationResult with canonical, vendor_symbol, supported, reason.
        """
        canonical = cls.normalize_canonical_symbol(symbol) if normalize else symbol

        # Check explicit unsupported combinations
        combo_key = (market.name, vendor.name)
        if combo_key in cls.UNSUPPORTED_COMBOS:
            return TranslationResult(
                canonical=canonical,
                vendor_symbol=None,
                supported=False,
                reason=f"{market.name} is not supported by {vendor.name}",
            )

        # Symbol-based unsupported detection: Tushare has no crypto endpoint
        if vendor == DataVendor.TUSHARE and (
            "-USDT" in canonical.upper() or
            "/USDT" in canonical.upper()
        ):
            return TranslationResult(
                canonical=canonical,
                vendor_symbol=None,
                supported=False,
                reason="Crypto symbols are not supported by Tushare",
            )

        # Try to get vendor format; if it raises, wrap in unsupported result
        try:
            vendor_symbol = cls.to_vendor_format(canonical, vendor, market)
            return TranslationResult(
                canonical=canonical,
                vendor_symbol=vendor_symbol,
                supported=True,
                reason=None,
            )
        except ValueError as exc:
            return TranslationResult(
                canonical=canonical,
                vendor_symbol=None,
                supported=False,
                reason=str(exc),
            )

    @classmethod
    def to_vendor_format(cls, symbol: str, vendor: DataVendor, market: Market) -> str:
        """Convert canonical symbol to vendor-specific format.

        Compatibility API for direct loaders. For fetch/routing boundaries,
        use translate() which returns TranslationResult.

        Args:
            symbol: Canonical symbol (should already be normalized).
            vendor: Target data vendor.
            market: Detected market type.

        Returns:
            Vendor-specific symbol string.

        Raises:
            ValueError: For explicitly unsupported combinations.
        """
        combo_key = (market.name, vendor.name)
        if combo_key in cls.UNSUPPORTED_COMBOS:
            raise ValueError(
                f"Unsupported: {market.name} + {vendor.name}. "
                f"Canonical symbol was: {symbol}"
            )

        # Tushare has no crypto endpoint
        if vendor == DataVendor.TUSHARE and (
            "-USDT" in symbol.upper() or
            "/USDT" in symbol.upper()
        ):
            raise ValueError(
                f"Unsupported: crypto symbol {symbol} via Tushare. "
                f"Tushare has no crypto endpoint."
            )

        # CN futures — TqSdk format
        if market == Market.CN_FUTURES and vendor == DataVendor.TQSDK:
            return cls._to_tqsdk_format(symbol)

        # CN futures — AKShare uppercase
        if market == Market.CN_FUTURES and vendor == DataVendor.AKSHARE:
            return cls._to_akshare_cn_futures(symbol)

        # CN futures — Tushare (returns unchanged; Tushare has no futures endpoint)
        # The UNSUPPORTED_COMBOS check above prevents this path for unsupported combos,
        # but for existing code that passes concrete contracts, return as-is.
        if market == Market.CN_FUTURES and vendor == DataVendor.TUSHARE:
            return symbol

        # A-share — AKShare Sina format (sh/sz prefix)
        if market == Market.CN_STOCK and vendor == DataVendor.AKSHARE:
            return cls._to_akshare_a_share(symbol)

        # A-share — Tushare (keep suffix)
        if market == Market.CN_STOCK and vendor == DataVendor.TUSHARE:
            return symbol

        # A-share ETF — AKShare Sina ETF format (same prefix as A-share)
        if market == Market.CN_ETF and vendor == DataVendor.AKSHARE:
            return cls._to_akshare_a_share(symbol)

        # US equity — yfinance strips .US
        if market == Market.US_STOCK and vendor == DataVendor.YAHOO_FINANCE:
            return cls._to_yfinance_symbol(symbol)

        # US equity — TqSdk unsupported
        if market == Market.US_STOCK and vendor == DataVendor.TQSDK:
            raise ValueError(f"Unsupported: {market.name} + {vendor.name}")

        # HK equity — AKShare (five-digit numeric, no .HK)
        if market == Market.HK_STOCK and vendor == DataVendor.AKSHARE:
            return cls._to_akshare_hk(symbol)

        # HK equity — yfinance (.HK format)
        if market == Market.HK_STOCK and vendor == DataVendor.YAHOO_FINANCE:
            return cls._to_yfinance_hk(symbol)

        # US futures — AKShare (strip =F)
        if market == Market.US_FUTURES and vendor == DataVendor.AKSHARE:
            return cls._to_akshare_us_futures(symbol)

        # US futures — Databento (continuous format)
        if market == Market.US_FUTURES and vendor == DataVendor.DATABENTO:
            return cls._to_databento_format(symbol)

        # US futures — yfinance (pass through with C→ZC mapping)
        if market == Market.US_FUTURES and vendor == DataVendor.YAHOO_FINANCE:
            return cls._to_yahoo_futures_format(symbol)

        # Forex — AKShare (pass through)
        if vendor == DataVendor.AKSHARE:
            # AKShare handles forex pairs like EURUSD directly
            return symbol.upper()

        # Crypto — OKX (hyphen passthrough, uppercase)
        if vendor == DataVendor.OKX:
            return symbol.replace("/", "-").upper()

        # Crypto — CCXT (slash vendor format)
        if vendor == DataVendor.CCXT:
            return symbol.replace("-", "/").upper()

        # Default: pass through
        return symbol

    @classmethod
    def _to_akshare_a_share(cls, symbol: str) -> str:
        """Convert A-share/ETF canonical to AKShare Sina format.

        Examples:
            600036.SH -> sh600036
            000001.SZ -> sz000001
            518880.SH -> sh518880
            159915.SZ -> sz159915
            830946.BJ -> bj830946
        """
        parts = symbol.upper().split(".")
        code = parts[0]
        suffix = parts[1] if len(parts) > 1 else "SH"

        # Map exchange suffix to Sina prefix
        prefix_map = {"SH": "sh", "SZ": "sz", "BJ": "bj"}
        prefix = prefix_map.get(suffix, "sh")
        return f"{prefix}{code}"

    @classmethod
    def _to_akshare_hk(cls, symbol: str) -> str:
        """Convert HK equity canonical to AKShare format.

        Examples:
            00700.HK -> 00700
            0700.HK -> 00700
        """
        # Normalize to 5-digit, strip .HK
        normalized = cls.normalize_canonical_symbol(symbol)
        if normalized.endswith(".HK"):
            return normalized[:-3]  # Strip .HK
        return normalized.zfill(5)

    @classmethod
    def _to_akshare_us_futures(cls, symbol: str) -> str:
        """Convert US futures canonical to AKShare format.

        Examples:
            GC=F -> GC
            CL=F -> CL
            SI=F -> SI
        """
        return symbol.upper().replace("=F", "").replace("=P", "")

    @classmethod
    def _to_akshare_cn_futures(cls, symbol: str) -> str:
        """Convert CN futures main continuous to AKShare format.

        Examples:
            rb0 -> RB0
            al0 -> AL0
        """
        lower = symbol.lower()
        if lower in cls.AKSHARE_CN_FUTURES_MAP:
            return cls.AKSHARE_CN_FUTURES_MAP[lower]
        # Fallback: uppercase and strip trailing 0
        base = symbol.upper().rstrip("0")
        if not base:
            base = symbol.upper()
        return base

    @classmethod
    def _to_yfinance_symbol(cls, symbol: str) -> str:
        """Convert US equity canonical to yfinance format.

        Examples:
            AAPL.US -> AAPL
            TSLA.US -> TSLA
        """
        upper = symbol.strip().upper()
        if upper.endswith(".US"):
            return upper[:-3]
        if upper.endswith(".HK"):
            # HK: preserve or zero-pad
            digits = upper[:-3]
            return f"{digits.zfill(5)}.HK"
        # Futures pass through
        return upper

    @classmethod
    def _to_yfinance_hk(cls, symbol: str) -> str:
        """Convert HK equity canonical to yfinance format.

        Examples:
            00700.HK -> 00700.HK (5-digit with .HK)
            0700.HK -> 00700.HK (normalized)
        """
        normalized = cls.normalize_canonical_symbol(symbol)
        # yfinance accepts .HK with 4+ digits
        return normalized  # Already normalized to 5-digit .HK

    @classmethod
    def _to_yahoo_futures_format(cls, symbol: str) -> str:
        """Convert US futures canonical to Yahoo Finance format.

        Examples:
            GC=F -> GC=F
            C=F -> ZC=F (CBOT corn mapping)
        """
        if "=" in symbol:
            base = symbol.split("=")[0]
        else:
            base = symbol

        mapped = cls.YAHOO_FUTURES_MAP.get(base)
        if mapped:
            return f"{mapped}=F"
        return symbol

    @classmethod
    def _to_databento_format(cls, symbol: str) -> str:
        """Convert US futures canonical to Databento continuous format.

        Examples:
            GC=F -> GC.c.0
            CL=F -> CL.c.0
        """
        if "=" in symbol:
            base = symbol.split("=")[0]
        else:
            base = symbol

        return cls.DATABENTO_FUTURES_MAP.get(base, f"{base}.c.0")

    @classmethod
    def _to_tqsdk_format(cls, symbol: str) -> str:
        """Convert CN futures canonical to TqSdk format.

        Examples:
            rb0 -> KQ.m@SHFE.rb (main continuous)
            al0 -> KQ.m@SHFE.al
            ag0 -> KQ.m@SHFE.ag
            if0 -> KQ.m@CFFEX.IF
            IF2406 -> CFFEX.IF2406 (concrete contract)
            rb2410 -> SHFE.rb2410 (concrete contract with year-month)
        """
        # Extract base product code (letters only)
        base = "".join(filter(str.isalpha, symbol))
        exchange = cls.TQSDK_EXCHANGE_MAP.get(
            base.upper(),
            cls.TQSDK_EXCHANGE_MAP.get(base.lower(), "SHFE")
        )

        # Determine if it's a main continuous or concrete contract
        # Main continuous: symbol is just the base + trailing 0 (e.g., rb0, al0, ag0, if0)
        # Concrete: has additional digits between base and trailing 0 (e.g., rb2410, RB2405)
        # Detection: count numeric characters after the base
        suffix = symbol[len(base):]  # Everything after the letters
        has_additional_digits = len([c for c in suffix if c.isdigit() and c != '0']) > 0

        if has_additional_digits or suffix.startswith(('1','2','3','4','5','6','7','8','9')):
            # Concrete contract: no KQ.m@ prefix
            if exchange in {"CFFEX", "CZCE"}:
                return f"{exchange}.{symbol.upper()}"
            return f"{exchange}.{symbol.lower()}"

        # Main continuous contract (e.g., rb0, al0)
        if exchange in {"CFFEX", "CZCE"}:
            return f"KQ.m@{exchange}.{base.upper()}"
        return f"KQ.m@{exchange}.{base.lower()}"

    @classmethod
    def is_supported_by_vendor(cls, symbol: str, vendor: DataVendor, market: Market) -> bool:
        """Check if a symbol/vendor/market combination is supported.

        Deprecated: Use translate() which returns TranslationResult with explicit supported flag.
        """
        result = cls.translate(symbol, vendor, market)
        return result.supported
