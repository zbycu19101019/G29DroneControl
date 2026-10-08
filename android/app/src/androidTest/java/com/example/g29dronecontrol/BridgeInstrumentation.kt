package com.example.g29dronecontrol

import android.app.Instrumentation
import android.os.Bundle
import org.json.JSONObject
import java.net.ServerSocket
import java.net.Socket

/** Bench-only device tests using localhost. No USB endpoints or DJI commands. */
class BridgeInstrumentation : Instrumentation() {
    private var passed = 0
    private val token = "00".repeat(32)
    private var nonce = "b".repeat(32)
    override fun onCreate(arguments: Bundle?) { super.onCreate(arguments); start() }
    private fun test(name: String, operation: () -> Unit) {
        operation(); passed++
        sendStatus(0, Bundle().apply { putString("stream", "PASS: $name\n") })
    }
    private fun frame(seq: Long = 1, active: Boolean = true): String = JSONObject()
        .put("version", SignedFrames.VERSION).put("type", "control").put("clientNonce", nonce).put("sessionId", "a".repeat(32)).put("seq", seq)
        .put("inputConnected", active).put("emergency", false).put("heartbeat", true)
        .put("output", JSONObject().put("yaw", if (active) .4 else 0).put("pitch", if (active) .2 else 0)
            .put("roll", if (active) -.3 else 0).put("vertical", if (active) .1 else 0)).toString()
    private fun waitUntil(predicate: () -> Boolean) {
        val deadline = System.currentTimeMillis() + 1500
        while (!predicate() && System.currentTimeMillis() < deadline) Thread.sleep(10)
        check(predicate()) { "Oczekiwany stan nie wystąpił" }
    }
    private fun connected(operation: (NetworkClient, Socket) -> Unit) {
        ServerSocket(0).use { server ->
            server.soTimeout = 2000
            val client = NetworkClient()
            try { client.connect(server.localPort, token); server.accept().use { peer ->
                peer.soTimeout = 1500
                val hello = SignedFrames.decode(peer.getInputStream().bufferedReader().readLine(), token)
                check(hello.getString("type") == "hello")
                nonce = hello.getString("clientNonce")
                send(peer, frame(seq = 0, active = false))
                val ack = SignedFrames.decode(peer.getInputStream().bufferedReader().readLine(), token)
                check(ack.getString("state") == "NEUTRAL")
                operation(client, peer)
            } }
            finally { client.shutdown() }
        }
    }
    private fun send(peer: Socket, value: String) {
        val wire = if (value.startsWith("{")) SignedFrames.encode(JSONObject(value), token) else value
        peer.getOutputStream().write((wire + "\n").toByteArray()); peer.getOutputStream().flush()
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
                check(!sample.copy(connection = "WAITING_USB_PERMISSION").toJson(1100).getBoolean("telemetryFresh"))
                check(!sample.copy(connection = "CONNECTING").toJson(1100).getBoolean("telemetryFresh"))
                check(!sample.toJson(1100).getBoolean("flightControl"))
            }
            test("USB PendingIntent creation on target 34+; no permission request") {
                val intent = UsbAccessoryPermission.permissionIntent(targetContext)
                val other = UsbAccessoryPermission.permissionIntent(targetContext)
                check(intent.`package` == targetContext.packageName)
                check(intent.action == "${targetContext.packageName}.USB_PERMISSION")
                check(intent.data != other.data)
                val pending = android.app.PendingIntent.getBroadcast(targetContext, 0, intent,
                    android.app.PendingIntent.FLAG_IMMUTABLE or android.app.PendingIntent.FLAG_ONE_SHOT)
                try {
                    if (android.os.Build.VERSION.SDK_INT >= 31) check(pending.isImmutable)
                    check(pending.creatorPackage == targetContext.packageName)
                } finally { pending.cancel() }
            }
            test("USB pilot whitelist and actual grant status") {
                check(UsbAccessoryPermission.isPilot("DJI", "com.dji.logiclink"))
                check(!UsbAccessoryPermission.isPilot("OTHER", "com.dji.logiclink"))
                check(!UsbAccessoryPermission.isPilot("DJI", "other"))
                check(!UsbAccessoryPermission.isPilot(null, null))
                listOf("WAITING", "DENIED", "TIMEOUT", "DETACHED", "ERROR", "CANCELLED").forEach {
                    check(!UsbAccessoryPermission.Result(it).granted)
                }
                check(UsbAccessoryPermission.Result("GRANTED").granted)
            }
            test("strict protocol / missing channel / range / session") {
                check(ControlPacket.parse(frame(), nonce).active)
                val bad = listOf(JSONObject(frame()).put("version", 1), JSONObject(frame()).put("sessionId", "wrong"),
                    JSONObject(frame()).apply { getJSONObject("output").remove("yaw") },
                    JSONObject(frame()).apply { getJSONObject("output").put("yaw", 1.2) })
                bad.forEach { check(runCatching { ControlPacket.parse(it.toString(), nonce) }.isFailure) }
            }
            test("neutral on input loss; duplex ACK") { connected { _, peer ->
                send(peer, frame(active = false))
                val ack = SignedFrames.decode(peer.getInputStream().bufferedReader().readLine(), token)
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
            test("HMAC wrong key and tampering rejected; Python key fingerprint") {
                check(SignedFrames.pairingCode(token) == "66687AAD")
                val encoded = SignedFrames.encode(JSONObject(frame()), token)
                check(SignedFrames.decode(encoded, token).getString("type") == "control")
                check(runCatching { SignedFrames.decode(encoded, "01".repeat(32)) }.isFailure)
                val altered = JSONObject(encoded).put("mac", "00".repeat(32)).toString()
                check(runCatching { SignedFrames.decode(altered, token) }.isFailure)
                check(runCatching { SignedFrames.decode(frame(), token) }.isFailure)
            }
            test("Python-produced Unicode HMAC golden frame") {
                val fixture = """{"version":2,"payload":"{\"version\":2,\"text\":\"\u015awie\u017ca bateria\",\"value\":0.25}","mac":"051d1f55f9ece268f1f82ac1c4817c22cd381c67a5644f26239cf911a863c3a1"}"""
                val decoded = SignedFrames.decode(fixture, token)
                check(decoded.getString("text") == "Świeża bateria" && decoded.getDouble("value") == .25)
            }
            test("first active frame rejected before ACK handshake") {
                ServerSocket(0).use { server ->
                    server.soTimeout = 2000
                    val client = NetworkClient()
                    try {
                        client.connect(server.localPort, token)
                        server.accept().use { peer ->
                            peer.soTimeout = 1500
                            nonce = SignedFrames.decode(peer.getInputStream().bufferedReader().readLine(), token).getString("clientNonce")
                            send(peer, frame())
                            waitUntil { BridgeState.snapshot.status.contains("Pierwszy pakiet") }
                            check(BridgeState.snapshot.yaw == 0f && !client.isRunning)
                        }
                    } finally { client.shutdown() }
                }
            }
            test("wrong per-connection nonce goes neutral") { connected { _, peer ->
                send(peer, frame()); waitUntil { BridgeState.snapshot.yaw == .4f }
                send(peer, JSONObject(frame(2)).put("clientNonce", "old").toString())
                waitUntil { BridgeState.snapshot.yaw == 0f }
            } }
            test("remote STOP latches and rejects following active frame") { connected { _, peer ->
                send(peer, frame()); waitUntil { BridgeState.snapshot.yaw == .4f }
                send(peer, JSONObject(frame(2, false)).put("emergency", true).toString())
                waitUntil { BridgeState.snapshot.status.contains("STOP Windows") }
                runCatching { send(peer, frame(3)) }; Thread.sleep(100)
                check(BridgeState.snapshot.yaw == 0f)
            } }
            test("battery warning is advisory; stale values cannot trigger cutoff") {
                val dji = JSONObject().put("batteryFresh", false).put("battery", JSONObject().put("percent", 10))
                check(!SafetyAssessment.criticalBattery(dji))
                dji.put("batteryFresh", true); check(SafetyAssessment.criticalBattery(dji))
                dji.getJSONObject("battery").put("percent", 90); check(!SafetyAssessment.criticalBattery(dji))
                check(SafetyAssessment.message(JSONObject()).contains("Brak ochrony antykolizyjnej"))
            }
            test("external connect Intent does not connect; own UI layout/render") {
                val activity = startActivitySync(android.content.Intent(targetContext, MainActivity::class.java)
                    .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK).putExtra("connect", true).putExtra("pairingToken", token))
                waitForIdleSync()
                check(!BridgeService.sessionActive())
                runOnMainSync {
                    val view = activity.window.decorView
                    check(view.width > 0 && view.height > 0)
                    val bitmap = android.graphics.Bitmap.createBitmap(view.width, view.height, android.graphics.Bitmap.Config.ARGB_8888)
                    view.draw(android.graphics.Canvas(bitmap))
                    java.io.File(targetContext.filesDir, "operator-ui-review.png").outputStream().use {
                        bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, it)
                    }
                    bitmap.recycle(); activity.finish()
                }
            }
            test("SDK rejection after USB grant does not blame the cable") {
                val message = ConnectionMessages.sdkStartRejectedAfterUsbGrant()
                check(message.contains("GRANTED") && message.contains("startConnectionToProduct() zwróciło false"))
                check(message.contains("przyczyna nieustalona") && message.contains("nie diagnoza"))
                check(!message.contains("przepnij kabel") && !message.contains("wymień kabel"))
            }
            finish(1, Bundle().apply { putString("stream", "OK: $passed tests; no flight commands\n") })
        } catch (error: Throwable) {
            finish(0, Bundle().apply { putString("stream", "FAILED after $passed tests: $error\n") })
        }
    }
}
