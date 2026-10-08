package com.example.g29dronecontrol

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.*
import org.json.JSONObject

/** External intents only propose a PC session; human approval is mandatory. */
class MainActivity : Activity() {
    private val handler = Handler(Looper.getMainLooper())
    private val ink = Color.rgb(20, 35, 53)
    private val muted = Color.rgb(100, 116, 139)
    private val blue = Color.rgb(37, 99, 235)
    private val red = Color.rgb(185, 28, 28)
    private val bg = Color.rgb(243, 246, 250)
    private lateinit var pc: TextView
    private lateinit var pairing: TextView
    private lateinit var aircraft: TextView
    private lateinit var safety: TextView
    private lateinit var channels: TextView
    private lateinit var details: TextView
    private lateinit var registerButton: Button
    private lateinit var readButton: Button
    private var proposedToken = ""
    private var proposedPort = 8765
    private val refresh = object : Runnable {
        override fun run() {
            refreshStatus()
            handler.postDelayed(this, 250)
        }
    }
    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
    private fun surface(color: Int = Color.WHITE): GradientDrawable = GradientDrawable().apply {
        setColor(color); cornerRadius = dp(14).toFloat(); setStroke(dp(1), Color.rgb(218, 226, 235))
    }
    private fun label(text: String, size: Float = 15f, color: Int = ink, bold: Boolean = false) = TextView(this).apply {
        this.text = text; textSize = size; setTextColor(color)
        typeface = Typeface.create(if (bold) "sans-serif-medium" else "sans-serif", Typeface.NORMAL)
        setPadding(0, dp(5), 0, dp(5))
    }
    private fun card(parent: LinearLayout, title: String): LinearLayout = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL; background = surface(); setPadding(dp(18), dp(12), dp(18), dp(14))
        parent.addView(this, LinearLayout.LayoutParams(-1, -2).apply { bottomMargin = dp(14) })
        addView(label(title, 18f, ink, true))
    }
    private fun button(parent: LinearLayout, title: String, danger: Boolean = false, action: () -> Unit): Button = Button(this).apply {
        text = title; isAllCaps = false; textSize = 15f; setTextColor(if (danger) red else blue)
        background = surface(if (danger) Color.rgb(254, 242, 242) else Color.rgb(239, 245, 255))
        minHeight = dp(48); setPadding(dp(12), dp(10), dp(12), dp(10))
        parent.addView(this, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(8) })
        setOnClickListener { action() }
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = bg; window.navigationBarColor = bg
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR or
            (if (android.os.Build.VERSION.SDK_INT >= 27) View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR else 0)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(bg) }
        val scroll = ScrollView(this).apply { isFillViewport = true }
        val body = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(18), dp(20), dp(18), dp(10)) }
        body.addView(label("G29 Operator", 28f, ink, true))
        body.addView(label("Windows + Android  •  0.6\nDiagnostyka i kanały testowe. Bez poleceń lotu.", 14f, muted))
        val safetyCard = card(body, "Bezpieczeństwo")
        safetyCard.background = surface(Color.rgb(255, 248, 235))
        safety = label("Brak ochrony przed przeszkodami", 15f, Color.rgb(146, 64, 14))
        safetyCard.addView(safety)
        val link = card(body, "Połączenie z Windows")
        pc = label("Mostek zatrzymany", 16f, ink, true); link.addView(pc)
        pairing = label("W Windows wybierz Telefon → Przygotuj połączenie.", 14f, muted); link.addView(pairing)
        button(link, "Potwierdź komputer i połącz") { confirmConnection() }
        link.addView(label("Porównaj 8-znakowy kod z Windows. Klucz sesji nie jest zapisywany. Samo otwarcie aplikacji nie uruchamia połączenia.", 13f, muted))
        val dji = card(body, "Pilot i dron")
        aircraft = label("Brak danych DJI", 15f); dji.addView(aircraft)
        if (SdkState.adapter.enabled) {
            registerButton = button(dji, "1. Zarejestruj DJI SDK") { registerSdk() }
            readButton = button(dji, "2. Rozpocznij odczyt DJI") { confirmRead() }
            button(dji, "Zatrzymaj odczyt DJI") { SdkState.adapter.stop() }
        } else dji.addView(label("Wariant testowy bez bibliotek DJI SDK.", 14f, muted))
        val input = card(body, "Kanały testowe G29")
        input.addView(label("Te wartości nie są orientacją ani komendami drona.", 13f, muted))
        channels = label("Obrót  +0.000\nPrzód / tył  +0.000\nPrzechylenie  +0.000\nPion  +0.000", 17f)
        channels.typeface = Typeface.MONOSPACE; input.addView(channels)
        val technical = card(body, "Szczegóły techniczne")
        details = label("", 12f, muted).apply { typeface = Typeface.MONOSPACE; visibility = View.GONE; setTextIsSelectable(true) }
        button(technical, "Pokaż / ukryj diagnostykę") { details.visibility = if (details.visibility == View.VISIBLE) View.GONE else View.VISIBLE; refreshStatus() }
        button(technical, "Odśwież informacje USB") { BridgeState.usbJson = UsbDiagnostics.snapshot(this).toString(); refreshStatus() }
        technical.addView(details)
        scroll.addView(body); root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        val footer = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(18), dp(4), dp(18), dp(12)); setBackgroundColor(Color.WHITE) }
        button(footer, "STOP — zatrzymaj mostek i odczyt", true) {
            BridgeService.emergencyStop(); stopService(Intent(this, BridgeService::class.java)); refreshStatus()
        }
        footer.addView(label("STOP nie wyłącza silników i nie hamuje rzeczywistego drona.", 12f, muted))
        root.addView(footer); setContentView(root)
        BridgeState.usbJson = UsbDiagnostics.snapshot(this).toString()
        acceptIntent(intent)
    }
    private fun refreshStatus() {
        val bridge = BridgeState.snapshot
        val dji = SdkState.json()
        pc.text = getString(R.string.bridge_status, bridge.status, bridge.seq)
        safety.text = SafetyAssessment.message(dji)
        channels.text = getString(R.string.bridge_channels, bridge.yaw, bridge.pitch, bridge.roll, bridge.vertical)
        val registration = dji.optString("registration")
        val product = if (dji.optBoolean("productConnected")) "połączony" else "brak połączenia"
        val fc = if (dji.optBoolean("flightControllerConnected")) "połączony" else "brak połączenia"
        aircraft.text = getString(R.string.aircraft_status, registration, dji.optString("usbPermission"), dji.optString("model"), product, fc)
        val telemetry = dji.optJSONObject("telemetry")
        if (dji.optBoolean("telemetryFresh") && telemetry != null) {
            fun number(name: String): String = telemetry.optDouble(name, Double.NaN).let { if (it.isFinite()) "%.1f".format(it) else "—" }
            aircraft.append("\nOrientacja SDK: P ${number("pitch")}°  R ${number("roll")}°  Y ${number("yaw")}°")
        }
        val error = dji.optString("error")
        if (error.isNotEmpty()) aircraft.append("\n$error")
        if (SdkState.adapter.enabled) {
            registerButton.isEnabled = registration != "REGISTERING" && registration != "REGISTERED"
            readButton.isEnabled = registration == "REGISTERED" && dji.optString("connection") == "STOPPED"
        }
        if (details.visibility == View.VISIBLE) details.text = getString(R.string.technical_status, dji.toString(2), runCatching { JSONObject(BridgeState.usbJson).toString(2) }.getOrDefault("—"))
    }
    private fun confirmConnection() {
        if (!SignedFrames.validToken(proposedToken)) {
            pairing.setText(R.string.session_missing)
            return
        }
        val token = proposedToken
        val port = proposedPort
        AlertDialog.Builder(this).setTitle("Porównaj kod z Windows")
            .setMessage("Kod komputera: ${SignedFrames.pairingCode(token)}\n\nPołącz tylko, gdy kod jest taki sam w panelu Windows. To kanał diagnostyczny, nie sterowanie dronem.")
            .setNegativeButton("Anuluj", null)
            .setPositiveButton("Kod zgodny — połącz") { _, _ ->
                startForegroundService(Intent(this, BridgeService::class.java).putExtra("port", port).putExtra("pairingToken", token))
            }.show()
    }
    private fun confirmRead() {
        val confirmed = BooleanArray(3)
        val dialog = AlertDialog.Builder(this).setTitle("Test DJI tylko na ziemi")
            .setMultiChoiceItems(arrayOf("Dron stoi na ziemi, śmigła zdjęte", "DJI Fly jest zamknięte", "Rozumiem: brak ochrony przed ścianami i komend lotu"), confirmed) { dialog, index, value ->
                confirmed[index] = value
                (dialog as AlertDialog).getButton(AlertDialog.BUTTON_POSITIVE).isEnabled = confirmed.all { it }
            }.setNegativeButton("Anuluj", null)
            .setPositiveButton("Potwierdzam — odczyt") { _, _ -> SdkState.adapter.connectReadOnly() }.create()
        dialog.setOnShowListener { dialog.getButton(AlertDialog.BUTTON_POSITIVE).isEnabled = false }
        dialog.show()
    }
    private fun registerSdk() {
        val required = arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION, Manifest.permission.READ_PHONE_STATE)
        val missing = required.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) requestPermissions(missing.toTypedArray(), 418) else SdkState.adapter.register(this)
    }
    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 418) {
            if (grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED }) SdkState.adapter.register(this)
            else SdkState.update { it.copy(error = "Brak wymaganych zgód SDK. Nie przyznano ich automatycznie.") }
        }
    }
    private fun acceptIntent(value: Intent) {
        // Never honor the old external connect=true flag, or start SDK from an Intent.
        val token = value.getStringExtra("pairingToken").orEmpty()
        val port = value.getIntExtra("port", 8765)
        if (SignedFrames.validToken(token) && port in 1024..65535) {
            if (BridgeService.sessionActive()) return
            proposedToken = token; proposedPort = port
            pairing.text = getString(R.string.session_code, SignedFrames.pairingCode(token))
            value.removeExtra("pairingToken")
        }
    }
    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); setIntent(intent); acceptIntent(intent) }
    override fun onResume() { super.onResume(); refresh.run() }
    override fun onPause() { handler.removeCallbacks(refresh); super.onPause() }
    override fun onStop() { SdkState.adapter.stop(); super.onStop() }
}
