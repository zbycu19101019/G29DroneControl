package com.example.g29dronecontrol

import android.os.SystemClock
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.net.SocketTimeoutException
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/** A single bounded reader plus one watchdog per client, not one per connect. */
class NetworkClient {
    private val gate = Any()
    private val worker = Executors.newSingleThreadExecutor()
    private val watchdog = Executors.newSingleThreadScheduledExecutor()
    private var generation = 0L
    private var running = false
    private var socket: Socket? = null
    private var lastPacket = 0L
    private var session = ""
    private var lastSeq = -1L

    init {
        watchdog.scheduleWithFixedDelay({ synchronized(gate) {
            if (running && lastPacket > 0 && SystemClock.elapsedRealtime() - lastPacket >= 300)
                stopLocked("WATCHDOG 300 ms / ZERO")
        } }, 10, 10, TimeUnit.MILLISECONDS)
    }

    fun connect(port: Int = 8765) {
        require(port in 1024..65535)
        val token: Long
        val connection = Socket()
        synchronized(gate) {
            if (running) { connection.close(); return }
            generation++
            token = generation
            running = true
            socket = connection
            lastPacket = 0
            session = ""
            lastSeq = -1
            BridgeState.neutral("Łączenie PC / ZERO")
        }
        worker.execute {
            try {
                connection.connect(InetSocketAddress("127.0.0.1", port), 2000)
                connection.tcpNoDelay = true
                connection.soTimeout = 50
                synchronized(gate) {
                    check(running && generation == token)
                    lastPacket = SystemClock.elapsedRealtime()
                }
                val input = connection.getInputStream()
                val output = connection.getOutputStream()
                val frame = ByteArrayOutputStream()
                val bytes = ByteArray(2048)
                while (synchronized(gate) { running && generation == token }) {
                    val count = try { input.read(bytes) } catch (_: SocketTimeoutException) { continue }
                    check(count >= 0) { "EOF / PC zamknął połączenie" }
                    for (i in 0 until count) {
                        val b = bytes[i].toInt() and 255
                        if (b != 10) {
                            check(frame.size() < 8192) { "Za duży pakiet" }
                            frame.write(b)
                        } else {
                            val packet = ControlPacket.parse(frame.toString("UTF-8"))
                            frame.reset()
                            synchronized(gate) {
                                check(running && generation == token)
                                // Also enforce expiry here: after device suspend the
                                // reader may resume before the scheduled watchdog.
                                check(SystemClock.elapsedRealtime() - lastPacket < 300) { "Przerwa pakietów 300 ms" }
                                if (session.isEmpty()) session = packet.session
                                check(session == packet.session && packet.seq > lastSeq) { "Stara sekwencja / sesja" }
                                lastSeq = packet.seq
                                lastPacket = SystemClock.elapsedRealtime()
                                BridgeState.apply(packet)
                            }
                            val djiState = SdkState.json()
                            val ack = JSONObject().put("version", 1).put("type", "ack")
                                .put("sessionId", packet.session).put("seq", packet.seq)
                                .put("state", if (packet.active) "RECEIVING" else "NEUTRAL")
                                .put("mode", SdkState.mode()).put("flightControl", false)
                                .put("aircraftTelemetry", djiState.getBoolean("telemetryFresh"))
                                .put("dji", djiState)
                                .put("usb", JSONObject(BridgeState.usbJson))
                            output.write((ack.toString() + "\n").toByteArray(Charsets.UTF_8))
                            output.flush()
                        }
                    }
                }
            } catch (e: Exception) {
                synchronized(gate) {
                    if (generation == token && running) stopLocked("LINK: ${e.message?.take(100)} / ZERO")
                }
            } finally {
                runCatching { connection.close() }
                synchronized(gate) {
                    if (generation == token && running) stopLocked("LINK zakończony / ZERO")
                }
            }
        }
    }

    private fun stopLocked(reason: String) {
        running = false
        generation++
        BridgeState.neutral(reason)
        runCatching { socket?.close() }
        socket = null
        lastPacket = 0
    }
    fun stop() { synchronized(gate) { stopLocked("STOP / ZERO") } }
    fun shutdown() { stop(); worker.shutdownNow(); watchdog.shutdownNow() }
}
