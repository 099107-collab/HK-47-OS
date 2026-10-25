package com.abacusai.hk47wear.net

import android.util.Log
import com.abacusai.hk47wear.model.BiometricPacket
import com.google.gson.Gson
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.PrintWriter
import java.net.Socket

class Hk47SocketBridge(
    private val hostProvider: () -> String = { "192.168.4.1" }, // Default Pocket CHIP AP IP
    private val port: Int = 4747,
    private val onMessageReceived: (String) -> Unit
) {
    private val tag = "Hk47SocketBridge"
    private val gson = Gson()
    private val scope = CoroutineScope(Dispatchers.IO)
    private var job: Job? = null
    private var socket: Socket? = null
    private var writer: PrintWriter? = null
    private var isConnected = false

    fun start() {
        if (job?.isActive == true) return
        job = scope.launch {
            while (isActive) {
                try {
                    val host = hostProvider()
                    Log.d(tag, "Attempting connection to Pocket CHIP at $host:$port...")
                    socket = Socket(host, port)
                    writer = PrintWriter(socket!!.getOutputStream(), true)
                    val reader = BufferedReader(InputStreamReader(socket!!.getInputStream()))
                    isConnected = true
                    Log.i(tag, "Connected to Pocket CHIP socket bridge!")

                    while (isActive && isConnected) {
                        val line = reader.readLine() ?: break
                        launch(Dispatchers.Main) {
                            onMessageReceived(line)
                        }
                    }
                } catch (e: Exception) {
                    Log.w(tag, "Socket connection error: ${e.message}. Retrying in 5s...")
                } finally {
                    isConnected = false
                    try { socket?.close() } catch (_: Exception) {}
                }
                delay(5000)
            }
        }
    }

    fun stop() {
        job?.cancel()
        job = null
        try { socket?.close() } catch (_: Exception) {}
        isConnected = false
    }

    fun sendTelemetry(packet: BiometricPacket) {
        if (!isConnected || writer == null) return
        scope.launch(Dispatchers.IO) {
            try {
                val json = gson.toJson(packet)
                writer?.println(json)
            } catch (e: Exception) {
                Log.w(tag, "Failed to send telemetry packet: ${e.message}")
            }
        }
    }

    fun isBridgeConnected(): Boolean = isConnected
}
