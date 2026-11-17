package org.aerovision.hub.garmin

data class HeartRateMeasurement(
    val flags: Int,
    val bpm: Int,
    val contactDetected: Boolean?,
    val energyExpendedKj: Int?,
    val rrIntervalsMs: List<Double>,
)

/** Bluetooth SIG Heart Rate Measurement (2A37), independent of Android/radio. */
object HeartRateDecoder {
    fun decode(packet: ByteArray): HeartRateMeasurement {
        require(packet.isNotEmpty()) { "Missing heart-rate flags" }
        val flags = packet[0].toInt() and 0xff
        var offset = 1
        fun unsigned(bytes: Int): Int {
            require(offset + bytes <= packet.size) { "Truncated heart-rate measurement" }
            var value = 0
            repeat(bytes) { index -> value = value or ((packet[offset++].toInt() and 0xff) shl (8 * index)) }
            return value
        }
        val bpm = unsigned(if (flags and 1 != 0) 2 else 1)
        val contact = if (flags and 4 != 0) flags and 2 != 0 else null
        val energy = if (flags and 8 != 0) unsigned(2) else null
        val intervals = mutableListOf<Double>()
        if (flags and 16 != 0) {
            while (offset < packet.size) intervals += unsigned(2) * 1000.0 / 1024.0
        }
        require(offset == packet.size) { "Unexpected trailing heart-rate bytes" }
        return HeartRateMeasurement(flags, bpm, contact, energy, intervals.toList())
    }
}
