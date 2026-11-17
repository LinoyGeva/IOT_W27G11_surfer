package org.aerovision.hub.garmin

import org.junit.Assert.*
import org.junit.Test

/** No radio or sleeps: the fake BLE port and clock drive production logic. */
class GarminSessionTest {
    private class Clock : HrClock {
        var now = 0L
        override fun monotonicMs() = now
        override fun utcMs() = 1_800_000_000_000L + now
    }
    private class Ble : HrBleTransport {
        val calls = mutableListOf<String>()
        val listeners = mutableListOf<HrBleTransport.Listener>()
        var discovered: ((HrDevice) -> Unit)? = null
        override fun scan(onFound: (HrDevice) -> Unit, onFailure: (String) -> Unit) {
            calls += "scan"
            discovered = onFound
        }
        override fun stopScan() { calls += "stopScan" }
        override fun connect(device: HrDevice, listener: HrBleTransport.Listener) {
            calls += "connect:${device.address}"
            listeners += listener
        }
        override fun discoverServices() { calls += "discover" }
        override fun subscribeHeartRate() { calls += "subscribe" }
        override fun close() { calls += "close" }
    }
    private val ble = Ble()
    private val clock = Clock()
    private val session = GarminSession(ble, clock, "synthetic-run")
    private val band = HrDevice("AA:BB:CC:DD:EE:01", "synthetic HR band")

    private fun subscribed(): HrBleTransport.Listener {
        session.select(band)
        return ble.listeners.last().also {
            it.onConnected()
            it.onServicesAvailable(true)
            it.onSubscribed()
        }
    }

    @Test fun scanningListsDevicesWithoutConnectingAndDeduplicatesAddresses() {
        session.scan()
        ble.discovered!!(band)
        ble.discovered!!(band.copy(name = "updated name"))
        assertEquals(1, session.snapshot().devices.size)
        assertEquals("updated name", session.snapshot().devices.single().name)
        assertFalse(ble.calls.any { it.startsWith("connect:") })
    }

    @Test fun servicesAndSubscriptionMustCompleteBeforeAcceptingData() {
        session.select(band)
        val callback = ble.listeners.last()
        callback.onPacket(byteArrayOf(0, 72))
        assertNull(session.snapshot().reading)
        callback.onConnected()
        assertEquals(SessionPhase.DISCOVERING, session.snapshot().phase)
        assertEquals("discover", ble.calls.last())
        callback.onServicesAvailable(true)
        assertEquals(SessionPhase.SUBSCRIBING, session.snapshot().phase)
        assertEquals("subscribe", ble.calls.last())
        callback.onSubscribed()
        assertEquals(SessionPhase.WAITING, session.snapshot().phase)
        assertNull(session.snapshot().reading)
        callback.onPacket(byteArrayOf(0, 72))
        assertEquals(72, session.snapshot().reading!!.measurement.bpm)
        assertEquals(SessionPhase.STREAMING, session.snapshot().phase)
    }

    @Test fun measurementHasReceptionClockIdentitySequenceAndLiveMode() {
        val callback = subscribed()
        clock.now = 100
        callback.onPacket(byteArrayOf(0, 72))
        val first = session.snapshot().reading!!
        assertEquals("live", first.inputMode)
        assertEquals("synthetic-run", first.runId)
        assertEquals(band.address, first.deviceAddress)
        assertEquals(1L, first.sequence)
        assertEquals(100L, first.receivedMonotonicMs)
        assertEquals(clock.utcMs(), first.receivedUtcMs)
        callback.onPacket(byteArrayOf(0, 73))
        assertEquals(2L, session.snapshot().reading!!.sequence)
    }

    @Test fun malformedDataDoesNotRefreshAnOldMeasurement() {
        val callback = subscribed()
        callback.onPacket(byteArrayOf(0, 72))
        clock.now = 4_000
        callback.onPacket(byteArrayOf(1))
        assertNotNull(session.snapshot().lastError)
        clock.now = 5_000
        session.tick()
        assertEquals(SessionPhase.STALE, session.snapshot().phase)
        assertNull(session.snapshot().reading)
    }

    @Test fun disconnectClearsReadingThenReconnectsWithNewIdentityAndIgnoresOldCallbacks() {
        val old = subscribed()
        old.onPacket(byteArrayOf(0, 72))
        val connection = session.snapshot().reading!!.connectionId
        old.onDisconnected("link lost")
        assertEquals(SessionPhase.RETRYING, session.snapshot().phase)
        assertNull(session.snapshot().reading)
        clock.now = 1_999
        session.tick()
        assertEquals(1, ble.listeners.size)
        clock.now = 2_000
        session.tick()
        assertEquals(2, ble.listeners.size)
        old.onPacket(byteArrayOf(0, 99))
        old.onDisconnected("late callback")
        assertEquals(SessionPhase.CONNECTING, session.snapshot().phase)
        val fresh = ble.listeners.last()
        fresh.onConnected()
        fresh.onServicesAvailable(true)
        fresh.onSubscribed()
        fresh.onPacket(byteArrayOf(0, 74))
        val reading = session.snapshot().reading!!
        assertNotEquals(connection, reading.connectionId)
        assertEquals(1L, reading.sequence)
        assertEquals(74, reading.measurement.bpm)
    }

    @Test fun missingServicesAndFailedSubscriptionCannotBeStreaming() {
        session.select(band)
        val callback = ble.listeners.last()
        callback.onConnected()
        callback.onServicesAvailable(false)
        assertEquals(SessionPhase.RETRYING, session.snapshot().phase)
        assertFalse(ble.calls.contains("subscribe"))
        assertNull(session.snapshot().reading)
    }

    @Test fun failedCccdWriteAndLateSuccessCannotBecomeStreaming() {
        session.select(band)
        val callback = ble.listeners.last()
        callback.onConnected()
        callback.onServicesAvailable(true)
        callback.onFailure("CCCD write denied")
        callback.onSubscribed()
        callback.onPacket(byteArrayOf(0, 99))
        assertEquals(SessionPhase.RETRYING, session.snapshot().phase)
        assertNull(session.snapshot().reading)
    }

    @Test fun repeatedSelectionAndDuplicateCallbacksDoNotSubscribeTwice() {
        val callback = subscribed()
        session.select(band)
        callback.onConnected()
        callback.onServicesAvailable(true)
        callback.onSubscribed()
        assertEquals(1, ble.listeners.size)
        assertEquals(1, ble.calls.count { it == "subscribe" })
    }

    @Test fun eachConnectionPhaseAndSilentStreamHasTimeout() {
        session.select(band)
        clock.now = 10_000
        session.tick()
        assertEquals(SessionPhase.RETRYING, session.snapshot().phase)
        clock.now = 12_000
        session.tick()
        val callback = ble.listeners.last()
        callback.onConnected()
        callback.onServicesAvailable(true)
        callback.onSubscribed()
        clock.now = 22_000
        session.tick()
        assertEquals(SessionPhase.RETRYING, session.snapshot().phase)
    }

    @Test fun stoppingCancelsRecoveryAndRejectsLateData() {
        val callback = subscribed()
        callback.onDisconnected("link lost")
        session.stop()
        clock.now = 100_000
        session.tick()
        callback.onPacket(byteArrayOf(0, 99))
        assertEquals(1, ble.listeners.size)
        assertEquals(SessionPhase.STOPPED, session.snapshot().phase)
        assertNull(session.snapshot().reading)
    }
}
