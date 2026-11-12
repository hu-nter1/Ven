package expo.modules.venbackgroundlistening

import android.content.Intent
import android.os.Build
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

class VenBackgroundListeningModule : Module() {
  override fun definition() = ModuleDefinition {
    Name("VenBackgroundListening")

    Function("start") {
      val context = appContext.reactContext?.applicationContext
        ?: throw IllegalStateException("VEN background service requires an active Android context.")
      val intent = Intent(context, VenListeningService::class.java)

      if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        context.startForegroundService(intent)
      } else {
        context.startService(intent)
      }
    }

    Function("stop") {
      val context = appContext.reactContext?.applicationContext
        ?: throw IllegalStateException("VEN background service requires an active Android context.")
      context.stopService(Intent(context, VenListeningService::class.java))
    }
  }
}
