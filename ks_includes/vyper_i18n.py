# -*- coding: utf-8 -*-
# =============================================================================
# VyperOS - Traductions des textes VOLUMIC (catalogue "volumic")
#
# Emplacement : ~/KlipperScreen/ks_includes/vyper_i18n.py
#
# Les textes VOLUMIC sont ecrits en anglais dans le code (texte source) et
# traduits dans ks_includes/locales/<langue>/LC_MESSAGES/volumic.po / .mo.
# Ce catalogue est separe de KlipperScreen.po pour ne jamais entrer en conflit
# avec les traductions d'origine de KlipperScreen.
#
# La langue suit celle choisie dans KlipperScreen : config.install_language()
# appelle set_language(). Langue sans traduction -> texte anglais.
#
# Utilisation :
#   from ks_includes.vyper_i18n import _v, N_
#   _v("Update {name}?").format(name=program)   # traduit tout de suite
#   RESTART = N_("Press ...")                    # marque seulement le texte,
#   ...  _v(RESTART)                             # traduit a l'affichage
#
# Mise a jour des traductions : scripts/update_volumic_translations.sh
# (ou Poedit : ouvrir le .po, "Mettre a jour depuis le fichier POT", enregistrer).
# =============================================================================

import gettext
import logging
import os

_LOCALEDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
_translation = gettext.NullTranslations()
_language = "en"


def set_language(lang):
    """Charge le catalogue volumic de la langue choisie dans KlipperScreen."""
    global _translation, _language
    _language = lang or "en"
    try:
        _translation = gettext.translation(
            "volumic", localedir=_LOCALEDIR, languages=[_language], fallback=True)
    except Exception as e:
        logging.warning(f"volumic : traductions indisponibles pour {_language} : {e}")
        _translation = gettext.NullTranslations()


def get_language():
    return _language


def _v(text):
    """Traduit un texte VOLUMIC dans la langue courante."""
    if not text:
        return text
    return _translation.gettext(text)


def N_(text):
    """Marque un texte a traduire plus tard (constantes calculees au chargement)."""
    return text


# Noms de menus VOLUMIC utilises dans .volumic/system/KlipperScreen.conf
# ({{ vgettext('...') }}) : declares ici pour figurer dans volumic.pot
MENU_NAMES = [
    N_("Fine tuning"),
    N_("IP configuration"),
]
