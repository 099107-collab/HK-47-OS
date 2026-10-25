package com.abacusai.hk47wear.ui

import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Message
import android.service.wallpaper.WallpaperService
import android.view.SurfaceHolder
import com.abacusai.hk47wear.service.Hk47CompanionService
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale

class Hk47CanvasWatchFaceService : WallpaperService() {

    override fun onCreateEngine(): Engine {
        return Engine()
    }

    inner class Engine : WallpaperService.Engine() {

        private val timeFormat = SimpleDateFormat("HH:mm:ss", Locale.US)
        private val ambientTimeFormat = SimpleDateFormat("HH:mm", Locale.US)
        private val calendar = Calendar.getInstance()

        private var isAmbient = false
        private var isLowBitAmbient = false
        private var isBurnInProtection = false

        private val backgroundPaint = Paint().apply {
            color = Color.parseColor("#0A0A0E")
        }

        private val titaniumPaint = Paint().apply {
            color = Color.parseColor("#202428")
            style = Paint.Style.STROKE
            strokeWidth = 6f
            isAntiAlias = true
        }

        private val photoreceptorPaint = Paint().apply {
            color = Color.parseColor("#FF3D00")
            style = Paint.Style.FILL
            isAntiAlias = true
        }

        private val coreGlowPaint = Paint().apply {
            color = Color.parseColor("#FFD54F")
            style = Paint.Style.FILL
            isAntiAlias = true
        }

        private val textPaint = Paint().apply {
            color = Color.parseColor("#F0F0F0")
            textSize = 38f
            textAlign = Paint.Align.CENTER
            isAntiAlias = true
            isFakeBoldText = true
        }

        private val hudSubPaint = Paint().apply {
            color = Color.parseColor("#E65100")
            textSize = 18f
            textAlign = Paint.Align.CENTER
            isAntiAlias = true
        }

        private val updateHandler = object : Handler(Looper.getMainLooper()) {
            override fun handleMessage(msg: Message) {
                invalidate()
                if (isVisible && !isAmbient) {
                    val delayMs = 1000 - (System.currentTimeMillis() % 1000)
                    sendEmptyMessageDelayed(0, delayMs)
                }
            }
        }

        override fun onVisibilityChanged(visible: Boolean) {
            super.onVisibilityChanged(visible)
            if (visible) {
                updateHandler.sendEmptyMessage(0)
            } else {
                updateHandler.removeMessages(0)
            }
        }

        override fun onSurfaceChanged(holder: SurfaceHolder?, format: Int, width: Int, height: Int) {
            super.onSurfaceChanged(holder, format, width, height)
            invalidate()
        }

        override fun onDraw(canvas: Canvas?, bounds: Rect?) {
            if (canvas == null || bounds == null) return

            calendar.timeInMillis = System.currentTimeMillis()
            val centerX = bounds.exactCenterX()
            val centerY = bounds.exactCenterY()
            val radius = Math.min(centerX, centerY)

            // Background
            if (isAmbient) {
                canvas.drawColor(Color.BLACK)
            } else {
                canvas.drawPaint(backgroundPaint)
                // Outer titanium armor ring
                canvas.drawCircle(centerX, centerY, radius - 8f, titaniumPaint)
            }

            // Photoreceptors (Twin Glowing Eyes of HK-47)
            val eyeWidth = 36f
            val eyeHeight = 12f
            val eyeSpacing = 28f
            val eyeY = centerY - 55f

            if (!isAmbient) {
                // Left photoreceptor glow & core
                canvas.drawRect(centerX - eyeSpacing - eyeWidth, eyeY, centerX - eyeSpacing, eyeY + eyeHeight, photoreceptorPaint)
                canvas.drawRect(centerX - eyeSpacing - eyeWidth + 8f, eyeY + 2f, centerX - eyeSpacing - 8f, eyeY + eyeHeight - 2f, coreGlowPaint)

                // Right photoreceptor glow & core
                canvas.drawRect(centerX + eyeSpacing, eyeY, centerX + eyeSpacing + eyeWidth, eyeY + eyeHeight, photoreceptorPaint)
                canvas.drawRect(centerX + eyeSpacing + 8f, eyeY + 2f, centerX + eyeSpacing + eyeWidth - 8f, eyeY + eyeHeight - 2f, coreGlowPaint)

                // HK-47 Unit Tag
                canvas.drawText("HK-47 CORE", centerX, centerY - 80f, hudSubPaint)
            } else {
                // Dim outline in ambient mode
                photoreceptorPaint.color = Color.parseColor("#882200")
                canvas.drawRect(centerX - eyeSpacing - eyeWidth, eyeY, centerX - eyeSpacing, eyeY + eyeHeight, photoreceptorPaint)
                canvas.drawRect(centerX + eyeSpacing, eyeY, centerX + eyeSpacing + eyeWidth, eyeY + eyeHeight, photoreceptorPaint)
            }

            // Time Display
            val timeText = if (isAmbient) ambientTimeFormat.format(calendar.time) else timeFormat.format(calendar.time)
            textPaint.color = if (isAmbient) Color.WHITE else Color.parseColor("#F0F0F0")
            canvas.drawText(timeText, centerX, centerY + 18f, textPaint)

            // Telemetry Gauges (Interactive Mode)
            if (!isAmbient) {
                val service = Hk47CompanionService.instance
                val packet = service?.getLatestTelemetry()
                val hrText = if (packet != null && packet.hrBpm > 0) "${packet.hrBpm} BPM" else "-- BPM"
                val stepsText = "${packet?.stepCount ?: 0} STEPS"
                val moodText = "MOOD: ${packet?.mood?.displayName ?: "STANDARD"}"

                hudSubPaint.textSize = 14f
                canvas.drawText(moodText, centerX, centerY + 50f, hudSubPaint)

                hudSubPaint.textSize = 13f
                hudSubPaint.color = Color.parseColor("#FF5252")
                canvas.drawText("HR: $hrText", centerX - 55f, centerY + 80f, hudSubPaint)

                hudSubPaint.color = Color.parseColor("#00E5FF")
                canvas.drawText(stepsText, centerX + 55f, centerY + 80f, hudSubPaint)
            }
        }

        override fun onPropertiesChanged(properties: Bundle?) {
            super.onPropertiesChanged(properties)
            isLowBitAmbient = properties?.getBoolean(PROPERTY_LOW_BIT_AMBIENT, false) ?: false
            isBurnInProtection = properties?.getBoolean(PROPERTY_BURN_IN_PROTECTION, false) ?: false
        }

        fun onAmbientModeChanged(inAmbientMode: Boolean) {
            isAmbient = inAmbientMode
            if (isLowBitAmbient) {
                photoreceptorPaint.isAntiAlias = !inAmbientMode
                textPaint.isAntiAlias = !inAmbientMode
            }
            invalidate()
            if (!inAmbientMode) {
                updateHandler.sendEmptyMessage(0)
            }
        }

        override fun onDestroy() {
            updateHandler.removeMessages(0)
            super.onDestroy()
        }
    }

    companion object {
        const val PROPERTY_LOW_BIT_AMBIENT = "low_bit_ambient"
        const val PROPERTY_BURN_IN_PROTECTION = "burn_in_protection"
    }
}
