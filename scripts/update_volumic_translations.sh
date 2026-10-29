#!/bin/sh
# VOLUMIC : met a jour le catalogue de traduction "volumic" (textes VOLUMIC)
# A lancer depuis la racine de KlipperScreen (necessite le paquet gettext).
# Equivalent Poedit : ouvrir ks_includes/locales/<langue>/LC_MESSAGES/volumic.po,
# Traduction > Mettre a jour depuis le fichier POT (volumic.pot), puis Enregistrer
# (Poedit regenere le .mo).

# 1) Modele : tous les textes _v("..."), N_("...") et vgettext('...')
xgettext --keyword= --keyword=_v --keyword=N_ --keyword=vgettext \
    --language=Python --from-code=UTF-8 --no-location --sort-output \
    --package-name=VyperOS \
    -o ks_includes/locales/volumic.pot \
    screen.py ks_includes/*.py panels/*.py

# 2) Fusion dans chaque langue + compilation
for DIR in ks_includes/locales/*/; do
    PO="${DIR}LC_MESSAGES/volumic.po"
    if [ -f "$PO" ]; then
        echo "Traitement de $PO"
        msgmerge -q --no-wrap "$PO" ks_includes/locales/volumic.pot -o "$PO"
        msgfmt --check -o "${DIR}LC_MESSAGES/volumic.mo" "$PO"
    fi
done
