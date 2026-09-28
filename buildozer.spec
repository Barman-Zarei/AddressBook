[app]
title = DigiShop
package.name = addressbook
package.domain = org.barmanzarei
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf
source.exclude_dirs = backend,.github,.git,venv,bin,tests,__pycache__
version = 5.9.143
requirements = python3,kivy==2.3.1,requests,arabic_reshaper,python-bidi==0.4.2
orientation = portrait
android.accept_sdk_license = True
android.permissions = INTERNET,READ_MEDIA_IMAGES,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
