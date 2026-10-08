package com.example.g29dronecontrol;

import android.app.Application;
import android.content.Context;

/** Install DJI's original protected runtime before any DJI class is resolved. */
public final class DjiProbeApplication extends Application {
    private Throwable loadFailure;

    @Override protected void attachBaseContext(Context base) {
        super.attachBaseContext(base);
        try {
            com.cySdkyc.clx.Helper.install(this);
        } catch (Throwable failure) {
            loadFailure = failure;
        }
    }

    @Override public void onCreate() {
        super.onCreate();
        try {
            if (loadFailure != null) throw loadFailure;
            SdkState.INSTANCE.setAdapter(new DjiReadOnlyDiagnostics(this));
            SdkState.INSTANCE.setSnapshot(new SdkSnapshot("NOT_REGISTERED", "STOPPED", "UNKNOWN",
                false, false, false, 0L, 0L, "{}", "{}", "", 0, "NOT_CHECKED"));
        } catch (Throwable failure) {
            SdkState.INSTANCE.setSnapshot(new SdkSnapshot("SDK_LOAD_FAILED", "STOPPED", "UNKNOWN",
                false, false, false, 0L, 0L, "{}", "{}",
                failure.getClass().getSimpleName(), 0, "NOT_CHECKED"));
        }
    }
}
