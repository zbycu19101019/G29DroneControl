package com.example.g29dronecontrol

import android.content.Context
import android.os.SystemClock
import org.json.JSONObject

/** No SDK classes here: the bench APK can still run independently. */
interface SdkDiagnostics {
    val enabled: Boolean
    fun register(context: Context)
    fun connectReadOnly()
    fun stop()
}

class NoSdkDiagnostics : SdkDiagnostics {
    override val enabled = false
    override fun register(context: Context) {}
    override fun connectReadOnly() {}
    override fun stop() {}
}

data class SdkSnapshot(
    val registration: String = "SDK_NOT_INCLUDED",
    val connection: String = "STOPPED",
    val model: String = "UNKNOWN",
    val productConnected: Boolean = false,
    val rcConnected: Boolean = false,
    val flightControllerConnected: Boolean = false,
    val lastFlightAt: Long = 0,
    val lastBatteryAt: Long = 0,
    val flightJson: String = "{}",
    val batteryJson: String = "{}",
    val error: String = "",
    val initProgress: Int = 0,
    val usbPermission: String = "NOT_CHECKED"
) {
    fun toJson(now: Long = SystemClock.elapsedRealtime()): JSONObject {
        val flightAge = if (lastFlightAt > 0) (now - lastFlightAt).coerceAtLeast(0) else -1
        val batteryAge = if (lastBatteryAt > 0) (now - lastBatteryAt).coerceAtLeast(0) else -1
        val flightFresh = connection == "READ_ONLY" && productConnected &&
            flightControllerConnected && flightAge in 0..1500
        val batteryFresh = connection == "READ_ONLY" && productConnected && batteryAge in 0..3000
        return JSONObject().put("registration", registration).put("connection", connection)
            .put("sdkVersion", if (registration == "SDK_NOT_INCLUDED") "none" else "4.18")
            .put("model", model).put("productConnected", productConnected)
            .put("rcConnected", rcConnected).put("flightControllerConnected", flightControllerConnected)
            .put("flightControl", false).put("officialMini2SeSupport", false)
            .put("telemetryFresh", flightFresh).put("telemetryAgeMs", flightAge)
            .put("batteryFresh", batteryFresh).put("batteryAgeMs", batteryAge)
            .put("validation", "SDK_CALLBACKS_NOT_HARDWARE_VERIFIED")
            .put("telemetry", if (flightFresh) JSONObject(flightJson) else JSONObject.NULL)
            .put("battery", if (batteryFresh) JSONObject(batteryJson) else JSONObject.NULL)
            .put("error", error.take(180)).put("initProgress", initProgress)
            .put("usbPermission", usbPermission)
    }
}

object SdkState {
    @Volatile var adapter: SdkDiagnostics = NoSdkDiagnostics()
    @Volatile var snapshot = SdkSnapshot()
    @Synchronized fun update(transform: (SdkSnapshot) -> SdkSnapshot) { snapshot = transform(snapshot) }
    fun json(): JSONObject = snapshot.toJson()
    fun mode(): String = if (adapter.enabled) "DJI_SDK_READ_ONLY" else "MOCK_ONLY"
}
