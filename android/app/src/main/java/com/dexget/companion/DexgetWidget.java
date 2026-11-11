package com.dexget.companion;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.widget.RemoteViews;

public final class DexgetWidget extends AppWidgetProvider {
    @Override public void onUpdate(Context context, AppWidgetManager manager, int[] ids) {
        for (int id : ids) update(context, manager, id);
    }

    private static PendingIntent action(Context context, String action, int requestCode) {
        Intent intent = new Intent(context, MainActivity.class);
        intent.setAction(action);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        return PendingIntent.getActivity(
                context, requestCode, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private static void update(Context context, AppWidgetManager manager, int id) {
        RemoteViews views = new RemoteViews(context.getPackageName(), R.layout.dexget_widget);
        String endpoint = context.getSharedPreferences("pairing", Context.MODE_PRIVATE)
                .getString("endpoint", "");
        views.setTextViewText(R.id.widget_status,
                endpoint.isEmpty() ? "Not paired · scan the laptop QR" : "Laptop paired · ready to transfer");
        views.setOnClickPendingIntent(
                R.id.widget_scan, action(context, MainActivity.ACTION_SCAN, 201));
        views.setOnClickPendingIntent(
                R.id.widget_send, action(context, MainActivity.ACTION_PICK_FILES, 202));
        views.setOnClickPendingIntent(
                R.id.widget_refresh, action(context, MainActivity.ACTION_REFRESH, 203));
        manager.updateAppWidget(id, views);
    }

    public static void updateAll(Context context) {
        AppWidgetManager manager = AppWidgetManager.getInstance(context);
        ComponentName component = new ComponentName(context, DexgetWidget.class);
        int[] ids = manager.getAppWidgetIds(component);
        for (int id : ids) update(context, manager, id);
    }
}
