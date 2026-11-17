package com.aerovision.hub.maverick

import android.content.Context

/**
 * API-key stub check. The SDK itself loads the key from assets, searching
 * `app.key`, `sdk.[serial].key`, then `sdk.key`. The build copies the file named by
 * `maverick.api_key_file` (SECRETS.local.properties) into the assets as `sdk.key`.
 */
object MaverickApiKey {
    fun isBundled(context: Context): Boolean {
        val names = context.assets.list("").orEmpty()
        return names.any { it == "app.key" || it == "sdk.key" || (it.startsWith("sdk.") && it.endsWith(".key")) }
    }
}
