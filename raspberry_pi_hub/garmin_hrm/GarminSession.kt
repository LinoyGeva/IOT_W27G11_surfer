package org.aerovision.hub.garmin

data class HrDevice(val address: String, val name: String?)

interface HrClock {
    fun monotonicMs(): Long
    fun utcMs(): Long
}

/** Android callbacks are marshalled to the owning main thread by the adapter. */
interface HrBleTransport {
    fun scan(onFound: (HrDevice) -> Unit, onFailure: (String) -> Unit)
    fun stopScan()
    fun connect(device: HrDevice, listener: Listener)
    fun discoverServices()
    fun subscribeHeartRate()
    fun close()

    interface Listener {
        fun onConnected()
        fun onServicesAvailable(supported: Boolean)
        fun onSubscribed()
        fun onPacket(packet: ByteArray)
        fun onDisconnected(reason: String)
        fun onFailure(reason: String)
    }
}

enum class SessionPhase { IDLE, SCANNING, CONNECTING, DISCOVERING, SUBSCRIBING, WAITING, STREAMING, STALE, RETRYING, STOPPED }

data class GarminReading(
    val runId: String,
    val connectionId: Long,
    val sequence: Long,
    val deviceAddress: String,
    val receivedUtcMs: Long,
    val receivedMonotonicMs: Long,
    val measurement: HeartRateMeasurement,
    val rawHex: String,
    val inputMode: String = "live",
)

data class GarminSnapshot(
    val phase: SessionPhase,
    val devices: List<HrDevice>,
    val selected: HrDevice?,
    val reading: GarminReading?,
    val receiveAgeMs: Long?,
    val lastError: String?,
)

/**
 * Production connection/freshness logic, testable with a fake BLE port and clock.
 * Single-thread confined. tick() is driven by the hub; no Android classes/sleeps.
 * Timings are receiver policy, not a claim about sensor latency or accuracy.
 */
class GarminSession(
    private val ble: HrBleTransport,
    private val clock: HrClock,
    private val runId: String,
    private val onChanged: (GarminSnapshot) -> Unit = {},
) {
    private var phase = SessionPhase.IDLE
    private val devices = linkedMapOf<String, HrDevice>()
    private var target: HrDevice? = null
    private var reading: GarminReading? = null
    private var error: String? = null
    private var generation = 0L
    private var connectionId = 0L
    private var sequence = 0L
    private var deadline = 0L
    private var subscribedAt = 0L

    fun snapshot(): GarminSnapshot {
        val age = reading?.let { (clock.monotonicMs() - it.receivedMonotonicMs).coerceAtLeast(0) }
        val fresh = age != null && age < 5_000 && phase == SessionPhase.STREAMING
        val visiblePhase = if (phase == SessionPhase.STREAMING && !fresh) SessionPhase.STALE else phase
        return GarminSnapshot(visiblePhase, devices.values.toList(), target,
            if (fresh) reading else null, age, error)
    }

    private fun publish() = onChanged(snapshot())

    fun scan() {
        generation++
        ble.stopScan()
        ble.close()
        target = null
        reading = null
        error = null
        devices.clear()
        phase = SessionPhase.SCANNING
        deadline = clock.monotonicMs() + 10_000
        val token = generation
        publish()
        ble.scan({ device ->
            if (token == generation && phase == SessionPhase.SCANNING) {
                devices[device.address] = device
                publish()
            }
        }, { reason ->
            if (token == generation && phase == SessionPhase.SCANNING) {
                generation++
                ble.stopScan()
                error = reason
                phase = SessionPhase.IDLE
                publish()
            }
        })
    }

    fun select(device: HrDevice) {
        if (target?.address == device.address && phase !in setOf(SessionPhase.STOPPED, SessionPhase.IDLE, SessionPhase.SCANNING)) return
        target = device
        connect()
    }

    private fun connect() {
        val device = target ?: return
        generation++
        val token = generation
        ble.stopScan()
        ble.close()
        connectionId++
        sequence = 0
        reading = null
        error = null
        phase = SessionPhase.CONNECTING
        deadline = clock.monotonicMs() + 10_000
        publish()
        ble.connect(device, object : HrBleTransport.Listener {
            override fun onConnected() {
                if (token != generation || phase != SessionPhase.CONNECTING) return
                phase = SessionPhase.DISCOVERING
                deadline = clock.monotonicMs() + 10_000
                publish()
                ble.discoverServices()
            }
            override fun onServicesAvailable(supported: Boolean) {
                if (token != generation || phase != SessionPhase.DISCOVERING) return
                if (!supported) { fail("Heart Rate Service, notifying measurement or CCCD missing"); return }
                phase = SessionPhase.SUBSCRIBING
                deadline = clock.monotonicMs() + 10_000
                publish()
                ble.subscribeHeartRate()
            }
            override fun onSubscribed() {
                if (token != generation || phase != SessionPhase.SUBSCRIBING) return
                phase = SessionPhase.WAITING
                subscribedAt = clock.monotonicMs()
                publish()
            }
            override fun onPacket(packet: ByteArray) {
                if (token != generation || phase !in setOf(SessionPhase.WAITING, SessionPhase.STREAMING, SessionPhase.STALE)) return
                val measurement = try { HeartRateDecoder.decode(packet) }
                    catch (bad: IllegalArgumentException) { error = bad.message; publish(); return }
                sequence++
                reading = GarminReading(runId, connectionId, sequence, device.address,
                    clock.utcMs(), clock.monotonicMs(), measurement,
                    packet.joinToString("") { "%02x".format(it.toInt() and 0xff) })
                phase = SessionPhase.STREAMING
                error = null
                publish()
            }
            override fun onDisconnected(reason: String) { if (token == generation) fail(reason) }
            override fun onFailure(reason: String) { if (token == generation) fail(reason) }
        })
    }

    private fun fail(reason: String) {
        generation++ // Invalidate callbacks before close can deliver a final event.
        ble.close()
        reading = null
        error = reason
        phase = SessionPhase.RETRYING
        deadline = clock.monotonicMs() + 2_000
        publish()
    }

    fun tick() {
        val now = clock.monotonicMs()
        when (phase) {
            SessionPhase.SCANNING -> if (now >= deadline) { ble.stopScan(); phase = SessionPhase.IDLE }
            SessionPhase.CONNECTING, SessionPhase.DISCOVERING, SessionPhase.SUBSCRIBING ->
                if (now >= deadline) fail("Timeout during ${phase.name.lowercase()}")
            SessionPhase.RETRYING -> if (now >= deadline) connect()
            SessionPhase.WAITING, SessionPhase.STREAMING, SessionPhase.STALE -> {
                val last = reading?.receivedMonotonicMs ?: subscribedAt
                if (now - last >= 10_000) fail("Connected but no valid heart-rate measurements")
                else if (reading != null && now - last >= 5_000) phase = SessionPhase.STALE
            }
            else -> Unit
        }
        publish()
    }

    fun stop() {
        generation++
        target = null
        ble.stopScan()
        ble.close()
        reading = null
        phase = SessionPhase.STOPPED
        publish()
    }
}
