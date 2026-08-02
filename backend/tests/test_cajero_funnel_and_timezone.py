import unittest
from datetime import datetime, timezone, timedelta

def _iso_to_ar_date_str(iso_str: str) -> str:
    """Convierte un timestamp ISO (UTC, Z, offset o sin tz) a la fecha corta YYYY-MM-DD
    en la zona horaria local de Argentina (UTC-3)."""
    if not iso_str:
        return ""
    try:
        s = str(iso_str).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ar_dt = dt.astimezone(timezone(timedelta(hours=-3)))
        return ar_dt.strftime("%Y-%m-%d")
    except Exception:
        return str(iso_str)[:10]

def _finanzas_range_utc_bounds(start_iso: str, end_iso: str) -> tuple:
    start_d = datetime.fromisoformat(start_iso).date()
    end_d = datetime.fromisoformat(end_iso).date()
    start_utc = datetime(start_d.year, start_d.month, start_d.day, 3, 0, 0, tzinfo=timezone.utc)
    end_next = end_d + timedelta(days=1)
    end_utc = datetime(end_next.year, end_next.month, end_next.day, 2, 59, 59, 999000, tzinfo=timezone.utc)
    return start_utc.isoformat(), end_utc.isoformat()

class TestCajeroFunnelAndTimezone(unittest.TestCase):
    def test_iso_to_ar_date_str_conversion(self):
        # 2026-08-02T01:30:00Z UTC -> 2026-08-01 22:30:00 ART (UTC-3)
        utc_late_night = "2026-08-02T01:30:00.000Z"
        ar_date = _iso_to_ar_date_str(utc_late_night)
        self.assertEqual(ar_date, "2026-08-01", f"Expected 2026-08-01 but got {ar_date}")

        # 2026-08-02T15:00:00+00:00 -> 2026-08-02 12:00:00 ART (UTC-3)
        utc_day = "2026-08-02T15:00:00+00:00"
        ar_date_day = _iso_to_ar_date_str(utc_day)
        self.assertEqual(ar_date_day, "2026-08-02", f"Expected 2026-08-02 but got {ar_date_day}")

        # Naive ISO string fallback/handling
        naive_iso = "2026-08-02 20:00:00"
        self.assertEqual(_iso_to_ar_date_str(naive_iso), "2026-08-02")

    def test_finanzas_range_utc_bounds(self):
        start_iso = "2026-08-01"
        end_iso = "2026-08-01"
        start_utc, end_utc = _finanzas_range_utc_bounds(start_iso, end_iso)
        self.assertIn("2026-08-01T03:00:00", start_utc)
        self.assertIn("2026-08-02T02:59:59", end_utc)

if __name__ == "__main__":
    unittest.main()
