import unittest
from support.protocols import hr


class GarminProtocolTests(unittest.TestCase):
    """Synthetic packets; checks the existing Python bench decoder."""

    def test_01_unsigned_bpm_formats_and_zero(self):
        for raw, bpm in [("0048", 72), ("00c8", 200), ("012c01", 300),
                         ("01ffff", 65535), ("0000", 0)]:
            with self.subTest(raw=raw):
                self.assertEqual(hr.decode_measurement(bytes.fromhex(raw))["heart_rate_bpm"], bpm)

    def test_02_all_optional_fields_and_units(self):
        self.assertEqual(hr.decode_measurement(bytes.fromhex("1f2c010a0000040002")), {
            "flags": 31, "heart_rate_bpm": 300, "contact_detected": True,
            "energy_expended_kj": 10, "rr_intervals_ms": [1000.0, 500.0]})

    def test_03_absent_fields_are_not_zero_or_false(self):
        value = hr.decode_measurement(bytes.fromhex("0048"))
        self.assertIsNone(value["contact_detected"])
        self.assertIsNone(value["energy_expended_kj"])
        self.assertEqual(value["rr_intervals_ms"], [])

    def test_04_contact_and_fractional_rr(self):
        self.assertFalse(hr.decode_measurement(bytes.fromhex("0448"))["contact_detected"])
        self.assertIsNone(hr.decode_measurement(bytes.fromhex("0248"))["contact_detected"])
        self.assertEqual(hr.decode_measurement(bytes.fromhex("10480100"))["rr_intervals_ms"], [1000 / 1024])

    def test_05_malformed_packets(self):
        for raw in ["", "00", "0148", "084801", "104800", "004800"]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                hr.decode_measurement(bytes.fromhex(raw))

    def test_06_changed_flags_do_not_reuse_old_optional_values(self):
        hr.decode_measurement(bytes.fromhex("1f2c010a0000040002"))
        value = hr.decode_measurement(bytes.fromhex("0000"))
        self.assertEqual(value["heart_rate_bpm"], 0)
        self.assertIsNone(value["energy_expended_kj"])
        self.assertIsNone(value["contact_detected"])
        self.assertEqual(value["rr_intervals_ms"], [])
