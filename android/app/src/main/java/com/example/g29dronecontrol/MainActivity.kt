package com.example.g29dronecontrol

import android.app.Activity
import android.app.AlertDialog
import android.Manifest
import android.content.pm.PackageManager
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.*

class MainActivity : Activity() {
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var status: TextView
    private lateinit var output: TextView
    private lateinit var usb: TextView
    private lateinit var sdk: TextView
    private var port = 8765
    private val refresh = object : Runnable {
        override fun run() {
            val s = BridgeState.snapshot
            status.text = getString(R.string.bridge_status, s.status, s.seq)
            output.text = getString(R.string.bridge_channels, s.yaw, s.pitch, s.roll, s.vertical)
            usb.text = getString(R.string.bridge_usb, runCatching { org.json.JSONObject(BridgeState.usbJson).toString(2) }.getOrDefault("--"))
            sdk.text = "DJI SDK / TYLKO ODCZYT\n" + SdkState.json().toString(2)
            handler.postDelayed(this, 200)
        }
    }
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.rgb(7, 12, 16)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(28, 28, 28, 28); setBackgroundColor(Color.rgb(7, 12, 16)) }
        fun label(text: String, size: Float): TextView = TextView(this).apply {
            this.text = text; textSize = size; setTextColor(Color.rgb(0, 230, 193)); typeface = android.graphics.Typeface.MONOSPACE; setPadding(0, 12, 0, 12)
        }
        root.addView(label("G29 / ANDROID BRIDGE\n${SdkState.mode()}", 21f))
        root.addView(label("Bez poleceń lotu. USB ≠ połączenie z dronem. Mini 2 SE nie ma oficjalnego wsparcia SDK. Odczyt DJI jest osobnym, ręcznie uruchamianym testem.", 14f))
        status = label("STOP", 15f); output = label("ZERO", 22f); usb = label("USB: --", 12f)
        root.addView(status); root.addView(output)
        root.addView(Button(this).apply { setText(R.string.connect_pc); setOnClickListener { connect() } })
        root.addView(Button(this).apply { setText(R.string.stop_bridge); setTextColor(Color.RED); setOnClickListener { BridgeService.emergencyStop(); stopService(Intent(this@MainActivity, BridgeService::class.java)) } })
        sdk = label("DJI SDK: --", 12f)
        if (SdkState.adapter.enabled) {
            root.addView(Button(this).apply { text = "1. REJESTRUJ DJI SDK (INTERNET)"; setOnClickListener { registerSdk() } })
            root.addView(Button(this).apply { text = "2. ODCZYT DJI / BEZ KOMEND LOTU"; setOnClickListener {
                AlertDialog.Builder(this@MainActivity).setTitle("Test tylko na ziemi")
                    .setMessage("Zdejmij śmigła, zamknij DJI Fly, pozostaw pilot podłączony. Test może przejąć USB od DJI Fly. Nie uruchamia silników i nie włącza Virtual Stick. Zera bez callbacku NIE są telemetrią.")
                    .setNegativeButton("Anuluj", null)
                    .setPositiveButton("Gotowe — odczyt", { _, _ -> SdkState.adapter.connectReadOnly() }).show()
            } })
            root.addView(Button(this).apply { text = "ZATRZYMAJ ODCZYT DJI"; setOnClickListener { SdkState.adapter.stop() } })
        }
        root.addView(sdk)
        root.addView(Button(this).apply { setText(R.string.refresh_usb); setOnClickListener { BridgeState.usbJson = UsbDiagnostics.snapshot(this@MainActivity).toString() } })
        root.addView(usb)
        setContentView(ScrollView(this).apply { addView(root) })
        BridgeState.usbJson = UsbDiagnostics.snapshot(this).toString()
        acceptIntent(intent)
    }
    private fun connect() { startForegroundService(Intent(this, BridgeService::class.java).putExtra("port", port)) }
    private fun registerSdk() {
        val required = arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION,
            Manifest.permission.READ_PHONE_STATE)
        val missing = required.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) {
            requestPermissions(missing.toTypedArray(), 418)
        } else SdkState.adapter.register(this)
    }
    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 418) {
            if (grantResults.isNotEmpty() && grantResults.all { it == PackageManager.PERMISSION_GRANTED })
                SdkState.adapter.register(this)
            else SdkState.update { it.copy(error = "Brak zgód wymaganych przez SDK. Nie nadano ich automatycznie.") }
        }
    }
    private fun acceptIntent(value: Intent) {
        port = value.getIntExtra("port", 8765)
        if (value.getBooleanExtra("connect", false)) connect()
    }
    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); setIntent(intent); acceptIntent(intent) }
    override fun onResume() { super.onResume(); refresh.run() }
    override fun onPause() { handler.removeCallbacks(refresh); super.onPause() }
}
