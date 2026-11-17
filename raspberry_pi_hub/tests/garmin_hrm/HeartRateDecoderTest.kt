package org.aerovision.hub.garmin

import org.junit.Assert.*
import org.junit.Test

/** Synthetic protocol fixtures; these tests exercise the production decoder. */
class HeartRateDecoderTest {
    private fun hex(value: String) = value.split(" ").filter { it.isNotBlank() }
        .map { it.toInt(16).toByte() }.toByteArray()

    @Test fun eightBitBpmAndAbsentFields() {
        val value = HeartRateDecoder.decode(hex("00 48"))
        assertEquals(72, value.bpm)
        assertNull(value.contactDetected)
        assertNull(value.energyExpendedKj)
        assertTrue(value.rrIntervalsMs.isEmpty())
    }

    @Test fun unsignedEightBitBpmIsNotNegative() {
        assertEquals(200, HeartRateDecoder.decode(hex("00 c8")).bpm)
    }

    @Test fun littleEndianSixteenBitBpmAndOptionalFields() {
        val value = HeartRateDecoder.decode(hex("1f 2c 01 0a 00 00 04 00 02"))
        assertEquals(300, value.bpm)
        assertEquals(true, value.contactDetected)
        assertEquals(10, value.energyExpendedKj)
        assertEquals(listOf(1000.0, 500.0), value.rrIntervalsMs)
    }

    @Test fun supportedContactCanBeAbsent() {
        assertEquals(false, HeartRateDecoder.decode(hex("04 48")).contactDetected)
    }

    @Test fun noContactSupportDoesNotInventContactStatus() {
        assertNull(HeartRateDecoder.decode(hex("02 48")).contactDetected)
    }

    @Test fun formatCanChangeBetweenNotifications() {
        assertEquals(72, HeartRateDecoder.decode(hex("00 48")).bpm)
        assertEquals(300, HeartRateDecoder.decode(hex("01 2c 01")).bpm)
        assertEquals(0, HeartRateDecoder.decode(hex("00 00")).bpm)
    }

    @Test fun rrFlagWithNoIntervalsIsAllowedByVariableLengthField() {
        assertTrue(HeartRateDecoder.decode(hex("10 48")).rrIntervalsMs.isEmpty())
    }

    @Test fun fractionalRrUnitsAndUnsignedSixteenBitBoundaryArePreserved() {
        assertEquals(listOf(1000.0 / 1024.0), HeartRateDecoder.decode(hex("10 48 01 00")).rrIntervalsMs)
        assertEquals(65535, HeartRateDecoder.decode(hex("01 ff ff")).bpm)
    }

    @Test fun malformedAndTrailingBytesAreRejected() {
        for (packet in listOf("", "00", "01 48", "08 48 01", "10 48 00", "00 48 00")) {
            assertThrows("packet=$packet", IllegalArgumentException::class.java) {
                HeartRateDecoder.decode(hex(packet))
            }
        }
    }
}
