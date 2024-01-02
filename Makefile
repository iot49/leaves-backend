.PHONY: check version build lib firmware flash micropython

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
			ls -l .; \
			make clean IDF_TARGET=esp32s3 BOARD_DIR=${BOARD_DIR}; \
			make V=1 IDF_TARGET=esp32s3 \
				BOARD_DIR=${BOARD_DIR} \
				USER_C_MODULES=${USER_C_MODULES} \
				FROZEN_MANIFEST=${FROZEN_MANIFEST}"

# update version in code-freeze to today's date
version:
	echo Update 'code-freeze/version.py' to $(TAG), tag repo and push
	git switch main
	echo \# automatically updated by Makefile >code-freeze/version.py
	echo VERSION = \"$(TAG)\" >>code-freeze/version.py

# clone and configure Micropython repo
download-micropython:
	git clone https://github.com/micropython/micropython.git

micropython:
	cd micropython; \
	cd mpy-cross; make; cd ..; \
	cd ports/unix; make submodules; make; cd ../..; \
	cd ports/esp32; make submodules; cd ../..

# sync cloned Micropython repo to github:micropython/micropython
update-micropython: micropython
	cd micropython; git switch master; git pull; git merge master


# download libraries

TARGET := code/lib
MPY    := micropython/ports/unix/build-standard/micropython -m mip install --no-mpy --target ${TARGET}

lib:
	${MPY} urllib.urequest
	# BUG: ??? installs old version ???
	# ${MPY} aioble

lib-update:
	# microdot webserver
	${MPY} github:miguelgrinberg/microdot/src/microdot.py
	${MPY} github:miguelgrinberg/microdot/src/microdot_websocket.py
	${MPY} github:miguelgrinberg/microdot/src/microdot_asyncio.py
	${MPY} github:miguelgrinberg/microdot/src/microdot_asyncio_websocket.py
