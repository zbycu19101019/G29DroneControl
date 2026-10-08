package com.example.g29dronecontrol

/** A USB descriptor/grant is evidence of USB, not proof of SDK compatibility. */
object ConnectionMessages {
    fun sdkStartRejectedAfterUsbGrant() =
        "USB pilota wykryte; zgoda GRANTED. SDK startConnectionToProduct() zwróciło false. " +
        "To nie diagnoza uszkodzonego kabla. Nie uzyskano połączenia produktu ani telemetrii. " +
        "Możliwe przyczyny: inna aplikacja używa USB lub niezgodność SDK/Androida/modelu; przyczyna nieustalona. " +
        "Mini 2 SE nie ma oficjalnego wsparcia SDK. Zamknij DJI Fly ręcznie przed następnym testem."
}
