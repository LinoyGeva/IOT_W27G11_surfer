package org.aerovision.maverick

import UIKit.app.Screen
import UIKit.app.data.Align
import UIKit.app.data.EvsColor
import UIKit.app.resources.Font
import UIKit.widgets.Text
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class HudTest {
    @Test
    fun blinkMessage() {
        MaverickSession("hud").use { glasses ->
            glasses.connect()
            val text = Text()
            val screen = object : Screen() {
                override fun onCreate() {
                    text.setText("MAVERICK OK")
                        .setResource(Font.StockFont.Large)
                        .setTextAlign(Align.center)
                    text.setXY(getWidth() / 2, getHeight() / 2)
                    text.setForegroundColor(EvsColor.Green.rgba)
                    add(text)
                }
            }
            try {
                glasses.onMain {
                    glasses.app.screens().addScreen(screen)
                    glasses.app.display().turnDisplayOn()
                    glasses.log("HUD_START message=MAVERICK_OK duration_s=16")
                }
                repeat(16) { second ->
                    val visible = second % 2 == 0
                    glasses.onMain { text.setVisibility(visible) }
                    glasses.log("HUD second=$second visible=$visible")
                    Thread.sleep(1000)
                    glasses.checkReady()
                }
            } catch (error: Throwable) {
                glasses.log("FAIL test=hud reason=${error.message}")
                throw error
            } finally {
                glasses.onMain {
                    text.setVisibility(false)
                    glasses.app.screens().removeScreen(screen)
                    glasses.app.display().turnDisplayOff()
                    glasses.log("HUD_STOP")
                }
            }
            glasses.log("PASS test=hud writes_completed=true manual_validation=pending")
        }
    }
}
