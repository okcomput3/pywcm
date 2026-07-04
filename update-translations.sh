#!/bin/sh
# Regenerate locale/wcm.pot from the sources and merge it into every
# existing locale/<lang>/LC_MESSAGES/wcm.po. Requires gettext tools
# (xgettext + msgmerge). Run from the project root after changing any
# user-facing string.
set -e
cd "$(dirname "$0")"

xgettext --language=Python --keyword=_ --keyword=N_ --from-code=UTF-8 \
         --package-name=wcm --add-comments=TRANSLATORS \
         -o locale/wcm.pot \
         wcm.py config_backend.py metadata.py i18n.py

for po in locale/*/LC_MESSAGES/wcm.po; do
    [ -f "$po" ] || continue
    echo "merging $po"
    msgmerge --update --backup=off "$po" locale/wcm.pot
done

echo "Done. Translate the new msgids, then just run wcm.py —"
echo "catalogs are compiled automatically at startup."
