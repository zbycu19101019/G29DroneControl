package com.example.g29dronecontrol

import android.app.Instrumentation
import android.os.Bundle
import org.json.JSONObject
import java.net.ServerSocket
import java.net.Socket

/** Bench-only device tests using localhost. No USB endpoints or DJI commands. */
class BridgeInstrumentation : Instrumentation() {
    private var passed = 0
    override fun onCreate(arguments: Bundle?) { super.onCreate(arguments); start() }
    private fun test(name: String, operation: () -> Unit) {
        operation(); passed++
        sendStatus(0, Bundle().apply { putString("stream", "PASS: $name\n") })
    }
    private fun frame(seq: Long = 1, active: Boolean = true): String = JSONObject()
        .put("version", 1).put("type", "control").put("sessionId", "a".repeat(32)).put("seq", seq)
        .put("inputConnected", active).put("emergency", false).put("heartbeat", true)
        .put("output", JSONObject().put("yaw", .4).put("pitch", .2).put("roll", -.3).put("vertical", .1)).toString()
    private fun waitUntil(predicate: () -> Boolean) {
        val deadline = System.currentTimeMillis() + 1500
        while (!predicate() && System.currentTimeMillis() < deadline) Thread.sleep(10)
        check(predicate()) { "Oczekiwany stan nie wystąpił" }
    }
    private fun connected(operation: (NetworkClient, Socket) -> Unit) {
        ServerSocket(0).use { server ->
            server.soTimeout = 2000
            val client = NetworkClient()
            try { client.connect(server.localPort); server.accept().use { peer -> peer.soTimeout = 1500; operation(client, peer) } }
            finally { client.shutdown() }
        }
    }
    private fun send(peer: Socket, value: String) {
        peer.getOutputStream().write((value + "\n").toByteArray()); peer.getOutputStream().flush()
    }
    override fun onStart() {
        try {
            test("SDK freshness gates / no flight authority") {
                val sample = SdkSnapshot(registration = "REGISTERED", connection = "READ_ONLY",
                    productConnected = true, flightControllerConnected = true, lastFlightAt = 1000,
                    flightJson = "{\"source\":\"DJI_MSDK_FLIGHT_CALLBACK\",\"yaw\":12}")
                check(sample.toJson(1100).getBoolean("telemetryFresh"))
                check(!sample.toJson(2501).getBoolean("telemetryFresh"))
                check(sample.toJson(2501).isNull("telemetry"))
                check(!sample.copy(productConnected = false).toJson(1100).getBoolean("telemetryFresh"))
                check(!sample.copy(connection = "STOPPED").toJson(1100).getBoolean("telemetryFresh"))
                check(!sample.toJson(1100).getBoolean("flightControl"))
            }
            test("strict protocol / missing channel / range / session") {
                check(ControlPacket.parse(frame()).active)
                val bad = listOf(JSONObject(frame()).put("version", 2), JSONObject(frame()).put("sessionId", "wrong"),
                    JSONObject(frame()).apply { getJSONObject("output").remove("yaw") },
                    JSONObject(frame()).apply { getJSONObject("output").put("yaw", 1.2) })
                bad.forEach { check(runCatching { ControlPacket.parse(it.toString()) }.isFailure) }
            }
            test("neutral on input loss; duplex ACK") { connected { _, peer ->
                send(peer, frame(active = false))
                val ack = JSONObject(peer.getInputStream().bufferedReader().readLine())
                check(ack.getString("state") == "NEUTRAL" && !ack.getBoolean("flightControl"))
                check(BridgeState.snapshot.yaw == 0f)
            } }
            test("active mock then EOF neutral") { connected { _, peer ->
                send(peer, frame()); waitUntil { BridgeState.snapshot.yaw == .4f }
                peer.shutdownOutput(); waitUntil { BridgeState.snapshot.yaw == 0f }
            } }
            test("300 ms watchdog neutral") { connected { _, peer ->
                send(peer, frame()); waitUntil { BridgeState.snapshot.yaw == .4f }
                waitUntil { BridgeState.snapshot.status.contains("WATCHDOG") }
                check(BridgeState.snapshot.yaw == 0f)
            } }
            test("duplicate sequence neutral") { connected { _, peer ->
                send(peer, frame()); waitUntil { BridgeState.snapshot.yaw == .4f }
                send(peer, frame()); waitUntil { BridgeState.snapshot.yaw == 0f }
            } }
            test("STOP rejects subsequent packets") { connected { client, peer ->
                send(peer, frame()); waitUntil { BridgeState.snapshot.yaw == .4f }
                client.stop(); runCatching { send(peer, frame(2)) }; Thread.sleep(100)
                check(BridgeState.snapshot.yaw == 0f)
            } }
            test("bounded input rejects oversized frame") { connected { _, peer ->
                send(peer, "x".repeat(9000)); waitUntil { BridgeState.snapshot.status.contains("Za duży") }
                check(BridgeState.snapshot.yaw == 0f)
            } }
            finish(1, Bundle().apply { putString("stream", "OK: $passed tests; no flight commands\n") })
        } catch (error: Throwable) {
            finish(0, Bundle().apply { putString("stream", "FAILED after $passed tests: $error\n") })
        }
    }
}
