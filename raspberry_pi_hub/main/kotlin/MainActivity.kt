package com.aerovision.hub

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import com.aerovision.hub.maverick.GlassesState
import com.aerovision.hub.maverick.MaverickGlasses
import com.aerovision.hub.maverick.OrientationSample
import java.util.Locale

/** Hub control screen: Maverick connection, status and a manual HUD message. */
class MainActivity : Activity(), MaverickGlasses.Listener {

    private lateinit var glasses: MaverickGlasses
    private lateinit var txtStatus: TextView
    private lateinit var txtOrientation: TextView
    private var lastOrientationUiNanos = 0L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        txtStatus = findViewById(R.id.txtStatus)
        txtOrientation = findViewById(R.id.txtOrientation)

        glasses = MaverickGlasses(this).also { it.listener = this }

        findViewById<Button>(R.id.btnConfigure).setOnClickListener { whenStarted { glasses.configure() } }
        findViewById<Button>(R.id.btnConnect).setOnClickListener { whenStarted { glasses.connect() } }
        findViewById<Button>(R.id.btnDisconnect).setOnClickListener { whenStarted { glasses.disconnect() } }
        findViewById<Button>(R.id.btnAdjust).setOnClickListener { whenStarted { glasses.adjust() } }
        findViewById<Button>(R.id.btnCalibrate).setOnClickListener { whenStarted { glasses.calibrate() } }
        val editHud = findViewById<EditText>(R.id.editHud)
        findViewById<Button>(R.id.btnSend).setOnClickListener {
            whenStarted { glasses.showText(editHud.text.toString()) }
        }

        render(glasses.state)
        val missing = missingPermissions()
        if (missing.isEmpty()) startGlasses() else requestPermissions(missing, PERMISSION_REQUEST)
    }

    override fun onDestroy() {
        glasses.listener = null
        if (sdkStarted) glasses.stop()
        super.onDestroy()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != PERMISSION_REQUEST) return
        if (missingPermissions().isEmpty()) startGlasses()
        else txtStatus.text = "Bluetooth permission denied — grant it in system settings and restart the app."
    }

    override fun onStateChanged(state: GlassesState) = runOnUiThread { render(state) }

    override fun onOrientation(sample: OrientationSample) {
        // Readings can arrive quickly; refresh the phone UI at most ~5 times per second.
        if (sample.receivedElapsedNanos - lastOrientationUiNanos < 200_000_000L) return
        lastOrientationUiNanos = sample.receivedElapsedNanos
        val text = String.format(
            Locale.US, "Orientation [%s] yaw %.1f  pitch %.1f  roll %.1f\ncalibration %s  t=%d ms",
            sample.inputMode, sample.yaw, sample.pitch, sample.roll, sample.calibration, sample.glassesTimestampMs,
        )
        runOnUiThread { txtOrientation.text = text }
    }

    private var sdkStarted = false

    private fun startGlasses() {
        if (sdkStarted) return
        sdkStarted = true
        glasses.start()
    }

    private inline fun whenStarted(action: () -> Unit) {
        if (sdkStarted) action() else txtStatus.text = "Waiting for Bluetooth permission."
    }

    private fun render(state: GlassesState) {
        txtStatus.text = buildString {
            appendLine("Glasses: ${state.link}${state.deviceName?.let { " ($it)" } ?: ""}")
            appendLine("Ready: ${if (state.ready) "yes" else "no"}")
            appendLine("Battery: ${state.batteryPercent?.let { "$it%" } ?: "—"}")
            appendLine("Bluetooth: ${when (state.bluetoothEnabled) { true -> "on"; false -> "off"; null -> "unknown" }}")
            if (!state.apiKeyBundled) appendLine("API key missing — see raspberry_pi_hub/README.md")
            state.lastError?.let { append("Error: $it") }
        }.trimEnd()
        if (!state.ready) {
            txtOrientation.text = getString(R.string.orientation_none)
        }
    }

    private fun missingPermissions(): Array<String> {
        val required = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            listOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            listOf(Manifest.permission.ACCESS_FINE_LOCATION)
        }
        return required.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }.toTypedArray()
    }

    private companion object {
        const val PERMISSION_REQUEST = 1
    }
}
