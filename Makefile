.PHONY: i18n build

i18n:
	./tools/i18n.sh

build:
	dpkg-buildpackage -us -uc
