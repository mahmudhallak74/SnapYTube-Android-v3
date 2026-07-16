# main.py — نقطة دخول تطبيق SnapYTube Ultimate (Kivy)
import os
import threading
import urllib.request
import json
import traceback

from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.core.window import Window
from kivy.core.text import LabelBase

SERVER_PORT = 5001
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"
HEALTH_URL = f"{SERVER_URL}/api/health"

IS_ANDROID = "ANDROID_ARGUMENT" in os.environ
BG_COLOR = (0.06, 0.05, 0.1, 1)
ACCENT_COLOR = (0.65, 0.4, 0.95, 1)

_ARABIC_FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arabic_font.ttf")
if os.path.exists(_ARABIC_FONT_PATH):
    LabelBase.register(name="Arabic", fn_regular=_ARABIC_FONT_PATH)
    ARABIC_FONT = "Arabic"
else:
    ARABIC_FONT = "DroidSansArabic"

def log_error_to_file(e):
    try:
        from android.storage import app_storage_path
        log_path = os.path.join(app_storage_path(), "crash_log.txt")
    except:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash_log.txt")
    
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("=== خطأ في تشغيل SnapYTube ===\n")
        f.write(str(e) + "\n\n")
        f.write(traceback.format_exc())
    return log_path

def get_storage_path():
    if IS_ANDROID:
        from android.storage import app_storage_path
        base = app_storage_path()
    else:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_data")
    os.makedirs(base, exist_ok=True)
    return base

def start_flask_server():
    try:
        import server
        from werkzeug.serving import make_server
        app = server.build_app(get_storage_path())
        httpd = make_server("127.0.0.1", SERVER_PORT, app, threaded=True)
        httpd.serve_forever()
    except Exception as e:
        log_error_to_file(e)

class Dot(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size = (14, 14)
        with self.canvas:
            Color(*ACCENT_COLOR)
            self.ellipse = Ellipse(pos=self.pos, size=self.size)
        self.bind(pos=self._update, size=self._update)
    def _update(self, *_):
        self.ellipse.pos = self.pos
        self.ellipse.size = self.size

class LoadingScreen(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Window.clearcolor = BG_COLOR
        wrapper = BoxLayout(orientation="vertical", spacing=18, size_hint=(0.86, None), height=260, pos_hint={"center_x": 0.5, "center_y": 0.5})
        
        self.title_label = Label(text="SnapYTube Ultimate", font_size="26sp", bold=True, color=(1, 1, 1, 1), size_hint_y=None, height=44)
        
        dots_row = BoxLayout(orientation="horizontal", spacing=14, size_hint_y=None, height=30, pos_hint={"center_x": 0.5})
        self.dots = [Dot() for _ in range(3)]
        for d in self.dots: dots_row.add_widget(d)

        self.status_label = Label(text="جاري تشغيل السيرفر...", font_size="15sp", color=(0.8, 0.8, 0.85, 1), size_hint_y=None, height=30, font_name=ARABIC_FONT)
        
        wrapper.add_widget(self.title_label)
        wrapper.add_widget(dots_row)
        wrapper.add_widget(self.status_label)
        self.add_widget(wrapper)
        self._animate_dots()

    def _animate_dots(self):
        for i, dot in enumerate(self.dots):
            anim = (Animation(opacity=0.25, duration=0.4) + Animation(opacity=1, duration=0.4))
            anim.repeat = True
            Clock.schedule_once(lambda dt, a=anim, d=dot: a.start(d), i * 0.15)

    def set_status(self, text):
        self.status_label.text = text

class SnapYTubeApp(App):
    def build(self):
        self.loading_screen = LoadingScreen()
        self.server_ready = False
        threading.Thread(target=start_flask_server, daemon=True).start()
        threading.Thread(target=self._poll_server_ready, daemon=True).start()
        return self.loading_screen

    def _poll_server_ready(self):
        import time
        attempts = 0
        while not self.server_ready:
            attempts += 1
            try:
                with urllib.request.urlopen(HEALTH_URL, timeout=1.5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("status") == "ok":
                        self.server_ready = True
                        Clock.schedule_once(lambda dt: self._on_server_ready(), 0)
                        return
            except Exception as e:
                if attempts > 3:
                    log_path = log_error_to_file(e)
                    Clock.schedule_once(lambda dt, p=log_path: self.loading_screen.set_status(f"خطأ: راجع ملف {p}"), 0)

            msg = "جاري تشغيل السيرفر..." if attempts < 6 else "بياخد وقت أطول شوي..."
            Clock.schedule_once(lambda dt, m=msg: self.loading_screen.set_status(m), 0)
            time.sleep(0.5)

            if attempts > 60:
                Clock.schedule_once(lambda dt: self.loading_screen.set_status("⚠️ في مشكلة بتشغيل السيرفر"), 0)
                return

    def _on_server_ready(self):
        self.loading_screen.set_status("جاهز! ✅")
        Clock.schedule_once(self._launch_webview, 0.4)

    def _launch_webview(self, dt):
        if IS_ANDROID:
            self._open_android_webview()
        else:
            import webbrowser
            webbrowser.open(SERVER_URL)
            self.loading_screen.set_status(f"شغّال محلياً على {SERVER_URL}")

    # ✅ الدالة موجودة الآن بشكل صحيح داخل الكلاس (لاحظ المسافات الـ 8 مسافات)
    def _open_android_webview(self):
        try:
            from jnius import autoclass
            WebView = autoclass("android.webkit.WebView")
            WebViewClient = autoclass("android.webkit.WebViewClient")
            WebChromeClient = autoclass("android.webkit.WebChromeClient")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            LayoutParams = autoclass("android.view.ViewGroup$LayoutParams")

            activity = PythonActivity.mActivity

            def create_and_load(*_):
                webview = WebView(activity)
                settings = webview.getSettings()
                settings.setJavaScriptEnabled(True)
                settings.setDomStorageEnabled(True)
                settings.setAllowFileAccess(True)
                settings.setMediaPlaybackRequiresUserGesture(False)
                
                if hasattr(settings, 'setMixedContentMode'):
                    settings.setMixedContentMode(0)

                webview.setWebViewClient(WebViewClient())
                webview.setWebChromeClient(WebChromeClient())

                activity.setContentView(webview, LayoutParams(
                    LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT
                ))
                webview.loadUrl(SERVER_URL)

            activity.runOnUiThread(create_and_load)
        except Exception as e:
            log_error_to_file(e)

# ✅ هذا السطر يجب أن يكون في النهاية فقط
if __name__ == "__main__":
    try:
        SnapYTubeApp().run()
    except Exception as e:
        log_error_to_file(e)
