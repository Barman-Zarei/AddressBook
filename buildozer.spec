[app]
title = AddressBook
package.name = addressbook
package.domain = org.barmanzarei
source.dir = addressbook_app
source.include_exts = py,png,jpg,kv,atlas,ttf
source.exclude_dirs = .github,.git,venv,bin,tests,__pycache__,.buildozer
version = 7.9.0
requirements = python3,kivy==2.3.1,requests,urllib3,idna,chardet,certifi
orientation = portrait
android.accept_sdk_license = True
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
