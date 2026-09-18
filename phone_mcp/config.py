"""
Global configuration file for storing configurable parameters
"""

from __future__ import annotations

import locale
import os
import re

# ISO 3166-1 alpha-2 → ITU-T E.164 country calling code
_COUNTRY_CALLING_CODES: dict[str, str] = {
    "AD": "+376", "AE": "+971", "AF": "+93", "AL": "+355", "AM": "+374",
    "AO": "+244", "AR": "+54", "AT": "+43", "AU": "+61", "AZ": "+994",
    "BA": "+387", "BD": "+880", "BE": "+32", "BG": "+359", "BH": "+973",
    "BI": "+257", "BJ": "+229", "BN": "+673", "BO": "+591", "BR": "+55",
    "BT": "+975", "BW": "+267", "BY": "+375", "BZ": "+501",
    "CA": "+1", "CD": "+243", "CF": "+236", "CG": "+242", "CH": "+41",
    "CI": "+225", "CL": "+56", "CM": "+237", "CN": "+86", "CO": "+57",
    "CR": "+506", "CU": "+53", "CV": "+238", "CY": "+357", "CZ": "+420",
    "DE": "+49", "DJ": "+253", "DK": "+45", "DO": "+1", "DZ": "+213",
    "EC": "+593", "EE": "+372", "EG": "+20", "EH": "+212", "ER": "+291",
    "ES": "+34", "ET": "+251",
    "FI": "+358", "FJ": "+679", "FO": "+298", "FR": "+33",
    "GA": "+241", "GB": "+44", "GE": "+995", "GF": "+594", "GH": "+233",
    "GI": "+350", "GL": "+299", "GM": "+220", "GN": "+224", "GP": "+590",
    "GQ": "+240", "GR": "+30", "GT": "+502", "GU": "+1", "GW": "+245",
    "GY": "+592",
    "HK": "+852", "HN": "+504", "HR": "+385", "HT": "+509", "HU": "+36",
    "ID": "+62", "IE": "+353", "IL": "+972", "IM": "+44", "IN": "+91",
    "IQ": "+964", "IR": "+98", "IS": "+354", "IT": "+39",
    "JE": "+44", "JM": "+1", "JO": "+962", "JP": "+81",
    "KE": "+254", "KG": "+996", "KH": "+855", "KM": "+269", "KP": "+850",
    "KR": "+82", "KW": "+965", "KY": "+1", "KZ": "+7",
    "LA": "+856", "LB": "+961", "LI": "+423", "LK": "+94", "LR": "+231",
    "LS": "+266", "LT": "+370", "LU": "+352", "LV": "+371", "LY": "+218",
    "MA": "+212", "MC": "+377", "MD": "+373", "ME": "+382", "MG": "+261",
    "MK": "+389", "ML": "+223", "MM": "+95", "MN": "+976", "MO": "+853",
    "MQ": "+596", "MR": "+222", "MT": "+356", "MU": "+230", "MV": "+960",
    "MW": "+265", "MX": "+52", "MY": "+60", "MZ": "+258",
    "NA": "+264", "NC": "+687", "NE": "+227", "NG": "+234", "NI": "+505",
    "NL": "+31", "NO": "+47", "NP": "+977", "NZ": "+64",
    "OM": "+968",
    "PA": "+507", "PE": "+51", "PF": "+689", "PG": "+675", "PH": "+63",
    "PK": "+92", "PL": "+48", "PR": "+1", "PS": "+970", "PT": "+351",
    "PY": "+595",
    "QA": "+974",
    "RE": "+262", "RO": "+40", "RS": "+381", "RU": "+7", "RW": "+250",
    "SA": "+966", "SC": "+248", "SD": "+249", "SE": "+46", "SG": "+65",
    "SI": "+386", "SK": "+421", "SL": "+232", "SM": "+378", "SN": "+221",
    "SO": "+252", "SR": "+597", "SS": "+211", "SV": "+503", "SY": "+963",
    "SZ": "+268",
    "TD": "+235", "TG": "+228", "TH": "+66", "TJ": "+992", "TL": "+670",
    "TM": "+993", "TN": "+216", "TO": "+676", "TR": "+90", "TT": "+1",
    "TW": "+886", "TZ": "+255",
    "UA": "+380", "UG": "+256", "UK": "+44", "US": "+1", "UY": "+598",
    "UZ": "+998",
    "VA": "+379", "VE": "+58", "VN": "+84", "VU": "+678",
    "WS": "+685",
    "XK": "+383",
    "YE": "+967", "YT": "+262",
    "ZA": "+27", "ZM": "+260", "ZW": "+263",
}

_LOCALE_REGION_RE = re.compile(
    r"^(?:[a-zA-Z]{2,3}|[a-zA-Z]{2,3})[_-]([A-Za-z]{2})\b"
)


def _normalize_calling_code(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if not value.startswith("+"):
        value = "+" + value
    return value


def _region_from_locale_string(value: str | None) -> str | None:
    """Extract ISO 3166-1 alpha-2 region from a locale string like cs_CZ.UTF-8."""
    if not value:
        return None
    for part in re.split(r"[:;]", value):
        part = part.strip()
        if not part or part in ("C", "POSIX"):
            continue
        # Drop encoding / modifier: cs_CZ.UTF-8@euro → cs_CZ
        part = part.split("@", 1)[0].split(".", 1)[0]
        match = _LOCALE_REGION_RE.match(part)
        if match:
            return match.group(1).upper()
        if re.fullmatch(r"[A-Za-z]{2}", part):
            return part.upper()
    return None


def detect_default_country_code() -> str:
    """Detect default calling code from env override or system locales.

    Priority:
      1. PHONE_COUNTRY_CODE environment variable (e.g. "+420" or "420")
      2. Region from LC_TELEPHONE / LC_ADDRESS / LC_ALL / LANG / LANGUAGE
      3. Region from Python locale.getlocale() / getdefaultlocale()
      4. Empty string (no automatic prefix) if nothing matches
    """
    override = os.environ.get("PHONE_COUNTRY_CODE", "").strip()
    if override:
        return _normalize_calling_code(override)

    candidates: list[str | None] = [
        os.environ.get("LC_TELEPHONE"),
        os.environ.get("LC_ADDRESS"),
        os.environ.get("LC_ALL"),
        os.environ.get("LANG"),
        os.environ.get("LANGUAGE"),
    ]

    try:
        loc = locale.getlocale()
        if loc and loc[0]:
            candidates.append(loc[0])
    except Exception:
        pass

    try:
        # Deprecated but still useful on older Python / odd setups
        getdefault = getattr(locale, "getdefaultlocale", None)
        if getdefault is not None:
            loc = getdefault()
            if loc and loc[0]:
                candidates.append(loc[0])
    except Exception:
        pass

    for candidate in candidates:
        region = _region_from_locale_string(candidate)
        if region and region in _COUNTRY_CALLING_CODES:
            return _COUNTRY_CALLING_CODES[region]

    return ""


# Default country/region code — derived from system locales (not hard-coded +86)
DEFAULT_COUNTRY_CODE = detect_default_country_code()

# Screenshot storage path (Android internal paths, not affected by host OS)
SCREENSHOT_PATH = "/sdcard/Pictures/Screenshots/"

# Screen recording storage path (Android internal paths, not affected by host OS)
RECORDING_PATH = "/sdcard/Movies/"

# Command execution timeout (seconds)
COMMAND_TIMEOUT = 30

# Whether to automatically retry connection
AUTO_RETRY_CONNECTION = True

# Maximum number of retry attempts
MAX_RETRY_COUNT = 3
