package com.aerovision.hub.maverick

import UIKit.app.data.CalibrationStatus
import UIKit.app.data.PowerButtonAction
import UIKit.app.data.YprData
import UIKit.services.AppErrorCode
import UIKit.services.IEvsAppEvents
import UIKit.services.IEvsCommunicationEvents
import UIKit.services.IEvsGlassesEvents
import UIKit.services.IEvsYprSensorsEvents
import android.content.Context
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import com.aerovision.hub.InputMode
import com.everysight.evskit.android.Evs

/**
 * Owns the Everysight Maverick SDK: start/stop, connection, HUD text and head-orientation readings.
 *
 * SDK calls follow the official everysight-maverick/samples Android projects (SDK 2.6.1).
 * Listener callbacks may arrive on SDK threads.
 */
class MaverickGlasses(private val context: Context) {

    interface Listener {
        fun onStateChanged(state: GlassesState)
        fun onOrientation(sample: OrientationSample)
    }

    @Volatile
    var listener: Listener? = null

    @Volatile
    var state = GlassesState()
        private set

    private val hud = HudScreen()
    private val mainHandler = Handler(Looper.getMainLooper())
    private var started = false
    private var orientationActive = false

    /** Initialise the SDK and reconnect to previously configured glasses. Requires Bluetooth permissions. */
    fun start() {
        if (started) return
        started = true
        dispatch(GlassesEvent.KeyChecked(MaverickApiKey.isBundled(context)))

        Evs.init(context).start()
        val evs = Evs.instance()
        evs.registerAppEvents(appEvents)
        evs.glasses().registerGlassesEvents(glassesEvents)
        evs.comm().registerCommunicationEvents(commEvents)
        evs.screens().addScreen(hud)

        if (evs.comm().hasConfiguredDevice()) evs.comm().connect()
        else dispatch(GlassesEvent.NotConfigured)
    }

    fun stop() {
        if (!started) return
        started = false
        val evs = Evs.instance()
        stopOrientation()
        evs.unregisterAppEvents(appEvents)
        evs.comm().unregisterCommunicationEvents(commEvents)
        evs.glasses().unregisterGlassesEvents(glassesEvents)
        evs.stop()
    }

    /** Connect to the stored glasses, or open the SDK's pairing UI when none is stored. */
    fun connect() {
        val comm = Evs.instance().comm()
        if (comm.hasConfiguredDevice()) comm.connect() else configure()
    }

    fun disconnect() = Evs.instance().comm().disconnect()

    /** SDK stock UI: scan for and select glasses. */
    fun configure() = Evs.instance().showUI("configure")

    /** SDK stock UI: brightness and display position. */
    fun adjust() = Evs.instance().showUI("adjust")

    /** SDK stock UI: inertial-sensor calibration. */
    fun calibrate() = Evs.instance().showUI("calibrate")

    fun showText(text: String) {
        mainHandler.post { hud.showMessage(text) }
    }

    @Synchronized
    private fun startOrientation() {
        if (orientationActive) return
        orientationActive = true
        with(Evs.instance().sensors()) {
            registerYprSensorsEvents(yprEvents)
            enableInertialSensors()
        }
    }

    @Synchronized
    private fun stopOrientation() {
        if (!orientationActive) return
        orientationActive = false
        with(Evs.instance().sensors()) {
            disableInertialSensors()
            unregisterYprSensorsEvents(yprEvents)
        }
    }

    private fun dispatch(event: GlassesEvent) {
        val next = synchronized(this) {
            state = state.reduce(event)
            state
        }
        Log.d(TAG, "$event -> $next")
        listener?.onStateChanged(next)
    }

    private fun deviceName(): String? = Evs.instance().comm().getDeviceName()

    private val appEvents = object : IEvsAppEvents {
        override fun onReady() {
            dispatch(GlassesEvent.Ready)
            Evs.instance().display().turnDisplayOn()
            startOrientation()
            showText("Connected to hub")
        }

        override fun onUnReady() {
            stopOrientation()
            dispatch(GlassesEvent.UnReady)
        }

        override fun onError(errCode: AppErrorCode, description: String) {
            dispatch(GlassesEvent.Error("$errCode: $description"))
        }
    }

    private val commEvents = object : IEvsCommunicationEvents {
        override fun onAdapterStateChanged(isEnabled: Boolean) = dispatch(GlassesEvent.AdapterChanged(isEnabled))
        override fun onConnecting() = dispatch(GlassesEvent.Connecting(deviceName()))
        override fun onConnected() = dispatch(GlassesEvent.Connected(deviceName()))
        override fun onDisconnected() = dispatch(GlassesEvent.Disconnected)
        override fun onFailedToConnect() = dispatch(GlassesEvent.FailedToConnect)
    }

    private val glassesEvents = object : IEvsGlassesEvents {
        override fun onBatteryChanged(percentage: Int) = dispatch(GlassesEvent.Battery(percentage))
        override fun onBrightnessChangeRequested(value: Short) {}
        override fun onChargerStateChanged(isChargerConnected: Boolean) {}
        override fun onDisplayState(isDisplayOn: Boolean) {}
        override fun onPowerButton(action: PowerButtonAction) {}
    }

    private val yprEvents = object : IEvsYprSensorsEvents {
        override fun onYpr(timestampMs: Long, yprData: YprData, calibrationStatus: CalibrationStatus) {
            listener?.onOrientation(
                OrientationSample(
                    glassesTimestampMs = timestampMs,
                    receivedElapsedNanos = SystemClock.elapsedRealtimeNanos(),
                    yaw = yprData.yaw,
                    pitch = yprData.pitch,
                    roll = yprData.roll,
                    calibration = calibrationStatus.name,
                    inputMode = InputMode.LIVE,
                )
            )
        }
    }

    private companion object {
        const val TAG = "MaverickGlasses"
    }
}
