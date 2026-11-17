package com.aerovision.hub.maverick

import UIKit.app.Screen
import UIKit.app.data.Align
import UIKit.app.data.EvsColor
import UIKit.app.resources.Font
import UIKit.widgets.Text

/** Minimal HUD: a fixed title and one message line, centred on the glasses display. */
class HudScreen : Screen() {
    private val title = Text()
    private val message = Text()

    override fun onCreate() {
        title.setText("AeroVision").setResource(Font.StockFont.Medium).setTextAlign(Align.center)
        title.setX(getWidth() / 2).setY(getHeight() / 2 - 40).setForegroundColor(EvsColor.Green.rgba)
        add(title)

        message.setText("").setResource(Font.StockFont.Medium).setTextAlign(Align.center)
        message.setX(getWidth() / 2).setY(getHeight() / 2 + 20).setForegroundColor(EvsColor.Green.rgba)
        add(message)
    }

    /** Call on the main thread (as in the Everysight samples). */
    fun showMessage(text: String) {
        message.setText(text)
    }
}
