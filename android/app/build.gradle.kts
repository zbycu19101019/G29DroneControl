import java.util.Properties

plugins { id("com.android.application") }

// The default build keeps the existing, dependency-free bench bridge.
// -PwithDjiSdk=true adds the UNMODIFIED official SDK and read-only probe.
val withDjiSdk = providers.gradleProperty("withDjiSdk").orNull == "true"
val privateKeys = Properties()
val privateFile = rootProject.file(providers.environmentVariable("DJI_KEYS_FILE").orNull
    ?: "../../../work/dji-private.properties")
if (withDjiSdk && privateFile.isFile) privateFile.inputStream().use { privateKeys.load(it) }
val appKey = providers.environmentVariable("DJI_APP_KEY").orNull
    ?: privateKeys.getProperty("djiAppKey", "")
if (withDjiSdk) require(appKey.matches(Regex("[a-fA-F0-9]{24}"))) {
    "Provide a DJI Android App Key via DJI_APP_KEY or DJI_KEYS_FILE. Do not commit it."
}

android {
    namespace = "com.example.g29dronecontrol"
    compileSdk = 37
    defaultConfig {
        applicationId = "com.example.g29dronecontrol"
        minSdk = 26
        // SDK v4.18's official sample targets 34; this is not an Android 16 certification.
        targetSdk = if (withDjiSdk) 34 else 35
        versionCode = if (withDjiSdk) 4 else 3
        versionName = if (withDjiSdk) "0.4-dji-readonly" else "0.3-audit"
        testInstrumentationRunner = "com.example.g29dronecontrol.BridgeInstrumentation"
        if (withDjiSdk) {
            manifestPlaceholders["djiAppKey"] = appKey
            ndk { abiFilters += "arm64-v8a" }
        }
    }
    if (withDjiSdk) {
        sourceSets.getByName("main") {
            java.directories += "src/dji/java"
            kotlin.directories += "src/dji/java"
            manifest.srcFile("src/dji/AndroidManifest.xml")
        }
        useLibrary("org.apache.http.legacy")
        packaging {
            jniLibs { useLegacyPackaging = true; keepDebugSymbols += "**/*.so" }
            resources.excludes += setOf("META-INF/rxjava.properties")
        }
    }
}

dependencies {
    if (withDjiSdk) {
        implementation("com.dji:dji-sdk:4.18") { exclude(module = "library-anti-distortion") }
        compileOnly("com.dji:dji-sdk-provided:4.18")
        // SDK resources reference these attributes even when our UI uses stock widgets.
        implementation("androidx.appcompat:appcompat:1.8.0")
        implementation("androidx.constraintlayout:constraintlayout:2.2.2")
        // Keep fly-safe-database: this project never removes DJI flight safeguards.
    }
}
