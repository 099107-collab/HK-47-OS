package com.abacusai.hk47wear.ble

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattServer
import android.bluetooth.BluetoothGattServerCallback
import android.bluetooth.BluetoothGattService
import android.bluetooth.BluetoothManager
import android.bluetooth.le.AdvertiseCallback
import android.bluetooth.le.AdvertiseData
import android.bluetooth.le.AdvertiseSettings
import android.bluetooth.le.BluetoothLeAdvertiser
import android.content.Context
import android.os.ParcelUuid
import android.util.Log
import com.abacusai.hk47wear.model.BiometricPacket
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.UUID

class Hk47BleGattServer(
    private val context: Context,
    private val onNotificationReceived: (String) -> Unit
) {
    private val tag = "Hk47BleServer"

    companion object {
        val SERVICE_UUID: UUID = UUID.fromString("484b3437-0001-4149-4745-4e5400000000")
        val TELEMETRY_CHAR_UUID: UUID = UUID.fromString("484b3437-0002-4149-4745-4e5400000000")
        val NOTIFICATION_CHAR_UUID: UUID = UUID.fromString("484b3437-0003-4149-4745-4e5400000000")
        val COMMAND_CHAR_UUID: UUID = UUID.fromString("484b3437-0004-4149-4745-4e5400000000")
        val STATUS_CHAR_UUID: UUID = UUID.fromString("484b3437-0005-4149-4745-4e5400000000")
    }

    private val bluetoothManager = context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager
    private val bluetoothAdapter: BluetoothAdapter? = bluetoothManager?.adapter
    private var gattServer: BluetoothGattServer? = null
    private var advertiser: BluetoothLeAdvertiser? = null
    private var connectedDevice: BluetoothDevice? = null
    private var telemetryChar: BluetoothGattCharacteristic? = null

    @SuppressLint("MissingPermission")
    fun start() {
        if (bluetoothAdapter == null || !bluetoothAdapter.isEnabled) {
            Log.w(tag, "Bluetooth is unavailable or disabled.")
            return
        }

        gattServer = bluetoothManager?.openGattServer(context, gattServerCallback)
        if (gattServer == null) {
            Log.e(tag, "Failed to open GATT Server.")
            return
        }

        val service = BluetoothGattService(SERVICE_UUID, BluetoothGattService.SERVICE_TYPE_PRIMARY)

        // Telemetry Char (Read + Notify)
        telemetryChar = BluetoothGattCharacteristic(
            TELEMETRY_CHAR_UUID,
            BluetoothGattCharacteristic.PROPERTY_READ or BluetoothGattCharacteristic.PROPERTY_NOTIFY,
            BluetoothGattCharacteristic.PERMISSION_READ
        )

        // Notification Char (Write)
        val notifChar = BluetoothGattCharacteristic(
            NOTIFICATION_CHAR_UUID,
            BluetoothGattCharacteristic.PROPERTY_WRITE or BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE,
            BluetoothGattCharacteristic.PERMISSION_WRITE
        )

        // Command Char (Write + Notify)
        val cmdChar = BluetoothGattCharacteristic(
            COMMAND_CHAR_UUID,
            BluetoothGattCharacteristic.PROPERTY_WRITE or BluetoothGattCharacteristic.PROPERTY_NOTIFY,
            BluetoothGattCharacteristic.PERMISSION_WRITE
        )

        service.addCharacteristic(telemetryChar)
        service.addCharacteristic(notifChar)
        service.addCharacteristic(cmdChar)
        gattServer?.addService(service)

        // Start Advertising HK-47 Service
        advertiser = bluetoothAdapter.bluetoothLeAdvertiser
        val settings = AdvertiseSettings.Builder()
            .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_BALANCED)
            .setConnectable(true)
            .setTimeout(0)
            .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_MEDIUM)
            .build()

        val data = AdvertiseData.Builder()
            .setIncludeDeviceName(true)
            .addServiceUuid(ParcelUuid(SERVICE_UUID))
            .build()

        advertiser?.startAdvertising(settings, data, advertiseCallback)
        Log.i(tag, "HK-47 Wear OS BLE GATT Server active and advertising.")
    }

    @SuppressLint("MissingPermission")
    fun stop() {
        advertiser?.stopAdvertising(advertiseCallback)
        gattServer?.close()
        gattServer = null
        connectedDevice = null
    }

    @SuppressLint("MissingPermission")
    fun notifyTelemetry(packet: BiometricPacket) {
        val device = connectedDevice ?: return
        val char = telemetryChar ?: return

        // Packed payload matching RTOS telemetry struct (14 bytes)
        // [0..1] steps uint16, [2] hr uint8, [3] bat uint8, [4] mood uint8, [5] flags uint8, [6..9] sedentary uint32
        val buffer = ByteBuffer.allocate(14).order(ByteOrder.LITTLE_ENDIAN)
        buffer.putShort((packet.stepCount and 0xFFFF).toShort())
        buffer.put(packet.hrBpm.toByte())
        buffer.put(packet.batteryPct.toByte())
        buffer.put(packet.mood.ordinal.toByte())
        buffer.put((if (packet.isWristAwake) 1 else 0).toByte())
        buffer.putInt(packet.sedentarySeconds.toInt())

        char.value = buffer.array()
        gattServer?.notifyCharacteristicChanged(device, char, false)
    }

    private val advertiseCallback = object : AdvertiseCallback() {
        override fun onStartSuccess(settingsInEffect: AdvertiseSettings?) {
            Log.i(tag, "BLE advertising started successfully.")
        }
        override fun onStartFailure(errorCode: Int) {
            Log.e(tag, "BLE advertising failed: code $errorCode")
        }
    }

    private val gattServerCallback = object : BluetoothGattServerCallback() {
        @SuppressLint("MissingPermission")
        override fun onConnectionStateChange(device: BluetoothDevice?, status: Int, newState: Int) {
            if (newState == BluetoothGatt.STATE_CONNECTED) {
                connectedDevice = device
                Log.i(tag, "Connected to master device: ${device?.address}")
            } else if (newState == BluetoothGatt.STATE_DISCONNECTED) {
                if (connectedDevice?.address == device?.address) {
                    connectedDevice = null
                }
                Log.i(tag, "Disconnected from device: ${device?.address}")
            }
        }

        @SuppressLint("MissingPermission")
        override fun onCharacteristicWriteRequest(
            device: BluetoothDevice?,
            requestId: Int,
            characteristic: BluetoothGattCharacteristic?,
            preparedWrite: Boolean,
            responseNeeded: Boolean,
            offset: Int,
            value: ByteArray?
        ) {
            if (responseNeeded) {
                gattServer?.sendResponse(device, requestId, BluetoothGatt.GATT_SUCCESS, offset, null)
            }
            if (characteristic?.uuid == NOTIFICATION_CHAR_UUID && value != null) {
                val message = String(value, Charsets.UTF_8)
                Log.i(tag, "Received notification from Pocket CHIP: $message")
                onNotificationReceived(message)
            }
        }
    }
}
