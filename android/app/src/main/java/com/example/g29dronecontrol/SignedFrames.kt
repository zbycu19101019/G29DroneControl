package com.example.g29dronecontrol

import org.json.JSONObject
import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/** Authenticate exact UTF-8 bytes. This is authentication, NOT payload encryption. */
object SignedFrames {
    const val VERSION = 2
    fun validToken(value: String) = value.matches(Regex("[a-f0-9]{64}"))
    private fun bytes(value: String): ByteArray = value.chunked(2).map { it.toInt(16).toByte() }.toByteArray()
    private fun hex(value: ByteArray): String = value.joinToString("") { "%02x".format(it.toInt() and 255) }
    fun pairingCode(token: String): String {
        require(validToken(token))
        return hex(MessageDigest.getInstance("SHA-256").digest(bytes(token))).take(8).uppercase()
    }
    private fun signature(body: String, token: String): ByteArray {
        require(validToken(token))
        return Mac.getInstance("HmacSHA256").run {
            init(SecretKeySpec(bytes(token), "HmacSHA256"))
            doFinal(body.toByteArray(Charsets.UTF_8))
        }
    }
    fun encode(packet: JSONObject, token: String): String {
        val body = packet.toString()
        return JSONObject().put("version", VERSION).put("payload", body)
            .put("mac", hex(signature(body, token))).toString()
    }
    fun decode(frame: String, token: String): JSONObject {
        val envelope = JSONObject(frame)
        require(envelope.length() == 3 && envelope.get("version") == VERSION)
        require(envelope.get("payload") is String && envelope.get("mac") is String)
        val body = envelope.getString("payload")
        val mac = envelope.getString("mac")
        require(body.toByteArray(Charsets.UTF_8).size <= 16000 && mac.matches(Regex("[a-f0-9]{64}")))
        require(MessageDigest.isEqual(signature(body, token), bytes(mac))) { "Nieprawidłowy podpis HMAC" }
        return JSONObject(body)
    }
}
