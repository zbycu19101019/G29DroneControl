package com.example.g29dronecontrol

import org.json.JSONObject

/** Versioned bench protocol. Never implies that an aircraft accepted a command. */
data class ControlPacket(val session: String, val seq: Long, val active: Boolean,
    val yaw: Float, val pitch: Float, val roll: Float, val vertical: Float) {
    companion object {
        fun parse(line: String): ControlPacket {
            val o = JSONObject(line)
            require(o.get("version") == 1 && o.getString("type") == "control")
            val session = o.getString("sessionId")
            require(session.matches(Regex("[a-f0-9]{32}")))
            val sequence = o.get("seq")
            require(sequence is Int || sequence is Long)
            val seq = (sequence as Number).toLong()
            require(seq >= 0)
            require(o.get("inputConnected") is Boolean && o.get("emergency") is Boolean)
            require(o.get("heartbeat") == true)
            val output = o.getJSONObject("output")
            fun channel(name: String): Float {
                val number = output.get(name)
                require(number is Number)
                val value = number.toDouble()
                require(value.isFinite() && value in -1.0..1.0)
                return value.toFloat()
            }
            return ControlPacket(session, seq, o.getBoolean("inputConnected") && !o.getBoolean("emergency"),
                channel("yaw"), channel("pitch"), channel("roll"), channel("vertical"))
        }
    }
}

data class BridgeSnapshot(val status: String = "STOP / ZERO", val seq: Long = -1,
    val yaw: Float = 0f, val pitch: Float = 0f, val roll: Float = 0f, val vertical: Float = 0f)

object BridgeState {
    @Volatile var snapshot = BridgeSnapshot()
    @Volatile var usbJson: String = "{}"
    fun neutral(reason: String) { snapshot = BridgeSnapshot(reason) }
    fun apply(packet: ControlPacket) {
        snapshot = if (packet.active) BridgeSnapshot("PC ACK / KANAŁY TESTOWE", packet.seq,
            packet.yaw, packet.pitch, packet.roll, packet.vertical)
        else BridgeSnapshot("NEUTRAL / wejście nieaktywne", packet.seq)
    }
}
