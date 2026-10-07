package com.example.g29dronecontrol
data class SimulatedDrone(var yaw:Float=0f,var pitch:Float=0f,var roll:Float=0f,var vertical:Float=0f) {
 fun step(command:ControlPacket,dt:Float){yaw+=command.yaw*dt; pitch+=command.pitch*dt; roll+=command.roll*dt; vertical+=command.vertical*dt}
 fun neutral(){yaw=0f;pitch=0f;roll=0f;vertical=0f}
}
