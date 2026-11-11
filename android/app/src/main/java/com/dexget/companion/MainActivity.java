package com.dexget.companion;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.ContentValues;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.NetworkRequest;
import android.net.Uri;
import android.net.wifi.WifiNetworkSpecifier;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.provider.Settings;
import android.provider.MediaStore;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import com.google.zxing.integration.android.IntentIntegrator;
import com.google.zxing.integration.android.IntentResult;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    public static final String ACTION_SCAN = "com.dexget.companion.SCAN";
    public static final String ACTION_PICK_FILES = "com.dexget.companion.PICK_FILES";
    public static final String ACTION_REFRESH = "com.dexget.companion.REFRESH";
    private static final int PICK_FILES = 41;
    private static final int CAMERA_PERMISSION = 42;
    private static final int WIFI_PERMISSION = 43;
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private SharedPreferences prefs;
    private TextView status;
    private TextView laptop;
    private LinearLayout downloads;
    private ProgressBar progress;
    private String endpoint = "";
    private Network directNetwork;
    private String pendingSsid;
    private String pendingPassword;
    private String pendingTarget;
    private boolean wifiConnectionRequested;
    private final Set<String> downloadedFiles = ConcurrentHashMap.newKeySet();

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences("pairing", MODE_PRIVATE);
        endpoint = prefs.getString("endpoint", "");
        setContentView(buildUi());
        renderPairing();
        handleLaunchAction(getIntent());
        if (!endpoint.isEmpty() && !ACTION_PICK_FILES.equals(getIntent().getAction())) refreshFiles();
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleLaunchAction(intent);
    }

    private void handleLaunchAction(Intent intent) {
        if (intent == null) return;
        String action = intent.getAction();
        if (ACTION_SCAN.equals(action)) scanPairing();
        else if (ACTION_PICK_FILES.equals(action)) chooseFiles();
        else if (ACTION_REFRESH.equals(action)) refreshFiles();
    }

    private View buildUi() {
        int pad = dp(22);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);
        root.setBackgroundColor(Color.rgb(5, 6, 8));

        TextView title = text("Dexget", 30, Color.WHITE);
        title.setTypeface(null, 1);
        root.addView(title);
        root.addView(text("Fast private transfer with your laptop", 15, Color.rgb(155, 157, 166)));

        laptop = text("No laptop paired", 18, Color.WHITE);
        laptop.setPadding(0, dp(28), 0, dp(8));
        root.addView(laptop);
        status = text("Scan the QR shown in the Dynamic Island.", 14, Color.rgb(155, 157, 166));
        root.addView(status);

        LinearLayout actions = new LinearLayout(this);
        actions.setPadding(0, dp(22), 0, dp(12));
        actions.setGravity(Gravity.CENTER);
        Button pair = button("Scan & pair");
        pair.setOnClickListener(v -> scanPairing());
        Button send = button("Send files");
        send.setOnClickListener(v -> chooseFiles());
        Button refresh = button("Refresh");
        refresh.setOnClickListener(v -> refreshFiles());
        actions.addView(pair, new LinearLayout.LayoutParams(0, dp(52), 1));
        actions.addView(send, new LinearLayout.LayoutParams(0, dp(52), 1));
        actions.addView(refresh, new LinearLayout.LayoutParams(0, dp(52), 1));
        root.addView(actions);

        progress = new ProgressBar(this);
        progress.setVisibility(View.GONE);
        root.addView(progress);
        TextView available = text("From laptop", 18, Color.WHITE);
        available.setTypeface(null, 1);
        available.setPadding(0, dp(20), 0, dp(8));
        root.addView(available);
        downloads = new LinearLayout(this);
        downloads.setOrientation(LinearLayout.VERTICAL);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(downloads);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        return root;
    }

    private TextView text(String value, int sp, int color) {
        TextView view = new TextView(this);
        view.setText(value); view.setTextSize(sp); view.setTextColor(color);
        return view;
    }

    private Button button(String value) {
        Button button = new Button(this);
        button.setText(value); button.setTextColor(Color.WHITE);
        button.setAllCaps(false); button.setBackgroundColor(Color.rgb(31, 32, 37));
        return button;
    }

    private void scanPairing() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M
                && checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.CAMERA}, CAMERA_PERMISSION);
            return;
        }
        launchScanner();
    }

    private void launchScanner() {
        try {
            IntentIntegrator integrator = new IntentIntegrator(this);
            integrator.setCaptureActivity(ScannerActivity.class);
            integrator.setPrompt("Scan Dexget pairing QR");
            integrator.setBeepEnabled(false);
            integrator.setOrientationLocked(false);
            integrator.initiateScan();
        } catch (Exception error) {
            status.setText("Camera scanner could not start: " + error.getMessage());
            Toast.makeText(this, "Unable to open the QR scanner", Toast.LENGTH_LONG).show();
        }
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
        if (requestCode == CAMERA_PERMISSION) {
            if (granted) launchScanner();
            else {
                status.setText("Camera permission is required to scan the pairing QR.");
                Toast.makeText(this, "Allow Camera permission to pair", Toast.LENGTH_LONG).show();
            }
        } else if (requestCode == WIFI_PERMISSION) {
            if (granted && pendingSsid != null)
                prepareDirectConnection(pendingSsid, pendingPassword, pendingTarget);
            else {
                status.setText("Nearby devices permission is required to join the laptop Wi-Fi.");
                Toast.makeText(this, "Allow Nearby devices to connect", Toast.LENGTH_LONG).show();
            }
        }
    }

    @Override protected void onResume() {
        super.onResume();
        if (pendingSsid != null && !wifiConnectionRequested) {
            WifiManager wifi = (WifiManager)getApplicationContext().getSystemService(Context.WIFI_SERVICE);
            if (wifi != null && wifi.isWifiEnabled())
                prepareDirectConnection(pendingSsid, pendingPassword, pendingTarget);
        }
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        IntentResult scan = IntentIntegrator.parseActivityResult(requestCode, resultCode, data);
        if (scan != null) {
            if (scan.getContents() != null) acceptPairing(scan.getContents());
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == PICK_FILES && resultCode == RESULT_OK && data != null) {
            List<Uri> uris = new ArrayList<>();
            if (data.getClipData() != null) {
                for (int i = 0; i < data.getClipData().getItemCount(); i++)
                    uris.add(data.getClipData().getItemAt(i).getUri());
            } else if (data.getData() != null) uris.add(data.getData());
            upload(uris);
        }
    }

    private void acceptPairing(String payload) {
        try {
            Uri uri = Uri.parse(payload);
            String candidate = payload;
            if ("dexget".equalsIgnoreCase(uri.getScheme())) {
                String encodedEndpoint = uri.getQueryParameter("endpoint");
                if (encodedEndpoint == null || encodedEndpoint.trim().isEmpty())
                    throw new IllegalArgumentException("Pairing endpoint is missing");
                candidate = URLDecoder.decode(encodedEndpoint, "UTF-8");
                String ssid = uri.getQueryParameter("ssid");
                String password = uri.getQueryParameter("password");
                if (ssid != null && password != null) {
                    tryCurrentNetworkFirst(ssid, password, candidate);
                    return;
                }
            }
            if (!candidate.startsWith("http://") && !candidate.startsWith("https://"))
                throw new IllegalArgumentException("Not a Dexget pairing code");
            endpoint = candidate.endsWith("/") ? candidate : candidate + "/";
            prefs.edit().putString("endpoint", endpoint).apply();
            renderPairing();
            DexgetWidget.updateAll(this);
            refreshFiles();
        } catch (Exception error) {
            status.setText("Invalid pairing code: " + error.getMessage());
        }
    }

    private void tryCurrentNetworkFirst(String ssid, String password, String target) {
        pendingSsid = ssid;
        pendingPassword = password;
        pendingTarget = target;
        directNetwork = null;
        endpoint = target.endsWith("/") ? target : target + "/";
        status.setText("Finding laptop on the current network…");
        io.execute(() -> {
            try {
                URL url = new URL(endpoint + "api/files");
                HttpURLConnection connection = (HttpURLConnection)url.openConnection();
                connection.setConnectTimeout(2500);
                connection.setReadTimeout(2500);
                if (connection.getResponseCode() >= 300)
                    throw new Exception("Laptop returned " + connection.getResponseCode());
                connection.disconnect();
                pendingSsid = pendingPassword = pendingTarget = null;
                prefs.edit().putString("endpoint", endpoint).apply();
                runOnUiThread(() -> {
                    renderPairing();
                    DexgetWidget.updateAll(this);
                    refreshFiles();
                });
            } catch (Exception ignored) {
                runOnUiThread(() -> prepareDirectConnection(ssid, password, target));
            }
        });
    }

    private void prepareDirectConnection(String ssid, String password, String target) {
        pendingSsid = ssid;
        pendingPassword = password;
        pendingTarget = target;
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.NEARBY_WIFI_DEVICES) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.NEARBY_WIFI_DEVICES}, WIFI_PERMISSION);
            return;
        }
        WifiManager wifi = (WifiManager)getApplicationContext().getSystemService(Context.WIFI_SERVICE);
        if (wifi != null && !wifi.isWifiEnabled()) {
            status.setText("Turn on Wi-Fi, then return to Dexget to continue pairing.");
            try {
                startActivity(new Intent(Settings.Panel.ACTION_WIFI));
            } catch (Exception ignored) {
                startActivity(new Intent(Settings.ACTION_WIFI_SETTINGS));
            }
            return;
        }
        connectDirect(ssid, password, target);
    }

    private void connectDirect(String ssid, String password, String target) {
        if (wifiConnectionRequested) return;
        wifiConnectionRequested = true;
        status.setText("Connecting to " + ssid + "…");
        try {
            WifiNetworkSpecifier specifier = new WifiNetworkSpecifier.Builder()
                    .setSsid(ssid).setWpa2Passphrase(password).build();
            NetworkRequest request = new NetworkRequest.Builder()
                    .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
                    .removeCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                    .setNetworkSpecifier(specifier).build();
            ConnectivityManager manager = (ConnectivityManager)getSystemService(Context.CONNECTIVITY_SERVICE);
            manager.requestNetwork(request, new ConnectivityManager.NetworkCallback() {
            @Override public void onAvailable(Network network) {
                directNetwork = network;
                wifiConnectionRequested = false;
                pendingSsid = pendingPassword = pendingTarget = null;
                endpoint = target.endsWith("/") ? target : target + "/";
                prefs.edit().putString("endpoint", endpoint).apply();
                runOnUiThread(() -> {
                    renderPairing();
                    DexgetWidget.updateAll(this);
                    refreshFiles();
                });
            }
            @Override public void onUnavailable() {
                wifiConnectionRequested = false;
                runOnUiThread(() -> status.setText("Connection was not approved or the network was unavailable."));
            }
            });
        } catch (SecurityException error) {
            wifiConnectionRequested = false;
            status.setText("Android blocked the Wi-Fi connection permission. Reinstall the latest Dexget app.");
        } catch (Exception error) {
            wifiConnectionRequested = false;
            status.setText("Could not connect to " + ssid + ": " + error.getMessage());
        }
    }

    private HttpURLConnection open(String path) throws Exception {
        URL url = new URL(endpoint + path);
        HttpURLConnection connection = (HttpURLConnection)(
                directNetwork != null ? directNetwork.openConnection(url) : url.openConnection());
        connection.setConnectTimeout(7000);
        connection.setReadTimeout(15000);
        return connection;
    }

    private void refreshFiles() {
        if (endpoint.isEmpty()) { status.setText("Pair a laptop first."); return; }
        busy(true, "Checking laptop…");
        io.execute(() -> {
            try {
                HttpURLConnection connection = open("api/files");
                String json = read(connection.getInputStream());
                JSONArray files = new JSONObject(json).getJSONArray("files");
                runOnUiThread(() -> showFiles(files));
            } catch (Exception error) {
                runOnUiThread(() -> status.setText(
                        "Laptop unavailable: " + error.getClass().getSimpleName()
                                + ". Keep Share to phone open on the laptop."));
            } finally { runOnUiThread(() -> busy(false, null)); }
        });
    }

    private void showFiles(JSONArray files) {
        downloads.removeAllViews();
        List<JSONObject> pending = new ArrayList<>();
        for (int i = 0; i < files.length(); i++) {
            JSONObject file = files.optJSONObject(i);
            if (file == null) continue;
            Button item = button(file.optString("name") + "   ↓");
            int index = file.optInt("index");
            String name = file.optString("name", "download");
            item.setOnClickListener(v -> downloadFile(index, name, false));
            downloads.addView(item, new LinearLayout.LayoutParams(-1, dp(54)));
            if (!downloadedFiles.contains(downloadKey(index, name))) pending.add(file);
        }
        status.setText("Connected · " + files.length() + " file(s) available");
        if (!pending.isEmpty()) {
            status.setText("Connected · downloading " + pending.size() + " file(s)…");
            for (JSONObject file : pending)
                downloadFile(file.optInt("index"), file.optString("name", "download"), true);
        }
    }

    private String downloadKey(int index, String name) {
        return endpoint + "|" + index + "|" + name;
    }

    private void downloadFile(int index, String requestedName, boolean automatic) {
        final String name = requestedName.replaceAll("[\\\\/:*?\"<>|]", "_");
        final String key = downloadKey(index, requestedName);
        if (automatic && downloadedFiles.contains(key)) return;
        io.execute(() -> {
            Uri destination = null;
            try {
                ContentValues values = new ContentValues();
                values.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
                values.put(MediaStore.MediaColumns.MIME_TYPE, "application/octet-stream");
                values.put(MediaStore.MediaColumns.RELATIVE_PATH, "Download/Dexget");
                values.put(MediaStore.MediaColumns.IS_PENDING, 1);
                destination = getContentResolver().insert(
                        MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
                if (destination == null) throw new Exception("Downloads folder is unavailable");

                HttpURLConnection connection = open("download/" + index);
                if (connection.getResponseCode() >= 300)
                    throw new Exception("Laptop returned " + connection.getResponseCode());
                try (InputStream input = connection.getInputStream();
                     OutputStream output = getContentResolver().openOutputStream(destination)) {
                    if (output == null) throw new Exception("Could not create the downloaded file");
                    byte[] buffer = new byte[256 * 1024];
                    int count;
                    while ((count = input.read(buffer)) >= 0) output.write(buffer, 0, count);
                }
                values.clear();
                values.put(MediaStore.MediaColumns.IS_PENDING, 0);
                getContentResolver().update(destination, values, null, null);
                downloadedFiles.add(key);
                runOnUiThread(() -> status.setText(
                        "Downloaded " + name + " to Downloads/Dexget"));
            } catch (Exception error) {
                if (destination != null) getContentResolver().delete(destination, null, null);
                runOnUiThread(() -> status.setText(
                        "Download failed for " + name + ": " + error.getMessage()));
            }
        });
    }

    private void chooseFiles() {
        if (endpoint.isEmpty()) { status.setText("Pair a laptop first."); return; }
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.setType("*/*"); intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        startActivityForResult(intent, PICK_FILES);
    }

    private void upload(List<Uri> uris) {
        if (uris.isEmpty()) return;
        busy(true, "Sending " + uris.size() + " file(s)…");
        io.execute(() -> {
            String boundary = "Dexget" + System.currentTimeMillis();
            try {
                HttpURLConnection connection = open("");
                connection.setDoOutput(true); connection.setRequestMethod("POST");
                connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);
                OutputStream out = connection.getOutputStream();
                for (Uri uri : uris) {
                    String name = displayName(uri);
                    out.write(("--" + boundary + "\r\nContent-Disposition: form-data; name=\"files\"; filename=\"" + name.replace("\"", "") + "\"\r\nContent-Type: application/octet-stream\r\n\r\n").getBytes(StandardCharsets.UTF_8));
                    try (InputStream input = getContentResolver().openInputStream(uri)) {
                        byte[] buffer = new byte[256 * 1024]; int read;
                        while (input != null && (read = input.read(buffer)) >= 0) out.write(buffer, 0, read);
                    }
                    out.write("\r\n".getBytes(StandardCharsets.UTF_8));
                }
                out.write(("--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8)); out.close();
                if (connection.getResponseCode() >= 300) throw new Exception("Upload failed");
                runOnUiThread(() -> status.setText("Files sent to laptop."));
            } catch (Exception error) {
                runOnUiThread(() -> status.setText("Send failed: " + error.getMessage()));
            } finally { runOnUiThread(() -> busy(false, null)); }
        });
    }

    private String displayName(Uri uri) {
        try (android.database.Cursor cursor = getContentResolver().query(uri, null, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int column = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (column >= 0) return cursor.getString(column);
            }
        }
        return "file";
    }

    private static String read(InputStream input) throws Exception {
        try (BufferedInputStream in = new BufferedInputStream(input); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] data = new byte[8192]; int count;
            while ((count = in.read(data)) >= 0) out.write(data, 0, count);
            return out.toString("UTF-8");
        }
    }

    private void renderPairing() {
        laptop.setText(endpoint.isEmpty() ? "No laptop paired" : "Ashwin's laptop");
        status.setText(endpoint.isEmpty() ? "Scan the QR shown in the Dynamic Island." : "Paired · ready to transfer");
    }

    private void busy(boolean value, String message) {
        progress.setVisibility(value ? View.VISIBLE : View.GONE);
        if (message != null) status.setText(message);
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    @Override protected void onDestroy() { super.onDestroy(); io.shutdownNow(); }
}
