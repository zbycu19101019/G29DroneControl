package com.example.g29dronecontrol

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.usb.UsbAccessory
import android.hardware.usb.UsbManager
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import java.util.UUID

/** Obtains Android permission only. Never opens USB or sends data to the pilot. */
class UsbAccessoryPermission(context: Context) {
    private val app = context.applicationContext
    private val manager = app.getSystemService(Context.USB_SERVICE) as UsbManager
    private val handler = Handler(Looper.getMainLooper())
    private var active: Request? = null

    data class Result(val status: String, val message: String = "") {
        val granted: Boolean get() = status == "GRANTED"
    }

    private class Request(
        val accessory: UsbAccessory,
        val intent: Intent,
        val completion: (Result) -> Unit
    ) {
        var receiver: BroadcastReceiver? = null
        var pendingIntent: PendingIntent? = null
        var timeout: Runnable? = null
    }

    companion object {
        const val TIMEOUT_MS = 30_000L

        fun isPilot(manufacturer: String?, model: String?): Boolean =
            manufacturer == "DJI" && model == "com.dji.logiclink"

        fun permissionIntent(context: Context): Intent =
            Intent("${context.packageName}.USB_PERMISSION")
                .setPackage(context.packageName)
                .setData(Uri.parse("g29-usb://permission/${UUID.randomUUID()}"))
    }

    private fun currentPilot(): UsbAccessory? = manager.accessoryList?.singleOrNull {
        isPilot(it.manufacturer, it.model)
    }

    /** Call only after the user's explicit read-only confirmation. */
    fun request(completion: (Result) -> Unit) {
        handler.post {
            cancelInternal()
            try {
                val accessory = currentPilot()
                if (accessory == null) {
                    val status = if (manager.accessoryList.isNullOrEmpty()) "NO_ACCESSORY" else "UNSUPPORTED_ACCESSORY"
                    completion(Result(status, "Brak pilota DJI RC-N1 w USB Accessory. Sprawdź kabel pilot–telefon."))
                    return@post
                }
                if (manager.hasPermission(accessory)) {
                    completion(Result("GRANTED"))
                    return@post
                }
                val request = Request(accessory, permissionIntent(app), completion)
                active = request
                val receiver = object : BroadcastReceiver() {
                    override fun onReceive(context: Context, intent: Intent) {
                        if (active !== request) return
                        if (intent.action == UsbManager.ACTION_USB_ACCESSORY_DETACHED) {
                            finish(request, Result("DETACHED", "Pilot odłączony. Podłącz USB i ponownie wybierz ODCZYT."))
                        } else if (intent.action == request.intent.action && intent.data == request.intent.data) {
                            // Do not trust extras supplied by a broadcast. Query Android's actual grant.
                            try {
                                when {
                                    currentPilot() != request.accessory -> finish(request, Result("DETACHED", "Pilot odłączony lub zmieniony."))
                                    manager.hasPermission(request.accessory) -> finish(request, Result("GRANTED"))
                                    else -> finish(request, Result("DENIED", "Nie udzielono zgody USB. Ponów ODCZYT i zaakceptuj okno Androida."))
                                }
                            } catch (_: Exception) {
                                finish(request, Result("ERROR", "Nie można sprawdzić zgody USB w Androidzie."))
                            }
                        }
                    }
                }
                val filter = IntentFilter(request.intent.action).apply {
                    addAction(UsbManager.ACTION_USB_ACCESSORY_DETACHED)
                }
                if (Build.VERSION.SDK_INT >= 33) app.registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED)
                else app.registerReceiver(receiver, filter)
                request.receiver = receiver
                // Immutable and package-scoped: no implicit mutable PendingIntent, no unsafe flags.
                // USB result extras are unnecessary; hasPermission() is the source of truth.
                request.pendingIntent = PendingIntent.getBroadcast(app, 0, request.intent,
                    PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_ONE_SHOT)
                val timeout = Runnable {
                    finish(request, Result("TIMEOUT", "Brak odpowiedzi na zgodę USB przez 30 s. Ponów ODCZYT."))
                }
                request.timeout = timeout
                handler.postDelayed(timeout, TIMEOUT_MS)
                manager.requestPermission(accessory, request.pendingIntent!!)
            } catch (_: Exception) {
                val result = Result("ERROR", "Android nie mógł wyświetlić zgody USB. Sprawdź kabel i ponów ODCZYT.")
                val request = active
                if (request != null) finish(request, result) else completion(result)
            }
        }
    }

    /** A delayed permission response must never resume a stopped SDK session. */
    fun cancel() { handler.post { cancelInternal() } }

    private fun finish(request: Request, result: Result) {
        if (active !== request) return
        cancelInternal()
        request.completion(result)
    }

    private fun cancelInternal() {
        val request = active ?: return
        active = null
        request.timeout?.let { handler.removeCallbacks(it) }
        request.receiver?.let { runCatching { app.unregisterReceiver(it) } }
        request.pendingIntent?.let { runCatching { it.cancel() } }
    }
}
