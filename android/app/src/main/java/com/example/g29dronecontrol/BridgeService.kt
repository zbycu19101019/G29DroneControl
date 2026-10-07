package com.example.g29dronecontrol

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Handler
import android.os.IBinder
import android.os.Looper

/** Foreground bench bridge remains active while DJI Fly is in front. */
class BridgeService : Service() {
    companion object {
        @Volatile private var instance: BridgeService? = null
        fun emergencyStop() { instance?.network?.stop(); SdkState.adapter.stop(); BridgeState.neutral("STOP / ZERO") }
    }
    private lateinit var network: NetworkClient
    private val handler = Handler(Looper.getMainLooper())
    private val diagnostics = object : Runnable {
        override fun run() {
            BridgeState.usbJson = runCatching { UsbDiagnostics.snapshot(this@BridgeService).toString() }.getOrDefault("{}")
            handler.postDelayed(this, 2000)
        }
    }
    override fun onCreate() {
        super.onCreate()
        network = NetworkClient()
        instance = this
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel("bridge", "G29 most diagnostyczny", NotificationManager.IMPORTANCE_LOW))
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val stop = PendingIntent.getService(this, 1, Intent(this, BridgeService::class.java).setAction("STOP"), PendingIntent.FLAG_IMMUTABLE)
        val notification = Notification.Builder(this, "bridge").setSmallIcon(android.R.drawable.ic_menu_compass)
            .setContentTitle("G29 Bridge / ${SdkState.mode()}").setContentText("ACK + diagnostyka. Bez sterowania dronem.")
            .setContentIntent(open).addAction(Notification.Action.Builder(null, "STOP", stop).build()).setOngoing(true).build()
        startForeground(29, notification)
        diagnostics.run()
    }
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == "STOP") { emergencyStop(); stopSelf(); return START_NOT_STICKY }
        val port = intent?.getIntExtra("port", 8765) ?: 8765
        if (port in 1024..65535) network.connect(port) else { BridgeState.neutral("Błędny port"); stopSelf() }
        return START_NOT_STICKY
    }
    override fun onTimeout(startId: Int, fgsType: Int) { network.stop(); stopSelf() }
    override fun onDestroy() { network.shutdown(); instance = null; handler.removeCallbacksAndMessages(null); super.onDestroy() }
    override fun onBind(intent: Intent?): IBinder? = null
}
