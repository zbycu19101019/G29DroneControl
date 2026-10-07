package com.example.g29dronecontrol.official

/**
 * Safe boundary for an official DJI SDK integration.
 * No DJI dependency is bundled here because it is licensed separately.
 * Mini 2 SE must remain rejected until DJI publishes support for it.
 */
class OfficialDjiSdkControl(private val productName: String) {
    private val supported = setOf("DJI Mini 3", "DJI Mini 3 Pro")

    fun connect(): Result<Unit> = if (productName !in supported) {
        Result.failure(UnsupportedOperationException("Model not supported by this adapter: $productName"))
    } else {
        Result.failure(NotImplementedError("Bind only to the official DJI SDK artifact and Virtual Stick API."))
    }

    fun emergencyStop() {
        // The production implementation must call the official SDK's documented neutral/stop path.
    }
}
