package expo.modules.venbackgroundlistening

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder

class VenListeningService : Service() {
  override fun onCreate() {
    super.onCreate()
    createNotificationChannel()
  }

  override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
    val notification = buildNotification()

    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
      startForeground(
        NOTIFICATION_ID,
        notification,
        ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE,
      )
    } else {
      startForeground(NOTIFICATION_ID, notification)
    }

    return START_NOT_STICKY
  }

  override fun onBind(intent: Intent?): IBinder? = null

  override fun onDestroy() {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
      stopForeground(STOP_FOREGROUND_REMOVE)
    } else {
      @Suppress("DEPRECATION")
      stopForeground(true)
    }
    super.onDestroy()
  }

  private fun createNotificationChannel() {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return

    val channel = NotificationChannel(
      CHANNEL_ID,
      "VEN voice listening",
      NotificationManager.IMPORTANCE_LOW,
    ).apply {
      description = "Shown while VEN is listening for voice input."
    }

    getSystemService(NotificationManager::class.java)
      .createNotificationChannel(channel)
  }

  private fun buildNotification(): Notification {
    val launchIntent = packageManager.getLaunchIntentForPackage(packageName)
    val contentIntent = launchIntent?.let {
      PendingIntent.getActivity(
        this,
        0,
        it,
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
      )
    }

    val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
      Notification.Builder(this, CHANNEL_ID)
    } else {
      @Suppress("DEPRECATION")
      Notification.Builder(this)
    }

    return builder
      .setSmallIcon(android.R.drawable.ic_btn_speak_now)
      .setContentTitle("VEN is listening")
      .setContentText("Voice listening is active. Tap to return to VEN.")
      .setCategory(Notification.CATEGORY_SERVICE)
      .setOngoing(true)
      .setOnlyAlertOnce(true)
      .setContentIntent(contentIntent)
      .build()
  }

  companion object {
    private const val CHANNEL_ID = "ven_voice_listening"
    private const val NOTIFICATION_ID = 4217
  }
}
