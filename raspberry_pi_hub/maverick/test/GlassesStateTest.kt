package com.aerovision.hub.maverick

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class GlassesStateTest {

    private fun connectedReady() = GlassesState()
        .reduce(GlassesEvent.Connecting("Maverick"))
        .reduce(GlassesEvent.Connected(null))
        .reduce(GlassesEvent.Ready)
        .reduce(GlassesEvent.Battery(80))

    @Test
    fun connectKeepsDeviceNameWhenSdkReportsNone() {
        val state = connectedReady()
        assertEquals(GlassesLink.CONNECTED, state.link)
        assertEquals("Maverick", state.deviceName)
        assertTrue(state.ready)
        assertEquals(80, state.batteryPercent)
    }

    @Test
    fun disconnectClearsLinkDependentValues() {
        val state = connectedReady().reduce(GlassesEvent.Disconnected)
        assertEquals(GlassesLink.DISCONNECTED, state.link)
        assertFalse(state.ready)
        assertNull(state.batteryPercent)
    }

    @Test
    fun failedConnectionClearsLinkDependentValues() {
        val state = connectedReady().reduce(GlassesEvent.FailedToConnect)
        assertEquals(GlassesLink.FAILED, state.link)
        assertFalse(state.ready)
        assertNull(state.batteryPercent)
    }

    @Test
    fun bluetoothOffActsAsDisconnect() {
        val state = connectedReady().reduce(GlassesEvent.AdapterChanged(false))
        assertEquals(false, state.bluetoothEnabled)
        assertEquals(GlassesLink.DISCONNECTED, state.link)
        assertFalse(state.ready)
        assertNull(state.batteryPercent)
    }

    @Test
    fun batteryIgnoredWhileNotConnected() {
        val state = GlassesState().reduce(GlassesEvent.Battery(50))
        assertNull(state.batteryPercent)
    }

    @Test
    fun batteryIsClampedToPercentRange() {
        assertEquals(100, connectedReady().reduce(GlassesEvent.Battery(130)).batteryPercent)
    }

    @Test
    fun errorPersistsUntilNextSuccessfulStep() {
        val failed = GlassesState().reduce(GlassesEvent.Error("AUTH: bad key"))
        assertEquals("AUTH: bad key", failed.lastError)
        assertNull(failed.reduce(GlassesEvent.Connecting(null)).lastError)
    }
}
