.PHONY: version build

# micropython repo branch
TAG    := `date +"%Y.%m.%d"`
BRANCH := mp
BOARD  := ESP32-S3-WROOM-1-N16R8
SHELL  := /bin/bash


# build custom Micropython VM with code-freeze built in
build:
	@cd micropython; git switch ${BRANCH}
	@rm -rf micropython/ports/esp32/build-${BOARD}
	docker run --rm -v \
		.:/project \
		-w /project espressif/idf:v5.0.2 \
		bash -c "cd micropython/ports/esp32; make IDF_TARGET=esp32s3 BOARD=${BOARD} FROZEN_MANIFEST=/project/code-freeze/manifest.py"
	ls -l micropython/ports/esp32/build-{BOARD}/*bin

# update version in code-freeze to today's date
version: check
	echo Update 'code-freeze/version.py', tag repo and push
	@git switch main
	@echo \# automatically updated by Makefile >code-freeze/version.py
	@echo VERSION = \"$(TAG)\" >>code-freeze/version.py
	@git tag $(TAG) main
	@git commit -am "update version to $(TAG)"
	@git push origin main
	@git push origin $(TAG)

# check that all changes in micropython and backend repos have been committed and pushed to github
check:
	@cd micropython; \
	git switch $(BRANCH); \
	if [[ -n `git status --porcelain=v1 2>/dev/null` ]]; then \
		echo "Micropython branch '$(BRANCH)' is not clean."; \
		echo "Commit and push all changes to github and try make again."; \
		exit 1; \
	fi; \
	if [[ -n `git diff --stat --cached origin/$(BRANCH)` ]]; then \
		echo "Micropython branch '$(BRANCH)' has commits that have not been pushed."; \
		echo "Push all changes to github and try make again."; \
		exit 1; \
	fi

	@if [[ -n `git status --porcelain=v1 2>/dev/null` ]]; then \
		echo "'backend' repo is not clean."; \
		echo "Commit and push all changes to github and try make again."; \
		exit 1; \
	fi
	if [[ -n `git diff --stat --cached origin/main` ]]; then \
		echo "'backend' repo has commits that have not been pushed."; \
		echo "Push all changes to github and try make again."; \
		exit 1; \
	fi

# clone and configure Micropython repo
micropython:
	git clone https://github.com/iot49/micropython.git
	cd micropython/mpy-cross; make
	cd micropython/ports/esp32; make submodules

