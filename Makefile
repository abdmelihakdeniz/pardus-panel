.PHONY: run i18n validate build clean

run:
	PYTHONPATH=src python3 -m pardus_panel

i18n:
	./tools/i18n.sh

validate:
	python3 -m compileall -q src
	desktop-file-validate src/pardus_panel/data/applications/tr.org.pardus.panel.desktop
	appstreamcli validate --no-net src/pardus_panel/data/metainfo/tr.org.pardus.panel.metainfo.xml
	msgfmt --check --output-file=/dev/null po/tr.po

build:
	dpkg-buildpackage -us -uc -b

clean:
	debian/rules clean
