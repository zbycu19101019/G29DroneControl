package com.example.g29dronecontrol
interface DroneControl { fun connect(): Boolean; fun disconnect(); fun setYaw(value: Float); fun setPitch(value: Float); fun setRoll(value: Float); fun setVertical(value: Float); fun emergencyStop() }
class MockDroneControl : DroneControl {
 @JvmField @Volatile var yaw=0f; @JvmField @Volatile var pitch=0f; @JvmField @Volatile var roll=0f; @JvmField @Volatile var vertical=0f
 override fun connect()=true; override fun disconnect()=emergencyStop(); override fun setYaw(v:Float){yaw=v}; override fun setPitch(v:Float){pitch=v}; override fun setRoll(v:Float){roll=v}; override fun setVertical(v:Float){vertical=v}; override fun emergencyStop(){yaw=0f;pitch=0f;roll=0f;vertical=0f}
}
/** Flight commands remain disabled. The separate optional SDK probe is read-only. */
class DisabledDjSdkDroneControl : DroneControl { override fun connect()=false; override fun disconnect(){}; override fun setYaw(v:Float){}; override fun setPitch(v:Float){}; override fun setRoll(v:Float){}; override fun setVertical(v:Float){}; override fun emergencyStop(){} }
