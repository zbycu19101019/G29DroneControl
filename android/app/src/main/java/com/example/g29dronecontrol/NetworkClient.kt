package com.example.g29dronecontrol

import android.os.SystemClock
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.net.SocketTimeoutException
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.UUID

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
    val isRunning: Boolean get() = synchronized(gate) { running }

    init {
        watchdog.scheduleWithFixedDelay({ synchronized(gate) {
            if (running && lastPacket > 0 && SystemClock.elapsedRealtime() - lastPacket >= 300)
                stopLocked("WATCHDOG 300 ms / ZERO")
        } }, 10, 10, TimeUnit.MILLISECONDS)
    }

    fun connect(port: Int = 8765, pairingToken: String) {
        require(port in 1024..65535)
        require(SignedFrames.validToken(pairingToken))
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
                val clientNonce = UUID.randomUUID().toString().replace("-", "")
                val hello = JSONObject().put("version", SignedFrames.VERSION).put("type", "hello").put("clientNonce", clientNonce)
                output.write((SignedFrames.encode(hello, pairingToken) + "\n").toByteArray(Charsets.UTF_8))
                output.flush()
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
                            val packet = ControlPacket.parse(SignedFrames.decode(frame.toString("UTF-8"), pairingToken).toString(), clientNonce)
                            frame.reset()
                            synchronized(gate) {
                                check(running && generation == token)
                                // Also enforce expiry here: after device suspend the
                                // reader may resume before the scheduled watchdog.
                                check(SystemClock.elapsedRealtime() - lastPacket < 300) { "Przerwa pakietów 300 ms" }
                                if (session.isEmpty()) {
                                    check(!packet.active && packet.yaw == 0f && packet.pitch == 0f && packet.roll == 0f && packet.vertical == 0f) { "Pierwszy pakiet musi być neutralny" }
                                    session = packet.session
                                }
                                check(session == packet.session && packet.seq > lastSeq) { "Stara sekwencja / sesja" }
                                lastSeq = packet.seq
                                lastPacket = SystemClock.elapsedRealtime()
                                if (SafetyAssessment.criticalBattery(SdkState.json())) {
                                    stopLocked("Niska bateria drona / kanały testowe ZERO")
                                    return@execute
                                }
                                BridgeState.apply(packet)
                                if (packet.emergency) {
                                    stopLocked("STOP Windows / ZERO")
                                    SdkState.adapter.stop()
                                }
                            }
                            val djiState = SdkState.json()
                            if (packet.emergency) return@execute
                            val ack = JSONObject().put("version", SignedFrames.VERSION).put("type", "ack")
                                .put("clientNonce", clientNonce)
                                .put("sessionId", packet.session).put("seq", packet.seq)
                                .put("state", if (packet.active) "RECEIVING" else "NEUTRAL")
                                .put("mode", SdkState.mode()).put("flightControl", false)
                                .put("aircraftTelemetry", djiState.getBoolean("telemetryFresh"))
                                .put("dji", djiState)
                                .put("usb", JSONObject(BridgeState.usbJson))
                            output.write((SignedFrames.encode(ack, pairingToken) + "\n").toByteArray(Charsets.UTF_8))
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
