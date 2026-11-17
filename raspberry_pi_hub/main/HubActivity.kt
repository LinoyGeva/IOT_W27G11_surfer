package org.aerovision.hub

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import android.util.Log
import android.view.WindowManager
import android.widget.*
import org.aerovision.hub.garmin.*
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

/** Foreground-only first hub milestone. No synthetic readings enter this app. */
class HubActivity : Activity() {
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var session: GarminSession
    private lateinit var status: TextView
    private lateinit var bpm: TextView
    private lateinit var details: TextView
    private lateinit var devices: LinearLayout
    private var previousDevices: List<HrDevice> = emptyList()
    private var lastLogKey = ""
    private val permissions = arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
    private val ticker = object : Runnable {
        override fun run() { session.tick(); handler.postDelayed(this, 500) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        val content = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(24, 24, 24, 24) }
        fun text(size: Float, value: String) = TextView(this).apply { textSize = size; text = value; content.addView(this) }
        text(26f, "AeroVision • Garmin HR")
        text(16f, "Select your own band. Keep it worn/active and close competing apps.")
        status = text(20f, "Idle")
        bpm = text(42f, "— BPM")
        details = text(16f, "Waiting for real BLE notifications")
        devices = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val scan = Button(this).apply { text = "Scan heart-rate bands"; setOnClickListener { requestScan() } }
        content.addView(scan)
        content.addView(Button(this).apply { text = "Disconnect / stop"; setOnClickListener { session.stop() } })
        content.addView(Button(this).apply {
            text = "Bluetooth settings"
            setOnClickListener { startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS)) }
        })
        content.addView(devices)
        setContentView(ScrollView(this).apply { addView(content) })
        val clock = object : HrClock {
            override fun monotonicMs() = SystemClock.elapsedRealtime()
            override fun utcMs() = System.currentTimeMillis()
        }
        session = GarminSession(AndroidGarminBle(applicationContext), clock, UUID.randomUUID().toString(), ::render)
        render(session.snapshot())
    }

    private fun requestScan() {
        if (permissions.all { checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED }) session.scan()
        else requestPermissions(permissions, 1)
    }

    override fun onRequestPermissionsResult(code: Int, requested: Array<out String>, results: IntArray) {
        super.onRequestPermissionsResult(code, requested, results)
        if (code == 1 && results.isNotEmpty() && results.all { it == PackageManager.PERMISSION_GRANTED }) session.scan()
        else status.text = "Nearby devices permission denied; scan cannot start"
    }

    override fun onStart() { super.onStart(); handler.post(ticker) }
    override fun onStop() {
        handler.removeCallbacks(ticker)
        session.stop()
        super.onStop()
    }

    private fun render(value: GarminSnapshot) {
        status.text = "State: ${value.phase}\n${value.selected?.name ?: "No band selected"}\n${value.lastError ?: ""}"
        val reading = value.reading
        bpm.text = reading?.let { "${it.measurement.bpm} BPM" } ?: "— BPM"
        bpm.setTextColor(if (reading == null) Color.DKGRAY else Color.rgb(0, 110, 55))
        details.text = if (reading == null) "No current measurement" else
            "Live BLE • received ${value.receiveAgeMs} ms ago\n" +
            "Connection ${reading.connectionId} • packet ${reading.sequence}\n" +
            "Contact: ${reading.measurement.contactDetected ?: "unsupported"}\n" +
            "RR: ${reading.measurement.rrIntervalsMs} ms\nRaw: ${reading.rawHex}"
        if (previousDevices != value.devices) {
            previousDevices = value.devices
            devices.removeAllViews()
            value.devices.forEach { band ->
                devices.addView(Button(this).apply {
                    text = "${band.name ?: "Unnamed HR sensor"}\n${band.address}"
                    setOnClickListener { session.select(band) }
                })
            }
        }
        val key = "${value.phase}/${reading?.connectionId}/${reading?.sequence}/${value.lastError}"
        if (key != lastLogKey) {
            lastLogKey = key
            val row = JSONObject().put("event", if (reading == null) "status" else "heart_rate")
                .put("input_mode", "live").put("phase", value.phase.name)
                .put("device_address", value.selected?.address ?: JSONObject.NULL)
                .put("error", value.lastError ?: JSONObject.NULL)
            if (reading != null) {
                row.put("run_id", reading.runId).put("connection_id", reading.connectionId)
                    .put("sequence", reading.sequence).put("received_utc_ms", reading.receivedUtcMs)
                    .put("received_monotonic_ms", reading.receivedMonotonicMs)
                    .put("clock_semantics", "Android elapsedRealtime reception; sensor sample time unavailable")
                    .put("bpm", reading.measurement.bpm).put("raw_hex", reading.rawHex)
                    .put("contact_detected", reading.measurement.contactDetected ?: JSONObject.NULL)
                    .put("energy_expended_kj", reading.measurement.energyExpendedKj ?: JSONObject.NULL)
                    .put("rr_intervals_ms", JSONArray(reading.measurement.rrIntervalsMs))
            }
            Log.i("AeroVisionHR", row.toString())
        }
    }
}
