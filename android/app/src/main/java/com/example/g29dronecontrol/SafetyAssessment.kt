package com.example.g29dronecontrol

import org.json.JSONObject

/** Advisory only: no distance sensors, no flight authority, no motor/RTH calls. */
object SafetyAssessment {
    fun criticalBattery(dji: JSONObject): Boolean {
        if (!dji.optBoolean("batteryFresh", false)) return false
        val percent = dji.optJSONObject("battery")?.optDouble("percent", Double.NaN) ?: Double.NaN
        return percent.isFinite() && percent in 0.0..20.0
    }
    fun message(dji: JSONObject): String {
        val percent = dji.optJSONObject("battery")?.optDouble("percent", Double.NaN) ?: Double.NaN
        val batteryText = if (dji.optBoolean("batteryFresh") && percent.isFinite()) {
            when {
                percent <= 20 -> "Niska bateria ${percent.toInt()}% — zakończ test."
                percent <= 30 -> "Bateria ${percent.toInt()}% — przygotuj zakończenie testu."
                else -> "Bateria ${percent.toInt()}%."
            }
        } else "Stan baterii nieznany."
        val data = if (dji.optBoolean("telemetryFresh")) "Świeży callback SDK — odczyt niezweryfikowany na tym dronie." else "Brak świeżej telemetrii drona."
        return "$batteryText\n$data\nMini 2 SE nie wykrywa ścian. Brak ochrony antykolizyjnej. Sterowanie lotem wyłączone."
    }
}
