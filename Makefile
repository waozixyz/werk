.DEFAULT_GOAL := all
ZIRAN ?= ./scripts/ziran.sh
# Local overrides refer to the real root repositories. Published builds
# require the exact versions recorded in the committed lock.
LOCK_FLAGS := $(if $(wildcard ziran.local.toml),,--locked)
ZIRAN_ROOT = $(shell $(ZIRAN) pkg path ziran $(LOCK_FLAGS))
KRYON_DIR = $(shell $(ZIRAN) pkg path kryon $(LOCK_FLAGS))
RAYLIB_DIR = $(shell $(ZIRAN) pkg path raylib $(LOCK_FLAGS))/src
MINGCUTE_DIR = $(shell $(ZIRAN) pkg path mingcute $(LOCK_FLAGS))
# Account sync: ML-DSA-44 account keys from liboqs, and Ed25519, X25519,
# BLAKE2b and XChaCha20-Poly1305 from Monocypher.
LIBOQS_DIR = $(shell $(ZIRAN) pkg path liboqs $(LOCK_FLAGS))
MONOCYPHER_DIR = $(shell $(ZIRAN) pkg path monocypher $(LOCK_FLAGS))
QRCODE_DIR = $(shell $(ZIRAN) pkg path qrcode $(LOCK_FLAGS))
WORKBOOK_DIR = $(shell $(ZIRAN) pkg path workbook $(LOCK_FLAGS))
SELF_DIR = $(shell $(ZIRAN) pkg path self $(LOCK_FLAGS))
APPS_DIR = $(shell $(ZIRAN) pkg path apps $(LOCK_FLAGS))
LIBOQS_FLAGS := -DCMAKE_BUILD_TYPE=MinSizeRel -DBUILD_SHARED_LIBS=OFF -DOQS_BUILD_ONLY_LIB=ON \
	-DOQS_USE_OPENSSL=OFF -DOQS_DIST_BUILD=OFF -DOQS_OPT_TARGET=generic -DOQS_MINIMAL_BUILD=SIG_ml_dsa_44
MONOCYPHER_SOURCES = $(MONOCYPHER_DIR)/src/monocypher.c $(MONOCYPHER_DIR)/src/optional/monocypher-ed25519.c
CC ?= cc
BIN_DIR ?= $(HOME)/bin
DATA_DIR ?= $(if $(XDG_DATA_HOME),$(XDG_DATA_HOME),$(HOME)/.local/share)
# The tool bundles and Werkzeug's other files.
LIB_DIR ?= $(HOME)/.local/lib/werk
WEB_CC ?= $(if $(wildcard $(HOME)/emsdk/upstream/emscripten/emcc),$(HOME)/emsdk/upstream/emscripten/emcc,emcc)
SOURCES := $(wildcard src/*.zi shared/*.zi apps/*/*.zi)
LIBRARY_SOURCES = $(wildcard $(KRYON_DIR)/src/ui/*.zi $(KRYON_DIR)/src/ui/*/module.zi $(KRYON_DIR)/src/kss/*.zi $(KRYON_DIR)/src/backend/*.zi $(KRYON_DIR)/src/backend/*/module.zi $(ZIRAN_ROOT)/std/*.zi)
ZIRAN_RUNTIME_SOURCES = $(wildcard $(ZIRAN_ROOT)/cmd/zir/*.[ch] $(ZIRAN_ROOT)/include/*.h)
SELF_SOURCES = $(wildcard $(SELF_DIR)/src/*.zi $(SELF_DIR)/assets/self/*)
CFLAGS := -std=c99 -O2 -Wno-unused-variable -I$(ZIRAN_ROOT)/include
PROJECT := --project $(LOCK_FLAGS)
ANDROID_ABIS ?= armeabi-v7a,arm64-v8a

.PHONY: all apps cli gui native run test source-check core-test ziran-core-test cli-test pass-state-test app-logic-test lesspass-compat-test self-account-test gui-smoke gui-test web web-canvas site web-smoke android-debug android-emulator android-release android-smoke android-input-test e2e check-package-urls install install-cli install-gui uninstall-cli uninstall-gui package-deb package-appimage plan9-c
all: cli gui
native: all

build/generated/cli/.complete: $(SOURCES) ziran.toml ziran.lock
	rm -rf $(@D)
	mkdir -p $(@D)
	$(ZIRAN) build $(PROJECT) --target=c --entry cli:main -o $(@D) apps/pass/cli.zi
	touch $@
build/pass: build/generated/cli/.complete
	$(CC) $(CFLAGS) -Ibuild/generated/cli build/generated/cli/*.c -o $@
cli: build/pass
	cp build/pass pass

# Each app is its own bundle; Werkzeug runs them in one window.
APPS := pass auth calculator clock
APP_BUNDLES := $(APPS:%=build/apps/%.zib) build/apps/self.zib build/apps/apps.zib build/apps/workbook.zib
SHARED_SOURCES := $(wildcard shared/*.zi)
APP_MODULE_PATHS = --module-path shared --module-path kryon=$(KRYON_DIR)/src/backend --module-path kryon=$(KRYON_DIR)/src/ui --module-path $(KRYON_DIR)/src/ui --module-path $(MINGCUTE_DIR)/src --module-path $(ZIRAN_ROOT)/std
apps: $(APP_BUNDLES)
build/apps/apps.zib: ziran.lock apps-controller.sha256
	mkdir -p $(@D)
	$(ZIRAN) version > /dev/null
	env -u DISPLAY -u WAYLAND_DISPLAY \
		PATH="$(if $(wildcard $(ZIRAN_ROOT)/build/bin/ziran),$(ZIRAN_ROOT)/build/bin,$(CURDIR)/build/toolchain/bin):$$PATH" \
		python3 '$(APPS_DIR)/scripts/build-ui.py' --output '$(abspath $(@D))'
	test "$$(cat $(@D)/apps.sha256)" = "$$(cat apps-controller.sha256)"
.SECONDEXPANSION:
build/apps/%.zib: $$(wildcard apps/$$*/*.zi apps/$$*/assets/*) $(SHARED_SOURCES) $(LIBRARY_SOURCES) $(ZIRAN_RUNTIME_SOURCES) ziran.lock Makefile scripts/ziran.sh
	mkdir -p $(@D)
	$(ZIRAN) bundle --root . --module-path apps/$* $(APP_MODULE_PATHS) --define KRYON_HOSTED_UI --define WERK_APP \
		$(if $(wildcard apps/$*/assets),--asset-dir assets=apps/$*/assets) --entry $*:Main -o $@ apps/$*/$*.zi

build/apps/workbook.zib: $(wildcard $(WORKBOOK_DIR)/src/*.zi) $(WORKBOOK_DIR)/Makefile ziran.lock
	$(MAKE) -C $(WORKBOOK_DIR) ZIRAN=$(ZIRAN_ROOT)/build/bin/ziran bundle
	install -m 0600 $(WORKBOOK_DIR)/build/workbook.zib $@

build/apps/self.zib: $(SELF_SOURCES) $(LIBRARY_SOURCES) $(ZIRAN_RUNTIME_SOURCES) ziran.lock Makefile
	mkdir -p $(@D)
	$(ZIRAN) bundle --root $(SELF_DIR) --module-path $(SELF_DIR)/src $(APP_MODULE_PATHS) --define KRYON_HOSTED_UI \
		--module-path qrcode=$(QRCODE_DIR)/src --asset-dir assets=$(SELF_DIR)/assets --entry self:Main -o $@ $(SELF_DIR)/src/self.zi

# The portable bundle runtime the host links, built from the locked Ziran.
build/ziran/libziran.a: ziran.lock $(ZIRAN_RUNTIME_SOURCES)
	env -u DISPLAY -u WAYLAND_DISPLAY $(MAKE) -C $(ZIRAN_ROOT) BUILD_DIR=$(abspath build/ziran) $(abspath $@)

build/generated/desktop/.complete: $(wildcard src/*.zi) $(wildcard $(WORKBOOK_DIR)/src/*.zi) $(SHARED_SOURCES) $(LIBRARY_SOURCES) $(SELF_SOURCES) ziran.toml ziran.lock
	rm -rf $(@D)
	mkdir -p $(@D)
	$(ZIRAN) build $(PROJECT) --define PLATFORM_DESKTOP --target=c --entry desktop:main -o $(@D) src/desktop.zi
	touch $@
build/liboqs/lib/liboqs.a: ziran.lock
	cmake -S $(LIBOQS_DIR) -B build/liboqs $(LIBOQS_FLAGS) > /dev/null
	cmake --build build/liboqs --target oqs > /dev/null
build/werk: build/generated/desktop/.complete build/ziran/libziran.a build/liboqs/lib/liboqs.a Makefile
	$(CC) $(CFLAGS) -Ibuild/generated/desktop -I$(MONOCYPHER_DIR)/src -I$(MONOCYPHER_DIR)/src/optional \
		build/generated/desktop/*.c $(MONOCYPHER_SOURCES) build/ziran/libziran.a build/liboqs/lib/liboqs.a \
		$(shell pkg-config --libs sdl2 cairo freetype2 fontconfig pangocairo gtk+-3.0) -lX11 -l:libcurl.so.4 -lm -lpthread -o $@
build/pfp.png: $(KRYON_DIR)/icons/pfp.png
	cp $< $@
gui: build/werk build/pfp.png apps
run: gui
	./build/werk

source-check:
	python3 scripts/source_check.py
	$(ZIRAN) fmt --check $(SOURCES) tests/*.zi
core-test ziran-core-test:
	sh scripts/ziran_core_test.sh "$(ZIRAN)"
pass-state-test:
	sh scripts/pass_state_test.sh "$(ZIRAN)"
app-logic-test:
	sh scripts/app_logic_test.sh "$(ZIRAN)"
cli-test: cli
	sh scripts/cli_test.sh ./pass
lesspass-compat-test: cli
	python3 scripts/lesspass_compat_test.py --cli ./pass
self-account-test: build/liboqs/lib/liboqs.a
	ZIRAN_BIN=$(ZIRAN) python3 scripts/self_account_test.py
test: source-check core-test pass-state-test app-logic-test cli-test lesspass-compat-test self-account-test
gui-smoke: gui
	sh scripts/gui_smoke.sh
gui-test: gui
	sh scripts/werk_gui_test.sh
	env -u DISPLAY -u WAYLAND_DISPLAY -u XAUTHORITY -u DBUS_SESSION_BUS_ADDRESS YUE_DESKTOP_RECOVERY=0 xvfb-run -a env WERK_TEST_PRIVATE_DISPLAY=1 python3 scripts/workbook_gui_test.py
	sh scripts/migration_test.sh
	python3 -I scripts/auth_command_test.py

# The bundle runtime for the browser, built from the locked Ziran.
WEB_AR ?= $(dir $(WEB_CC))emar
build/web-runtime/libziran.a: ziran.lock
	env -u DISPLAY -u WAYLAND_DISPLAY $(MAKE) -C $(ZIRAN_ROOT) BOOTSTRAP=1 BUILD_DIR=$(abspath build/web-runtime) \
		CC=$(WEB_CC) AR=$(WEB_AR) OBJCOPY=true CFLAGS=-O2 $(abspath $@)
build/generated/browser/.complete: $(wildcard src/*.zi) $(SHARED_SOURCES) $(LIBRARY_SOURCES) ziran.toml ziran.lock
	rm -rf $(@D)
	mkdir -p $(@D)
	$(ZIRAN) build $(PROJECT) --define PLATFORM_WEB --target=c -o $(@D) src/browser.zi
	touch $@
build/web-app/index.js: build/generated/browser/.complete build/web-runtime/libziran.a $(APP_BUNDLES) build/pfp.png assets/app/icon.png assets/fonts/NotoSans-Regular.ttf
	mkdir -p $(@D)
	$(WEB_CC) -O2 -Wno-parentheses-equality -I$(ZIRAN_ROOT)/include -iquote build/generated/browser build/generated/browser/*.c \
		build/web-runtime/libziran.a \
		--js-library $(ZIRAN_ROOT)/web/ziran_web.js -sEXPORTED_RUNTIME_METHODS=FS,IDBFS -lidbfs.js \
		-sASYNCIFY -sALLOW_MEMORY_GROWTH=1 -sSTACK_SIZE=16777216 -sASYNCIFY_STACK_SIZE=1048576 -sENVIRONMENT=web \
		--embed-file assets/fonts/NotoSans-Regular.ttf@/kryon-font.ttf \
		--embed-file build/apps@/apps --embed-file build/pfp.png@/pfp.png --embed-file assets/app/icon.png@/icon.png -o $@
build/web-app/index.html: build/web-app/index.js web/site/app/index.html
	cp web/site/app/index.html $@
build/generated/worker/.complete: src/service_worker.zi ziran.toml ziran.lock
	rm -rf $(@D)
	mkdir -p $(@D)
	$(ZIRAN) build $(PROJECT) --target=c -o $(@D) src/service_worker.zi
	touch $@
build/web-app/sw.js: build/generated/worker/.complete
	$(WEB_CC) -O2 -I$(ZIRAN_ROOT)/include -iquote build/generated/worker build/generated/worker/*.c \
		--js-library $(ZIRAN_ROOT)/web/ziran_web.js -sENVIRONMENT=worker -sNO_EXIT_RUNTIME=1 \
		-sSINGLE_FILE=1 -sWASM_ASYNC_COMPILATION=0 -o $@
web-canvas: build/web-app/index.html build/web-app/sw.js
web site: web-canvas
	./web/build.sh
web-smoke: site
	bash scripts/web_smoke.sh

# CMake emits JNI and foreign ABI types separately for each Android ABI.
android-debug: apps
	cd droid && env WERK_ZIRAN_COMMAND="$(ZIRAN)" KRYON_DIR="$(KRYON_DIR)" ZIRAN_ROOT="$(ZIRAN_ROOT)" RAYLIB_DIR="$(RAYLIB_DIR)" LIBOQS_DIR="$(LIBOQS_DIR)" MONOCYPHER_DIR="$(MONOCYPHER_DIR)" ./gradlew assembleDebug -Pabi=$(ANDROID_ABIS) -PsplitApks=true $(GRADLE_ARGS)
	mkdir -p build
	cp droid/app/build/outputs/apk/debug/app-universal-debug.apk build/werk-android-debug.apk
	python3 scripts/android_apk_check.py build/werk-android-debug.apk
	cp droid/app/build/outputs/apk/debug/app-arm64-v8a-debug.apk build/werk-android-arm64-v8a-debug.apk
	cp droid/app/build/outputs/apk/debug/app-armeabi-v7a-debug.apk build/werk-android-armeabi-v7a-debug.apk
android-emulator: apps
	cd droid && env WERK_ZIRAN_COMMAND="$(ZIRAN)" KRYON_DIR="$(KRYON_DIR)" ZIRAN_ROOT="$(ZIRAN_ROOT)" RAYLIB_DIR="$(RAYLIB_DIR)" LIBOQS_DIR="$(LIBOQS_DIR)" MONOCYPHER_DIR="$(MONOCYPHER_DIR)" ./gradlew assembleDebug -Pabi=x86_64 $(GRADLE_ARGS)
	mkdir -p build
	cp droid/app/build/outputs/apk/debug/app-debug.apk build/werk-android-emulator.apk
	python3 scripts/android_apk_check.py build/werk-android-emulator.apk
android-release: apps
	cd droid && env WERK_ZIRAN_COMMAND="$(ZIRAN)" KRYON_DIR="$(KRYON_DIR)" ZIRAN_ROOT="$(ZIRAN_ROOT)" RAYLIB_DIR="$(RAYLIB_DIR)" LIBOQS_DIR="$(LIBOQS_DIR)" MONOCYPHER_DIR="$(MONOCYPHER_DIR)" ./gradlew assembleRelease -Pabi=$(ANDROID_ABIS) -PsplitApks=true $(GRADLE_ARGS)
.PHONY: android-fdroid
# F-Droid owns signing and updates. Keep the same package/version as the
# reference release; the suffix belongs to the unsigned output filename.
android-fdroid:
	$(MAKE) android-release GRADLE_ARGS="$(GRADLE_ARGS) -PfDroidBuild=true"
	cp droid/app/build/outputs/apk/release/app-universal-release-unsigned.apk build/werk-$(shell cat VERSION)-fdroid-unsigned.apk
	python3 scripts/android_apk_check.py build/werk-$(shell cat VERSION)-fdroid-unsigned.apk
android-smoke:
	bash scripts/android_smoke.sh
android-input-test:
	python3 scripts/android_input_test.py

# The pass command for Plan 9; transfer the checkout with build/plan9 and run mk.
plan9-c:
	mkdir -p build/plan9
	$(ZIRAN) build $(PROJECT) --define PLAN9_BUILD --target=plan9-c --entry cli:main -o build/plan9/cli apps/pass/cli.zi

check-package-urls:
	bash scripts/check_package_urls.sh
e2e: check-package-urls test gui-smoke gui-test web-smoke android-debug

install: install-cli install-gui
install-cli: cli
	mkdir -p $(BIN_DIR)
	install -m 0755 pass $(BIN_DIR)/pass
install-gui: gui
	mkdir -p $(BIN_DIR) $(DATA_DIR)/applications $(DATA_DIR)/icons/hicolor/512x512/apps $(DATA_DIR)/mime/packages
	install -d -m 0700 $(LIB_DIR) $(LIB_DIR)/apps
	install -m 0755 build/werk $(BIN_DIR)/werk
	install -m 0600 $(APP_BUNDLES) $(LIB_DIR)/apps/
	install -m 0644 build/pfp.png $(LIB_DIR)/pfp.png
	sed 's|^Exec=werk$$|Exec=$(BIN_DIR)/werk --bundle %f|' packaging/linux/xyz.waozi.werk.desktop > $(DATA_DIR)/applications/xyz.waozi.werk.desktop
	install -m 0644 packaging/linux/werk-bundle.xml $(DATA_DIR)/mime/packages/werk-bundle.xml
	@if command -v update-mime-database >/dev/null; then update-mime-database $(DATA_DIR)/mime; fi
	@if command -v update-desktop-database >/dev/null; then update-desktop-database $(DATA_DIR)/applications; fi
	cp assets/app/icon.png $(DATA_DIR)/icons/hicolor/512x512/apps/werk.png
uninstall-cli:
	rm -f $(BIN_DIR)/pass
uninstall-gui:
	rm -f $(BIN_DIR)/werk $(DATA_DIR)/applications/xyz.waozi.werk.desktop $(DATA_DIR)/icons/hicolor/512x512/apps/werk.png
	rm -rf $(LIB_DIR)
package-deb: gui
	./scripts/package-deb.sh
package-appimage: gui
	./scripts/package-appimage.sh
