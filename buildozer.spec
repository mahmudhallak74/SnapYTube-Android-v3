[app]
title = SnapYTube Ultimate
package.name = snapytube
package.domain = com.mahmud

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,html,js,css,ttf

version = 4.1.0

# تم التعديل هنا: أضفت رقم تحديث محدد لـ yt-dlp لحل مشكلة تيك توك نهائياً
requirements = python3==3.11.9,hostpython3==3.11.9,kivy==2.3.0,flask,flask-cors,yt-dlp,setuptools,wheel,requests,certifi,idna,urllib3,pyjnius,android,werkzeug
 
orientation = portrait
fullscreen = 0

# صلاحيات الإنترنت والقراءة والكتابة
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

android.accept_sdk_license = True
android.api = 33
android.minapi = 21
android.ndk = 25b

# هذا السطر يحل مشكلة الاتصال (بدون الحاجة لـ apktool إطلاقاً)
android.manifest.uses_cleartext_traffic = True

# arm64-v8a: أغلب الأجهزة الحديثة (2018+) | armeabi-v7a: الأجهزة القديمة/الرخيصة (32-بت)
# بدون armeabi-v7a، أي جهاز 32-بت ما رح يقدر يثبت التطبيق إطلاقاً — لهيك لازم الاثنين
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
