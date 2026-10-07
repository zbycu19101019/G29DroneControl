package com.example.g29dronecontrol

import android.content.Context
import android.hardware.usb.UsbManager
import org.json.JSONArray
import org.json.JSONObject

/** Descriptors only: never opens endpoints, asks permission, or takes over DJI Fly. */
object UsbDiagnostics {
    fun snapshot(context: Context): JSONObject {
        val manager = context.getSystemService(Context.USB_SERVICE) as UsbManager
        val devices = JSONArray()
        manager.deviceList.values.take(8).forEach { device ->
            devices.put(JSONObject().put("vid", device.vendorId).put("pid", device.productId)
                .put("name", device.productName?.take(100) ?: "?")
                .put("manufacturer", device.manufacturerName?.take(100) ?: "?")
                .put("interfaces", device.interfaceCount).put("permission", manager.hasPermission(device)))
        }
        val accessories = JSONArray()
        manager.accessoryList?.take(8)?.forEach { accessory ->
            accessories.put(JSONObject().put("manufacturer", accessory.manufacturer?.take(100) ?: "?")
                .put("model", accessory.model?.take(100) ?: "?")
                .put("description", accessory.description?.take(100) ?: "?")
                .put("permission", manager.hasPermission(accessory)))
        }
        return JSONObject().put("devices", devices).put("accessories", accessories)
            .put("aircraftConnection", "UNKNOWN").put("descriptorOnly", true)
    }
    fun summary(context: Context): String = snapshot(context).toString(2) +
        "\n\nUSB ≠ połączenie radiowe z dronem. Brak komend do RC-N1."
}
