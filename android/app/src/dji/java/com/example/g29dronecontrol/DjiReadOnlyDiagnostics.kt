package com.example.g29dronecontrol

import android.content.Context
import android.os.SystemClock
import dji.common.error.DJIError
import dji.common.error.DJISDKError
import dji.sdk.base.BaseComponent
import dji.sdk.base.BaseProduct
import dji.sdk.battery.Battery
import dji.sdk.flightcontroller.FlightController
import dji.sdk.products.Aircraft
import dji.sdk.sdkmanager.DJISDKInitEvent
import dji.sdk.sdkmanager.DJISDKManager
import org.json.JSONObject
import java.util.concurrent.Executors

/** Real official SDK integration, deliberately NO flight/camera/configuration setters. */
class DjiReadOnlyDiagnostics : SdkDiagnostics {
    override val enabled = true
    private val gate = Any()
    private val worker = Executors.newSingleThreadExecutor()
    private var registering = false
    private var registered = false
    private var reading = false
    private var generation = 0L
    private var flight: FlightController? = null
    private var battery: Battery? = null

    private fun fail(error: Throwable) {
        SdkState.update { it.copy(error = "${error.javaClass.simpleName}: ${error.message.orEmpty().take(100)}") }
    }

    override fun register(context: Context) {
        synchronized(gate) {
            if (registering || registered) return
            registering = true
            SdkState.update { it.copy(registration = "REGISTERING", error = "") }
        }
        worker.execute {
            try {
                val manager = DJISDKManager.getInstance()
                manager.setAnalyticsEventPrivacyPermission(false)
                manager.registerApp(context.applicationContext, callback)
            } catch (error: Throwable) {
                synchronized(gate) { registering = false }
                SdkState.update { it.copy(registration = "FAILED") }; fail(error)
            }
        }
    }

    private val callback = object : DJISDKManager.SDKManagerCallback {
        override fun onRegister(error: DJIError?) {
            synchronized(gate) {
                registering = false
                registered = error == DJISDKError.REGISTRATION_SUCCESS
                SdkState.update { it.copy(registration = if (registered) "REGISTERED" else "FAILED",
                    error = if (registered) "" else error?.description?.take(180) ?: "Brak wyniku rejestracji") }
                // Do NOT start USB/product connection as a side effect of registration.
            }
        }
        override fun onProductDisconnect() {
            synchronized(gate) {
                clearCallbacks()
                SdkState.update { it.copy(productConnected = false, rcConnected = false,
                    flightControllerConnected = false, lastFlightAt = 0, lastBatteryAt = 0,
                    flightJson = "{}", batteryJson = "{}") }
            }
        }
        override fun onProductConnect(product: BaseProduct?) { observe(product) }
        override fun onProductChanged(product: BaseProduct?) { observe(product) }
        override fun onComponentChange(key: BaseProduct.ComponentKey?, old: BaseComponent?, new: BaseComponent?) {
            runCatching {
                new?.setComponentListener { runCatching { observe(DJISDKManager.getInstance().product) }.onFailure { fail(it) } }
                observe(DJISDKManager.getInstance().product)
            }.onFailure { fail(it) }
        }
        override fun onInitProcess(event: DJISDKInitEvent?, total: Int) {
            SdkState.update { it.copy(initProgress = total.coerceIn(0, 100)) }
        }
        override fun onDatabaseDownloadProgress(current: Long, total: Long) {}
    }

    override fun connectReadOnly() {
        synchronized(gate) {
            if (!registered) {
                SdkState.update { it.copy(error = "Najpierw zarejestruj SDK.") }; return
            }
            if (reading) return
            reading = true; generation++
            SdkState.update { it.copy(connection = "READ_ONLY", error = "") }
            try {
                check(DJISDKManager.getInstance().startConnectionToProduct()) { "SDK odrzuciło połączenie produktu" }
                observe(DJISDKManager.getInstance().product)
            } catch (error: Throwable) { stop(); fail(error) }
        }
    }

    private fun clearCallbacks() {
        generation++ // In-flight callbacks from the previous product are no longer valid.
        runCatching { flight?.setStateCallback(null) }
        runCatching { battery?.setStateCallback(null) }
        flight = null; battery = null
    }

    private fun observe(product: BaseProduct?) {
        synchronized(gate) {
            if (!reading) return
            try {
                val aircraft = product as? Aircraft
                val nextFlight = aircraft?.flightController
                val nextBattery = product?.battery
                val changed = flight !== nextFlight || battery !== nextBattery
                if (changed) clearCallbacks()
                SdkState.update { it.copy(model = product?.model?.name ?: "UNKNOWN",
                    productConnected = product?.isConnected == true,
                    rcConnected = aircraft?.remoteController?.isConnected == true,
                    flightControllerConnected = nextFlight?.isConnected == true,
                    lastFlightAt = if (changed || nextFlight?.isConnected != true) 0 else it.lastFlightAt,
                    lastBatteryAt = if (changed) 0 else it.lastBatteryAt) }
                if (!changed) return
                flight = nextFlight; battery = nextBattery
                val token = generation
                nextFlight?.setStateCallback { value ->
                    synchronized(gate) {
                        if (!reading || token != generation || flight !== nextFlight) return@setStateCallback
                        try {
                            val sample = JSONObject().put("source", "DJI_MSDK_FLIGHT_CALLBACK")
                            fun number(name: String, value: Double) { if (value.isFinite()) sample.put(name, value) }
                            value.attitude?.let { number("pitch", it.pitch); number("roll", it.roll); number("yaw", it.yaw) }
                            value.aircraftLocation?.let {
                                number("altitudeM", it.altitude.toDouble())
                                if (value.satelliteCount >= 4 && it.latitude in -90.0..90.0 && it.longitude in -180.0..180.0) {
                                    number("latitude", it.latitude); number("longitude", it.longitude)
                                }
                            }
                            number("velocityXMps", value.velocityX.toDouble())
                            number("velocityYMps", value.velocityY.toDouble())
                            number("velocityZMps", value.velocityZ.toDouble())
                            sample.put("satellites", value.satelliteCount).put("flightMode", value.flightMode?.name ?: "UNKNOWN")
                                .put("flying", value.isFlying).put("motorsOn", value.areMotorsOn())
                            SdkState.update { it.copy(lastFlightAt = SystemClock.elapsedRealtime(),
                                productConnected = product?.isConnected == true,
                                flightControllerConnected = nextFlight.isConnected, flightJson = sample.toString()) }
                        } catch (error: Throwable) { fail(error) }
                    }
                }
                nextBattery?.setStateCallback { value ->
                    synchronized(gate) {
                        if (!reading || token != generation || battery !== nextBattery) return@setStateCallback
                        val sample = JSONObject().put("source", "DJI_MSDK_BATTERY_CALLBACK")
                        if (value.chargeRemainingInPercent in 0..100) sample.put("percent", value.chargeRemainingInPercent)
                        if (value.temperature.isFinite()) sample.put("temperatureC", value.temperature.toDouble())
                        SdkState.update { it.copy(lastBatteryAt = SystemClock.elapsedRealtime(), batteryJson = sample.toString()) }
                    }
                }
            } catch (error: Throwable) { fail(error) }
        }
    }

    override fun stop() {
        synchronized(gate) {
            val wasReading = reading
            reading = false; clearCallbacks()
            if (wasReading) runCatching { DJISDKManager.getInstance().stopConnectionToProduct() }.onFailure { fail(it) }
            SdkState.update { it.copy(connection = "STOPPED", productConnected = false,
                rcConnected = false, flightControllerConnected = false,
                lastFlightAt = 0, lastBatteryAt = 0, flightJson = "{}", batteryJson = "{}") }
        }
    }
}
