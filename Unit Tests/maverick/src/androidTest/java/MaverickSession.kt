package org.aerovision.maverick

import UIKit.app.data.BTConstants
import UIKit.services.AppErrorCode
import UIKit.services.IEvsAppEvents
import UIKit.services.IEvsCommunicationEvents
import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.os.Build
import android.os.ParcelUuid
import android.util.Log
import androidx.test.platform.app.InstrumentationRegistry
import com.everysight.evskit.android.Evs
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference

class MaverickSession(private val testName: String) : IEvsAppEvents, IEvsCommunicationEvents, AutoCloseable {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext
    private val finished = CountDownLatch(1)
    private val failure = AtomicReference<String?>()

    val app get() = Evs.instance()

    fun connect() {
        log("START test=$testName mode=live android=${Build.VERSION.RELEASE} abi=${Build.SUPPORTED_ABIS.first()}")
        try {
            val permissions = if (Build.VERSION.SDK_INT >= 31) {
                listOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
            } else {
                listOf(Manifest.permission.ACCESS_FINE_LOCATION)
            }
            permissions.forEach { instrumentation.uiAutomation.grantRuntimePermission(context.packageName, it) }
            val adapter = context.getSystemService(BluetoothManager::class.java)?.adapter
            check(adapter != null && adapter.isEnabled) { "Enable Bluetooth on the Pi" }
            if (adapter.isDiscovering) {
                adapter.cancelDiscovery()
                log("CLASSIC_DISCOVERY_STOP")
            }
            val address = InstrumentationRegistry.getArguments().getString("address")
            val device = if (address != null) {
                check(BluetoothAdapter.checkBluetoothAddress(address)) { "Invalid glasses address" }
                adapter.getRemoteDevice(address)
            } else {
                discover(adapter)
            }
            log("DEVICE name=${device.name} address=${device.address}")
            instrumentation.runOnMainSync {
                val app = Evs.init(context)
                app.registerAppEvents(this)
                app.comm().registerCommunicationEvents(this)
                check(app.start()) { "SDK start failed" }
                log("SDK version=${app.getSDKVersion()}")
                app.comm().setDeviceInfo(device.address, device.name ?: "Maverick")
                check(app.comm().connect()) { "SDK rejected connect request" }
            }
            check(finished.await(60, TimeUnit.SECONDS)) { "Handshake timed out after 60s" }
            checkReady()
        } catch (error: Throwable) {
            log("FAIL test=$testName reason=${error.message}")
            throw error
        }
    }

    fun checkReady() {
        check(failure.get() == null) { failure.get()!! }
        onMain { check(app.isReady()) { "SDK became unready before validation" } }
    }

    fun onMain(action: () -> Unit) { instrumentation.runOnMainSync { action() } }

    override fun close() {
        onMain {
            if (Evs.wasInitialized()) {
                app.comm().unregisterCommunicationEvents(this)
                app.unregisterAppEvents(this)
                app.comm().disconnect()
                app.stop()
                log("STOP test=$testName")
            }
        }
    }

    private fun discover(adapter: BluetoothAdapter): BluetoothDevice {
        val devices = ConcurrentHashMap<String, BluetoothDevice>()
        val name = InstrumentationRegistry.getArguments().getString("name")
        val service = ParcelUuid(UUID.fromString(BTConstants.serviceUUID))
        val maverickName = Regex("EV\\d+")
        val advertisements = AtomicInteger()
        val scanError = AtomicReference<Int?>()
        val scanDone = CountDownLatch(1)
        val callback = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult) {
                advertisements.incrementAndGet()
                val advertisedName = result.scanRecord?.deviceName ?: result.device.name
                val matches = if (name != null) advertisedName == name else {
                    result.scanRecord?.serviceUuids?.contains(service) == true ||
                        advertisedName?.matches(maverickName) == true
                }
                if (matches) devices[result.device.address] = result.device
            }
            override fun onScanFailed(errorCode: Int) {
                scanError.set(errorCode)
                scanDone.countDown()
            }
        }
        val scanner = checkNotNull(adapter.bluetoothLeScanner) { "BLE scanner unavailable" }
        log("SCAN name=${name ?: "auto"} duration_s=10")
        try {
            scanner.startScan(null, ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), callback)
            scanDone.await(10, TimeUnit.SECONDS)
        } finally {
            scanner.stopScan(callback)
        }
        check(scanError.get() == null) { "BLE scan failed code=${scanError.get()}" }
        log("SCAN_DONE advertisements=${advertisements.get()} matches=${devices.size}")
        devices.values.forEach { log("FOUND name=${it.name} address=${it.address}") }
        check(devices.size == 1) {
            "Found ${devices.size} Maverick devices; power on glasses near the Pi, or select one with -e address MAC"
        }
        return devices.values.single()
    }

    override fun onConnecting() = log("CONNECTING")
    override fun onConnected() = log("CONNECTED awaiting_auth=true")
    override fun onBeginAuth(serial: String, fwVersion: Int) = log("AUTH serial=$serial firmware=$fwVersion")
    override fun onReady() {
        log("READY battery_pct=${app.glasses().batteryPercentage()} proximity=${app.sensors().proximityState()}")
        finished.countDown()
    }
    override fun onUnReady() = fail("SDK unready")
    override fun onDisconnected() = fail("Disconnected")
    override fun onFailedToConnect() = fail("Connection failed")
    override fun onError(errCode: AppErrorCode, description: String) = fail("SDK error code=$errCode")

    private fun fail(reason: String) {
        failure.compareAndSet(null, reason)
        log("ERROR $reason")
        finished.countDown()
    }
    fun log(message: String) { Log.i("MaverickTest", message) }
}
