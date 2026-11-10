package com.dexget.companion;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.google.zxing.client.android.Intents;
import com.journeyapps.barcodescanner.BarcodeCallback;
import com.journeyapps.barcodescanner.BarcodeResult;
import com.journeyapps.barcodescanner.DecoratedBarcodeView;

public final class ScannerActivity extends Activity {
    private DecoratedBarcodeView scanner;
    private boolean delivered;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.BLACK);

        TextView title = new TextView(this);
        title.setText("Scan Dexget pairing QR");
        title.setTextColor(Color.WHITE);
        title.setTextSize(18);
        title.setGravity(Gravity.CENTER);
        title.setPadding(16, 24, 16, 20);
        root.addView(title, new LinearLayout.LayoutParams(-1, -2));

        scanner = new DecoratedBarcodeView(this);
        scanner.setStatusText("Place the laptop QR code inside the frame");
        root.addView(scanner, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);

        BarcodeCallback callback = new BarcodeCallback() {
            @Override public void barcodeResult(BarcodeResult result) {
                if (delivered || result == null || result.getText() == null) return;
                delivered = true;
                Intent response = new Intent();
                response.putExtra(Intents.Scan.RESULT, result.getText());
                response.putExtra(Intents.Scan.RESULT_FORMAT, result.getBarcodeFormat().toString());
                setResult(RESULT_OK, response);
                finish();
            }
        };
        scanner.decodeSingle(callback);
    }

    @Override protected void onResume() {
        super.onResume();
        if (scanner != null) scanner.resume();
    }

    @Override protected void onPause() {
        if (scanner != null) scanner.pause();
        super.onPause();
    }

    @Override public void onBackPressed() {
        setResult(RESULT_CANCELED);
        super.onBackPressed();
    }
}
