package app.lawhat.muallima;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.webkit.WebViewAssetLoader;

import org.json.JSONObject;

import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/**
 * غلاف «لوحة المعلمة»: الواجهة نفسها (dist/index.html) مضمّنة في التطبيق وتُخدَم من أصل https ثابت
 * (appassets.androidplatform.net) عبر WebViewAssetLoader، فتعمل IndexedDB وlocalStorage كما في المتصفح وبلا إنترنت.
 * البيانات في مساحة التطبيق الخاصة؛ تبقى عند التحديث (التوقيع نفسه) وتُمحى عند إلغاء التثبيت.
 * الجسر LawhatAndroid: حفظ الملفات بنافذة «حفظ باسم» من النظام، النسخ إلى الحافظة، فتح الروابط في المتصفح، ورقم الإصدار.
 */
public class MainActivity extends Activity {
    private static final String HOST = "appassets.androidplatform.net";
    private static final String START = "https://" + HOST + "/assets/index.html";
    private static final int REQ_OPEN = 1;
    private static final int REQ_SAVE = 2;

    private WebView web;
    private ValueCallback<Uri[]> fileCallback;
    private String saveId, saveName, saveText;
    private long lastBack;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        if (BuildConfig.WEBDEBUG) WebView.setWebContentsDebuggingEnabled(true); // بناء الاختبار الآلي وحده
        web = new WebView(this);
        setContentView(web);

        final WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
                .setDomain(HOST)
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false); // منبّه نهاية الجلسة
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setSupportMultipleWindows(false);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                return loader.shouldInterceptRequest(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri u = request.getUrl();
                if (HOST.equals(u.getHost())) return false;
                openExternalUri(u); // أي رابط خارجي يُفتح في المتصفح لا داخل التطبيق
                return true;
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("*/*"); // ملفات .json لا يعرّفها كل مدير ملفات بنوعها
                try {
                    startActivityForResult(Intent.createChooser(i, getString(R.string.choose_file)), REQ_OPEN);
                } catch (Exception e) {
                    fileCallback = null;
                    return false;
                }
                return true;
            }
        });

        web.addJavascriptInterface(new Bridge(), "LawhatAndroid");
        // لا استعادة لحالة WebView: البيانات في IndexedDB، والصفحة تُحمَّل من جديد دائماً
        web.loadUrl(START);
    }

    private void openExternalUri(Uri u) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, u));
        } catch (Exception e) {
            Toast.makeText(this, u.toString(), Toast.LENGTH_LONG).show();
        }
    }

    private void js(String code) {
        web.post(() -> web.evaluateJavascript(code, null));
    }

    private void fileSaved(String id, boolean ok, String err) {
        js("window.LM_fileSaved && window.LM_fileSaved(" + JSONObject.quote(id) + "," + ok + "," + (err == null ? "null" : JSONObject.quote(err)) + ")");
    }

    final class Bridge {
        @JavascriptInterface
        public void saveFile(String id, String name, String mime, String text) {
            runOnUiThread(() -> {
                if (saveId != null) fileSaved(saveId, false, "بدأ حفظ آخر");
                saveId = id;
                saveName = name;
                saveText = text;
                Intent i = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType(mime == null || mime.isEmpty() ? "application/octet-stream" : mime);
                i.putExtra(Intent.EXTRA_TITLE, name);
                try {
                    startActivityForResult(i, REQ_SAVE);
                } catch (Exception e) {
                    String sid = saveId;
                    saveId = null;
                    saveText = null;
                    fileSaved(sid, false, "لا تطبيق ملفات لحفظه");
                }
            });
        }

        @JavascriptInterface
        public boolean copy(String text) {
            try {
                ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
                cm.setPrimaryClip(ClipData.newPlainText("lawhat", text));
                return true;
            } catch (Exception e) {
                return false;
            }
        }

        @JavascriptInterface
        public void openExternal(String url) {
            runOnUiThread(() -> openExternalUri(Uri.parse(url)));
        }

        @JavascriptInterface
        public boolean isPreview() {
            return BuildConfig.PREVIEW;
        }

        @JavascriptInterface
        public String appVersion() {
            return BuildConfig.VERSION_NAME + " (" + BuildConfig.VERSION_CODE + ")";
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_OPEN) {
            if (fileCallback != null) fileCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
            fileCallback = null;
        } else if (requestCode == REQ_SAVE) {
            String id = saveId, text = saveText;
            saveId = null;
            saveText = null;
            if (id == null) return;
            if (resultCode != RESULT_OK || data == null || data.getData() == null) {
                fileSaved(id, false, null); // أُلغي
                return;
            }
            try (OutputStream out = getContentResolver().openOutputStream(data.getData(), "wt")) {
                if (out == null) throw new Exception("no stream");
                out.write(text.getBytes(StandardCharsets.UTF_8));
                out.flush();
                fileSaved(id, true, null);
            } catch (Exception e) {
                fileSaved(id, false, getString(R.string.save_failed) + ": " + e.getMessage());
            }
        }
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        // الواجهة تغلق النافذة المفتوحة أو تعود للشاشة الرئيسية؛ وإلا: رجوع مرتين خلال ثانيتين للخروج
        web.evaluateJavascript("(window.LM_back && window.LM_back()) ? 'handled' : 'no'", value -> {
            if (value != null && value.contains("handled")) return;
            long now = SystemClock.elapsedRealtime();
            if (now - lastBack < 2000) finish();
            else {
                lastBack = now;
                Toast.makeText(this, R.string.press_back_again, Toast.LENGTH_SHORT).show();
            }
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
    }

    @Override
    protected void onDestroy() {
        if (web != null) web.destroy();
        super.onDestroy();
    }
}
