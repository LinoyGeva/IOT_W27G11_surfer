"""Synthetic protocol examples only; these do not verify physical hardware."""

import unittest

from hr_diagnostic import decode_measurement


class DecodeTests(unittest.TestCase):
    def test_eight_bit_bpm_and_unsupported_contact(self):
        result = decode_measurement(bytes.fromhex("00 48"))
        self.assertEqual(result["heart_rate_bpm"], 72)
        self.assertIsNone(result["contact_detected"])

    def test_sixteen_bit_bpm_energy_and_multiple_rr_intervals(self):
        result = decode_measurement(bytes.fromhex("1f 2c 01 0a 00 00 04 00 02"))
        self.assertEqual(result["heart_rate_bpm"], 300)
        self.assertTrue(result["contact_detected"])
        self.assertEqual(result["energy_expended_kj"], 10)
        self.assertEqual(result["rr_intervals_ms"], [1000, 500])

    def test_supported_contact_not_detected(self):
        self.assertFalse(decode_measurement(bytes.fromhex("04 48"))["contact_detected"])

    def test_invalid_packets(self):
        for packet in ("", "00", "01 48", "08 48 01", "10 48", "10 48 00", "00 48 00"):
            with self.subTest(packet=packet), self.assertRaises(ValueError):
                decode_measurement(bytes.fromhex(packet))


if __name__ == "__main__":
    unittest.main()
