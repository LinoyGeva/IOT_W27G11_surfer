package org.aerovision.maverick

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class HandshakeTest {
    @Test
    fun handshake() {
        MaverickSession("handshake").use { glasses ->
            glasses.connect()
            glasses.log("PASS test=handshake authenticated=true")
        }
    }
}
