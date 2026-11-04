"""Country -> currency / language defaults.

The mobile app sends the ISO country it detected from GPS (reverse geocode);
if it does not, we fall back to CDN country headers, then Accept-Language.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

SUPPORTED_LANGUAGES = ["en", "ur", "ar", "hi", "es"]
RTL_LANGUAGES = {"ur", "ar"}

# country: (currency, primary language)
COUNTRIES: dict[str, tuple[str, str]] = {
    "PK": ("PKR", "ur"), "IN": ("INR", "hi"), "BD": ("BDT", "en"), "LK": ("LKR", "en"), "NP": ("NPR", "hi"),
    "AF": ("AFN", "en"),
    "AE": ("AED", "ar"), "SA": ("SAR", "ar"), "QA": ("QAR", "ar"), "KW": ("KWD", "ar"), "BH": ("BHD", "ar"),
    "OM": ("OMR", "ar"), "JO": ("JOD", "ar"), "EG": ("EGP", "ar"), "IQ": ("IQD", "ar"), "LB": ("LBP", "ar"),
    "MA": ("MAD", "ar"), "DZ": ("DZD", "ar"), "TN": ("TND", "ar"), "LY": ("LYD", "ar"), "SY": ("SYP", "ar"),
    "YE": ("YER", "ar"), "SD": ("SDG", "ar"),
    "US": ("USD", "en"), "CA": ("CAD", "en"), "GB": ("GBP", "en"), "IE": ("EUR", "en"), "AU": ("AUD", "en"),
    "NZ": ("NZD", "en"), "ZA": ("ZAR", "en"), "NG": ("NGN", "en"), "KE": ("KES", "en"), "GH": ("GHS", "en"),
    "SG": ("SGD", "en"), "MY": ("MYR", "en"), "PH": ("PHP", "en"), "HK": ("HKD", "en"),
    "ES": ("EUR", "es"), "MX": ("MXN", "es"), "AR": ("ARS", "es"), "CO": ("COP", "es"), "CL": ("CLP", "es"),
    "PE": ("PEN", "es"), "VE": ("VES", "es"), "EC": ("USD", "es"), "UY": ("UYU", "es"), "PY": ("PYG", "es"),
    "BO": ("BOB", "es"), "CR": ("CRC", "es"), "PA": ("PAB", "es"), "DO": ("DOP", "es"), "GT": ("GTQ", "es"),
    "DE": ("EUR", "en"), "FR": ("EUR", "en"), "IT": ("EUR", "en"), "NL": ("EUR", "en"), "BE": ("EUR", "en"),
    "PT": ("EUR", "en"), "AT": ("EUR", "en"), "FI": ("EUR", "en"), "GR": ("EUR", "en"), "SE": ("SEK", "en"),
    "NO": ("NOK", "en"), "DK": ("DKK", "en"), "CH": ("CHF", "en"), "PL": ("PLN", "en"), "CZ": ("CZK", "en"),
    "TR": ("TRY", "en"), "RU": ("RUB", "en"), "UA": ("UAH", "en"), "BR": ("BRL", "en"), "JP": ("JPY", "en"),
    "KR": ("KRW", "en"), "CN": ("CNY", "en"), "ID": ("IDR", "en"), "TH": ("THB", "en"), "VN": ("VND", "en"),
    "IR": ("IRR", "en"), "KZ": ("KZT", "en"), "AZ": ("AZN", "en"), "UZ": ("UZS", "en"),
}

# Currencies with no minor unit in everyday use (prices shown without decimals).
ZERO_DECIMAL = {"PKR", "INR", "JPY", "KRW", "IDR", "VND", "CLP", "PYG", "COP", "IQD", "LBP", "IRR", "UZS",
                "NGN", "BDT", "LKR", "NPR", "HUF", "KZT", "SYP", "YER", "AFN"}

DEFAULT_COUNTRY = "US"


@dataclass
class LocaleInfo:
    country_code: str
    currency: str
    language: str
    rtl: bool
    currency_decimals: int
    supported_languages: list[str]
    detected_from: str

    def to_dict(self) -> dict:
        return asdict(self)


def locale_for(country: str | None, preferred_language: str | None = None, source: str = "country") -> LocaleInfo:
    cc = (country or "").upper()
    if cc not in COUNTRIES:
        cc, source = DEFAULT_COUNTRY, "default"
    currency, lang = COUNTRIES[cc]
    if preferred_language and preferred_language[:2].lower() in SUPPORTED_LANGUAGES:
        lang = preferred_language[:2].lower()
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"
    return LocaleInfo(
        country_code=cc,
        currency=currency,
        language=lang,
        rtl=lang in RTL_LANGUAGES,
        currency_decimals=0 if currency in ZERO_DECIMAL else 2,
        supported_languages=SUPPORTED_LANGUAGES,
        detected_from=source,
    )


def country_from_headers(headers) -> tuple[str | None, str]:
    for h in ("cf-ipcountry", "x-vercel-ip-country", "cloudfront-viewer-country", "x-country-code"):
        v = headers.get(h)
        if v and len(v) == 2 and v.upper() != "XX":
            return v.upper(), "ip"
    al = headers.get("accept-language", "")
    for part in al.split(","):
        tag = part.split(";")[0].strip()
        if "-" in tag:
            region = tag.split("-")[-1]
            if len(region) == 2:
                return region.upper(), "accept_language"
    return None, "default"
