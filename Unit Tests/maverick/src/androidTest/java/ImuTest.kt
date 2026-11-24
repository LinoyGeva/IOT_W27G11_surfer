package org.aerovision.maverick

import UIKit.app.Screen
import UIKit.app.data.ScreenRenderRate
import UIKit.app.data.SensorRate
import UIKit.app.data.SensorType
import UIKit.services.IEvsInertialSensorsEvents
import android.os.SystemClock
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Test
import org.junit.runner.RunWith
import java.util.Locale
import java.util.concurrent.atomic.AtomicReference

@RunWith(AndroidJUnit4::class)
class ImuTest {
    @Test
    fun readForThirtySeconds() {
        MaverickSession("imu").use { glasses ->
            glasses.connect()
            val units = mapOf(SensorType.acc to "m/s^2", SensorType.gyro to "rad/s", SensorType.mag to "mGauss")
            val counts = units.keys.associateWith { 0 }.toMutableMap()
            val duplicates = units.keys.associateWith { 0 }.toMutableMap()
            val backwards = units.keys.associateWith { 0 }.toMutableMap()
            val timestamps = mutableMapOf<SensorType, Long>()
            val lastReceived = mutableMapOf<SensorType, Long>()
            val lastLog = mutableMapOf<SensorType, Long>()
            val invalid = AtomicReference<String?>()
            val started = SystemClock.elapsedRealtime()
            val listener = object : IEvsInertialSensorsEvents {
                override fun onSensor(sensorType: SensorType, timestampNs: Long, x: Float, y: Float, z: Float) {
                    synchronized(counts) {
                        if (sensorType !in counts) return
                        if (!x.isFinite() || !y.isFinite() || !z.isFinite()) {
                            invalid.compareAndSet(null, "$sensorType non-finite reading")
                        }
                        timestamps[sensorType]?.let { previous ->
                            if (timestampNs == previous) {
                                duplicates[sensorType] = duplicates.getValue(sensorType) + 1
                                return
                            }
                            if (timestampNs < previous) {
                                backwards[sensorType] = backwards.getValue(sensorType) + 1
                                if (backwards.getValue(sensorType) == 1) {
                                    glasses.log("TIMING_WARNING sensor=$sensorType previous_ns=$previous current_ns=$timestampNs")
                                }
                            }
                        }
                        timestamps[sensorType] = timestampNs
                        counts[sensorType] = counts.getValue(sensorType) + 1
                        val received = SystemClock.elapsedRealtime() - started
                        lastReceived[sensorType] = received
                        if (received - (lastLog[sensorType] ?: -500L) >= 500) {
                            lastLog[sensorType] = received
                            glasses.log(String.format(Locale.US,
                                "IMU sensor=%s ts_ns=%d rx_ms=%d x=%.3f y=%.3f z=%.3f unit=%s",
                                sensorType, timestampNs, received, x, y, z, units.getValue(sensorType)))
                        }
                    }
                }
            }
            // Sensor batches follow the SDK rendering cycle; no HUD content is drawn.
            val screen = Screen().apply { setScreenRenderRate(ScreenRenderRate.fast) }
            try {
                glasses.onMain {
                    val sensors = glasses.app.sensors()
                    units.keys.forEach { check(sensors.isSupported(it)) { "Unsupported sensor: $it" } }
                    glasses.app.display().turnDisplayOn()
                    glasses.app.screens().addScreen(screen)
                    sensors.registerInertialSensorsEvents(listener)
                    sensors.setSensorsRate(SensorRate.rate0)
                    sensors.enableInertialSensors()
                    glasses.log("STREAM_START duration_s=30 log_hz_per_sensor=2 requested_rate=${SensorRate.rate0.toHz()}")
                }
                repeat(30) { second ->
                    Thread.sleep(1000)
                    glasses.checkReady()
                    check(invalid.get() == null) { invalid.get()!! }
                    if (second >= 4) synchronized(counts) {
                        val now = SystemClock.elapsedRealtime() - started
                        units.keys.forEach { sensor ->
                            check(now - (lastReceived[sensor] ?: -30_000L) < 3000) { "No fresh $sensor samples for 3s" }
                        }
                    }
                }
            } catch (error: Throwable) {
                glasses.log("FAIL test=imu reason=${error.message}")
                throw error
            } finally {
                glasses.onMain {
                    glasses.app.sensors().disableInertialSensors()
                    glasses.app.sensors().unregisterInertialSensorsEvents(listener)
                    glasses.app.screens().removeScreen(screen)
                    glasses.app.display().turnDisplayOff()
                    glasses.log("STREAM_STOP")
                }
            }
            synchronized(counts) {
                glasses.log("COUNTS " + counts.entries.joinToString(" ") { "${it.key}=${it.value}" })
                glasses.log("DUPLICATES " + duplicates.entries.joinToString(" ") { "${it.key}=${it.value}" })
                glasses.log("BACKWARDS " + backwards.entries.joinToString(" ") { "${it.key}=${it.value}" })
                check(counts.values.all { it > 0 }) { "Missing IMU samples: $counts" }
            }
            glasses.log("PASS test=imu delivery=true manual_validation=pending")
        }
    }
}
