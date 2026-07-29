#!/bin/sh
set -eu

domain=pardus-panel
locale_dir=src/pardus_panel/locales
po_dir=po
version=$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
mkdir -p "$po_dir" "$locale_dir/tr/LC_MESSAGES"

find src/pardus_panel -name '*.py' -print | sort | \
xgettext --force-po --from-code=UTF-8 --language=Python --keyword=_ --files-from=- \
	--package-name="$domain" --package-version="$version" \
	--copyright-holder=abdmelihakdeniz \
	--msgid-bugs-address=melowiann@gmail.com \
	--output="$po_dir/$domain.pot"
find src/pardus_panel/data/ui -name '*.ui' -print | sort | \
xgettext --from-code=UTF-8 --language=Glade --join-existing --files-from=- \
	--package-name="$domain" --package-version="$version" \
	--copyright-holder=abdmelihakdeniz \
	--msgid-bugs-address=melowiann@gmail.com \
	--output="$po_dir/$domain.pot"

if [ -f "$po_dir/tr.po" ]; then
	msgmerge --quiet --backup=none --update "$po_dir/tr.po" "$po_dir/$domain.pot"
else
	msginit --no-translator --locale=tr --input="$po_dir/$domain.pot" --output-file="$po_dir/tr.po"
fi

msgfmt --check --output-file="$locale_dir/tr/LC_MESSAGES/$domain.mo" "$po_dir/tr.po"
