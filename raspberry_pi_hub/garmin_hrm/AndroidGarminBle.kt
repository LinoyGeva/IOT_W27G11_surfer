package org.aerovision.hub.garmin

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.*
import android.bluetooth.le.*
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import java.util.UUID

/** Android GATT port. Only this class owns scanner/GATT lifecycle and CCCDs. */
@SuppressLint("MissingPermission") // Permission failures are surfaced to the session/UI.
class AndroidGarminBle(private val context: Context) : HrBleTransport {
    companion object {
        val SERVICE: UUID = UUID.fromString("0000180d-0000-1000-8000-00805f9b34fb")
        val MEASUREMENT: UUID = UUID.fromString("00002a37-0000-1000-8000-00805f9b34fb")
        val CCCD: UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")
    }
    private val handler = Handler(Looper.getMainLooper())
    private val manager = context.getSystemService(BluetoothManager::class.java)
    private var scanner: BluetoothLeScanner? = null
    private var scanCallback: ScanCallback? = null
    private var gatt: BluetoothGatt? = null
    private var listener: HrBleTransport.Listener? = null

    private fun permitted(): Boolean = listOf(Manifest.permission.BLUETOOTH_SCAN,
        Manifest.permission.BLUETOOTH_CONNECT).all {
        context.checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED
    }

    override fun scan(onFound: (HrDevice) -> Unit, onFailure: (String) -> Unit) {
        stopScan()
        if (!permitted()) { onFailure("Nearby devices permission is required"); return }
        val adapter = manager?.adapter
        if (adapter == null || !adapter.isEnabled) { onFailure("Turn on Bluetooth on the Pi"); return }
        val bleScanner = adapter.bluetoothLeScanner
        if (bleScanner == null) { onFailure("BLE scanner unavailable"); return }
        val callback = object : ScanCallback() {
            override fun onScanResult(callbackType: Int, result: ScanResult) {
                val current = this
                val name = result.scanRecord?.deviceName
                handler.post {
                    if (scanCallback === current) onFound(HrDevice(result.device.address, name))
                }
            }
            override fun onScanFailed(errorCode: Int) {
                val current = this
                handler.post { if (scanCallback === current) onFailure("BLE scan failed: $errorCode") }
            }
        }
        scanner = bleScanner
        scanCallback = callback
        try {
            bleScanner.startScan(listOf(ScanFilter.Builder().setServiceUuid(ParcelUuid(SERVICE)).build()),
                ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), callback)
        } catch (error: Exception) {
            stopScan()
            onFailure("Cannot scan: ${error.message}")
        }
    }

    override fun stopScan() {
        val old = scanCallback
        scanCallback = null
        try { if (old != null) scanner?.stopScan(old) } catch (_: SecurityException) { }
        scanner = null
    }

    override fun connect(device: HrDevice, listener: HrBleTransport.Listener) {
        close()
        this.listener = listener
        if (!permitted()) { listener.onFailure("Nearby devices permission is required"); return }
        // Rediscover on every attempt: after a radio restart, directly opening a
        // cached device can stall on the Pi even though a fresh scan finds it.
        // GarminSession bounds this scan + connection with its connect timeout.
        scan({ found ->
            if (found.address.equals(device.address, ignoreCase = true)) {
                stopScan()
                openGatt(found, listener)
            }
        }, { reason -> listener.onFailure(reason) })
    }

    private fun openGatt(device: HrDevice, listener: HrBleTransport.Listener) {
        try {
            val adapter = manager?.adapter
            if (adapter == null || !adapter.isEnabled) { listener.onFailure("Turn on Bluetooth on the Pi"); return }
            gatt = adapter.getRemoteDevice(device.address).connectGatt(context, false, callback, BluetoothDevice.TRANSPORT_LE)
            if (gatt == null) listener.onFailure("Could not create GATT client")
        } catch (error: Exception) { listener.onFailure("Cannot connect: ${error.message}") }
    }

    private fun deliver(source: BluetoothGatt, action: (HrBleTransport.Listener) -> Unit) {
        handler.post { if (gatt === source) listener?.let(action) }
    }

    private val callback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(source: BluetoothGatt, status: Int, newState: Int) {
            deliver(source) {
                when {
                    status != BluetoothGatt.GATT_SUCCESS -> it.onFailure("GATT connection error $status")
                    newState == BluetoothProfile.STATE_CONNECTED -> it.onConnected()
                    newState == BluetoothProfile.STATE_DISCONNECTED -> it.onDisconnected("Bluetooth link disconnected")
                }
            }
        }
        override fun onServicesDiscovered(source: BluetoothGatt, status: Int) {
            deliver(source) {
                if (status != BluetoothGatt.GATT_SUCCESS) { it.onFailure("Service discovery error $status"); return@deliver }
                val measurement = source.getService(SERVICE)?.getCharacteristic(MEASUREMENT)
                it.onServicesAvailable(measurement != null &&
                    measurement.properties and BluetoothGattCharacteristic.PROPERTY_NOTIFY != 0 &&
                    measurement.getDescriptor(CCCD) != null)
            }
        }
        override fun onDescriptorWrite(source: BluetoothGatt, descriptor: BluetoothGattDescriptor, status: Int) {
            if (descriptor.uuid != CCCD || descriptor.characteristic.uuid != MEASUREMENT) return
            deliver(source) {
                if (status == BluetoothGatt.GATT_SUCCESS) it.onSubscribed()
                else it.onFailure("Notification subscription error $status")
            }
        }
        override fun onCharacteristicChanged(source: BluetoothGatt, characteristic: BluetoothGattCharacteristic, value: ByteArray) {
            if (characteristic.uuid == MEASUREMENT) {
                val copy = value.copyOf()
                deliver(source) { it.onPacket(copy) }
            }
        }
        @Deprecated("Compatibility callback for API 31/32")
        override fun onCharacteristicChanged(source: BluetoothGatt, characteristic: BluetoothGattCharacteristic) {
            if (Build.VERSION.SDK_INT < 33 && characteristic.uuid == MEASUREMENT) {
                @Suppress("DEPRECATION") val copy = characteristic.value?.copyOf() ?: return
                deliver(source) { it.onPacket(copy) }
            }
        }
    }

    override fun discoverServices() {
        try { if (gatt?.discoverServices() != true) listener?.onFailure("Cannot begin service discovery") }
        catch (error: Exception) { listener?.onFailure("Cannot discover services: ${error.message}") }
    }

    override fun subscribeHeartRate() {
        val current = gatt ?: return
        val measurement = current.getService(SERVICE)?.getCharacteristic(MEASUREMENT)
        val descriptor = measurement?.getDescriptor(CCCD)
        if (measurement == null || descriptor == null) { listener?.onFailure("Heart-rate notification characteristic missing"); return }
        try {
            if (!current.setCharacteristicNotification(measurement, true)) {
                listener?.onFailure("Cannot enable local notification routing"); return
            }
            val accepted = if (Build.VERSION.SDK_INT >= 33) {
                current.writeDescriptor(descriptor, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE) == BluetoothStatusCodes.SUCCESS
            } else {
                @Suppress("DEPRECATION")
                descriptor.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                @Suppress("DEPRECATION")
                current.writeDescriptor(descriptor)
            }
            if (!accepted) listener?.onFailure("Cannot write heart-rate CCCD")
        } catch (error: Exception) { listener?.onFailure("Cannot subscribe: ${error.message}") }
    }

    override fun close() {
        stopScan()
        val old = gatt
        gatt = null
        listener = null
        try { old?.disconnect() } catch (_: SecurityException) { }
        try { old?.close() } catch (_: SecurityException) { }
    }
}
