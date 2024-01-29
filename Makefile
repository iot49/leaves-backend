.PHONY: check version build build-generic lib firmware flash micropython

SHELL           := /bin/bash
TAG             := $(shell date +"%Y.%m.%d")

# FIRMWARE_DIR    := ../iot49.github.io/leaf-firmware
FIRMWARE_DIR    := ../frontend/public/firmware
USER_C_MODULES  := /project/mp/modules/micropython.cmake
FROZEN_MANIFEST := /project/code-freeze/manifest.py
BOARD_DIR       := /project/mp/boards/ESP32_S3_WROOM_1_N16R8/
BOARD           ?= $(notdir $(BOARD_DIR:/=))
BUILD_DIR       := micropython/ports/esp32/build-${BOARD}


flash: # firmware
	@ls /dev/*usb*
	esptool.py erase_flash
	esptool.py --chip esp32s3 write_flash -z 0 micropython/ports/esp32/build-${BOARD}/firmware.bin

firmware: build
	echo create firmware and copy to ${FIRMWARE_DIR}
	@ mkdir -p ${FIRMWARE_DIR}
	# initial flash
	@cp        ${BUILD_DIR}/firmware.bin     ${FIRMWARE_DIR}/firmware-${TAG}.bin
	# ota binary
	@cp        ${BUILD_DIR}/micropython.bin  ${FIRMWARE_DIR}/micropython-${TAG}.bin
	# index.json
	@ zsh -c "./bin/make_firmware_index.py   ${FIRMWARE_DIR}"

# build custom Micropython VM with code-freeze built in
build: version
	zsh -c ./bin/make_default_config.py
	@echo copy board spec and partition table
	cp -a mp/boards/ESP32_S3_WROOM_1_N16R8 micropython/ports/esp32/boards 
	cp -a mp/boards/ESP32_S3_WROOM_1_N16R8/partitions-S3-N16-custom.csv micropython/ports/esp32
	@echo compile
	docker run --rm -v .:/project -w /project espressif/idf:v5.0.4 \
		bash -c " \
			cd micropython/ports/esp32; \
			make clean BOARD_DIR=${BOARD_DIR}; \
			make V=1 BOARD=ESP32_S3_WROOM_1_N16R8 FROZEN_MANIFEST=${FROZEN_MANIFEST}"

# build custom Micropython VM with code-freeze built in
build-backup: version
	zsh -c ./bin/make_default_config.py
	@echo copy board spec and partition table
	cp -a mp/boards/ESP32_S3_WROOM_1_N16R8 micropython/ports/esp32/boards 
	cp -a mp/boards/ESP32_S3_WROOM_1_N16R8/partitions-S3-N16-custom.csv micropython/ports/esp32
	@echo compile
	docker run --rm -v .:/project -w /project espressif/idf:v5.0.4 \
		bash -c " \
			cd micropython/ports/esp32; \
			ls -l .; \
			make clean IDF_TARGET=esp32s3 BOARD_DIR=${BOARD_DIR}; \
			make V=1 \
				BOARD_DIR=${BOARD_DIR} \
				USER_C_MODULES=${USER_C_MODULES} \
				FROZEN_MANIFEST=${FROZEN_MANIFEST}"

# generic Micropython VM for esp32
build-generic-s3:
	@echo mpy-cross
	cd micropython; make V=1 -C mpy-cross; cd ..
	@echo esp32/generic
	docker run --rm -v .:/project -w /project espressif/idf:v5.0.4 \
		bash -c "cd micropython/ports/esp32; make clean; make submodules; make V=1 BOARD=ESP32_GENERIC_S3"

# update version in code-freeze to today's date
version:
	echo Update 'code-freeze/version.py' to $(TAG), tag repo and push
	git switch main
	echo \# automatically updated by Makefile >code-freeze/version.py
	echo VERSION = \"$(TAG)\" >>code-freeze/version.py

# clone and configure Micropython repo
download-micropython:
	git clone https://github.com/micropython/micropython.git

micropython: download-micropython
	cd micropython; \
	cd mpy-cross; make; cd ..; \
	cd ports/unix; make submodules; make; cd ../..; \
	cd ports/esp32; make submodules; cd ../..

# sync cloned Micropython repo to github:micropython/micropython
update-micropython: micropython
	cd micropython; git switch master; git pull; git merge master


# download libraries
TARGET := code
TARGET_M := code/lib/microdot
MPY     := micropython/ports/unix/build-standard/micropython -m mip install --no-mpy --target code/lib
MPY_DOT := micropython/ports/unix/build-standard/micropython -m mip install --no-mpy --target code/lib/microdot

lib:
	${MPY} datetime
	${MPY} hmac
	${MPY} pyjwt
	${MPY} unittest
	${MPY} aioble
	${MPY} aiohttp
	${MPY} urllib.urequest
	# microdot webserver
	${MPY_DOT} github:miguelgrinberg/microdot/src/microdot/__init__.py
	${MPY_DOT} github:miguelgrinberg/microdot/src/microdot/microdot.py
	${MPY_DOT} github:miguelgrinberg/microdot/src/microdot/websocket.py
	${MPY_DOT} github:miguelgrinberg/microdot/src/microdot/session.py
	${MPY_DOT} github:miguelgrinberg/microdot/src/microdot/sse.py
	${MPY_DOT} github:miguelgrinberg/microdot/src/microdot/cors.py
	${MPY_DOT} github:miguelgrinberg/microdot/src/microdot/jinja.py
	${MPY_DOT} github:miguelgrinberg/microdot/src/microdot/utemplate.py
	${MPY_DOT} github:miguelgrinberg/microdot/src/microdot/test_client.py
	cp -a code/lib/ code-freeze/lib
