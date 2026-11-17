package com.aerovision.hub.maverick

import com.aerovision.hub.InputMode

enum class GlassesLink { IDLE, NOT_CONFIGURED, CONNECTING, CONNECTED, DISCONNECTED, FAILED }

/**
 * Snapshot of the glasses connection. Values that only hold while connected
 * ([ready], [batteryPercent]) are cleared on disconnect so stale data never looks current.
 */
data class GlassesState(
    val apiKeyBundled: Boolean = false,
    val bluetoothEnabled: Boolean? = null,
    val link: GlassesLink = GlassesLink.IDLE,
    val deviceName: String? = null,
    /** SDK authenticated the glasses and can render screens. */
    val ready: Boolean = false,
    val batteryPercent: Int? = null,
    val lastError: String? = null,
)

sealed interface GlassesEvent {
    data class KeyChecked(val bundled: Boolean) : GlassesEvent
    data class AdapterChanged(val enabled: Boolean) : GlassesEvent
    data object NotConfigured : GlassesEvent
    data class Connecting(val deviceName: String?) : GlassesEvent
    data class Connected(val deviceName: String?) : GlassesEvent
    data object Disconnected : GlassesEvent
    data object FailedToConnect : GlassesEvent
    data object Ready : GlassesEvent
    data object UnReady : GlassesEvent
    data class Battery(val percent: Int) : GlassesEvent
    data class Error(val description: String) : GlassesEvent
}

fun GlassesState.reduce(event: GlassesEvent): GlassesState = when (event) {
    is GlassesEvent.KeyChecked -> copy(apiKeyBundled = event.bundled)
    is GlassesEvent.AdapterChanged ->
        if (event.enabled) copy(bluetoothEnabled = true)
        else disconnected(GlassesLink.DISCONNECTED).copy(bluetoothEnabled = false)
    GlassesEvent.NotConfigured -> copy(link = GlassesLink.NOT_CONFIGURED)
    is GlassesEvent.Connecting ->
        copy(link = GlassesLink.CONNECTING, deviceName = event.deviceName ?: deviceName, lastError = null)
    is GlassesEvent.Connected ->
        copy(link = GlassesLink.CONNECTED, deviceName = event.deviceName ?: deviceName, lastError = null)
    GlassesEvent.Disconnected -> disconnected(GlassesLink.DISCONNECTED)
    GlassesEvent.FailedToConnect -> disconnected(GlassesLink.FAILED)
    GlassesEvent.Ready -> copy(ready = true, lastError = null)
    GlassesEvent.UnReady -> copy(ready = false)
    is GlassesEvent.Battery ->
        if (link == GlassesLink.CONNECTED) copy(batteryPercent = event.percent.coerceIn(0, 100)) else this
    is GlassesEvent.Error -> copy(lastError = event.description)
}

private fun GlassesState.disconnected(link: GlassesLink) =
    copy(link = link, ready = false, batteryPercent = null)

/**
 * Head orientation reported by the glasses' fused inertial sensors.
 *
 * [glassesTimestampMs] is the SDK's original timestamp (clock semantics not yet verified);
 * [receivedElapsedNanos] is the hub's monotonic clock (SystemClock.elapsedRealtimeNanos) at receipt.
 * Angle units follow the SDK's YprData and have not yet been verified on hardware.
 */
data class OrientationSample(
    val glassesTimestampMs: Long,
    val receivedElapsedNanos: Long,
    val yaw: Float,
    val pitch: Float,
    val roll: Float,
    val calibration: String,
    val inputMode: InputMode,
)
