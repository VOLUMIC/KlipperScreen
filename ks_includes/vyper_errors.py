# -*- coding: utf-8 -*-
# =============================================================================
# VyperOS - Traduction des erreurs Klipper / Moonraker / KlipperScreen
#
# Emplacement : ~/KlipperScreen/ks_includes/vyper_errors.py
#
# Principe :
#   - chaque entree de ERRORS associe un motif (regex) du message anglais
#     d'origine a un titre clair + une liste d'actions pour le client
#   - la premiere entree qui correspond gagne : les cas precis sont places
#     AVANT les cas generiques
#   - les textes d'aide anglais de Klipper (FIRMWARE_RESTART, hints...) sont
#     retires ; la premiere ligne d'origine est conservee en "Ref :" pour
#     le support
#
# Textes : ecrits en anglais (texte source) et traduits par le catalogue
# "volumic" (ks_includes/locales/<langue>/LC_MESSAGES/volumic.po), voir
# vyper_i18n.py. Les constantes sont marquees N_() et traduites a l'affichage
# par _v(), pour suivre un changement de langue sans redemarrer.
#
# Dans les titres et actions, {mcu_l}, {heater_l}, {sensor_l}, {stepper_l},
# {endstop_l} sont remplaces par un libelle lisible (ex : "carte principale",
# "tete d'impression (buse)", "moteur X"...). Les autres {xxx} reprennent
# directement la valeur trouvee dans le message.
# =============================================================================

import re

from ks_includes.vyper_i18n import _v, N_

# -----------------------------------------------------------------------------
# Actions reutilisables
# -----------------------------------------------------------------------------
RESTART = N_('Press "Restart VyperOS" at the bottom of the screen.')
POWERCYCLE = N_("Switch the printer off at the power switch, wait 30 seconds, "
                "then switch it back on.")
SUPPORT = N_("If the problem persists, contact VOLUMIC support with a photo "
             "of this message.")
SUPPORT_LOGS = N_("If the problem persists, contact VOLUMIC support and attach "
                  "the logs, which can be downloaded from the web interface.")
REPRINT = N_("A print in progress cannot be resumed: restart it from the "
             "beginning.")
SLICER = N_("Use the VOLUMIC profile of your slicer for YOUR model, then "
            "generate the file again.")
CONFIG_STEPS = [
    N_("If the configuration (printer.cfg) was modified, undo the last change "
       "from the web interface."),
    N_("Otherwise, update the VyperOS module from the Update menu."),
    RESTART,
    SUPPORT,
]

# En-tetes selon l'endroit ou le message est affiche
CONTEXT_HEADERS = {
    "shutdown": N_("The printer has put itself in safe mode"),
    "error": N_("The printer could not start"),
    "moonraker": N_("The screen cannot reach the API service"),
}


# -----------------------------------------------------------------------------
# Libelles lisibles (traduits tout de suite)
# -----------------------------------------------------------------------------
def _mcu_label(name):
    if not name:
        return _v("electronic board")
    n = name.strip().lower()
    if n == "mcu":
        return _v("main electronic board")
    if any(k in n for k in ("acc", "adxl", "lis", "mpu", "rp2040")):
        return _v("accelerometer board")
    return _v("electronic board '{name}'").format(name=name)


def _heater_label(name):
    if not name:
        return _v("heater")
    n = name.strip()
    for prefix in ("temperature_sensor ", "heater_generic ",
                   "temperature_fan ", "heater_fan "):
        if n.startswith(prefix):
            n = n[len(prefix):]
    low = n.lower()
    if low == "extruder":
        return _v("print head (nozzle)")
    if low.startswith("extruder"):
        return _v("print head {num} (nozzle)").format(num=n[len("extruder"):])
    if low == "heater_bed":
        return _v("heated bed")
    if low in ("alimentation", "protection"):
        return _v("sensor '{name}' (electronics enclosure)").format(name=n)
    if low in ("chambre", "chamber"):
        return _v("chamber sensor")
    return _v("sensor '{name}'").format(name=n)


def _stepper_label(name):
    if not name:
        return _v("motor")
    n = name.strip().lower()
    if n.startswith("stepper_"):
        return _v("motor {axis}").format(axis=n[len("stepper_"):].upper())
    if n.startswith("extruder"):
        return _v("extruder motor")
    return _v("motor '{name}'").format(name=name)


def _endstop_label(name):
    if not name:
        return _v("endstop")
    n = name.strip().lower()
    if n in ("x", "y", "z") or n.startswith("stepper_"):
        axis = n.replace("stepper_", "").upper()
        return _v("{axis} axis endstop").format(axis=axis)
    if "probe" in n:
        return _v("probe")
    return _v("sensor '{name}'").format(name=name)


_LABELS = {
    "mcu": _mcu_label,
    "heater": _heater_label,
    "sensor": _heater_label,
    "stepper": _stepper_label,
    "endstop": _endstop_label,
}


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# -----------------------------------------------------------------------------
# Actions dynamiques (renvoient des textes deja traduits)
# -----------------------------------------------------------------------------
def _steps_sensor_range(g):
    temp = _to_float(g.get("temp"))
    tmin = _to_float(g.get("min"))
    name = (g.get("sensor") or "").lower()
    electronic = any(k in name for k in ("alimentation", "protection"))
    if temp is not None and tmin is not None and temp < tmin:
        return [
            _v("The temperature sensor seems to be disconnected, cut or "
               "faulty."),
            _v("With the printer switched off, check the sensor connector: "
               "{label}.").format(label=_heater_label(g.get("sensor"))),
            _v(RESTART),
            _v(SUPPORT),
        ]
    if electronic:
        return [
            _v("The electronics enclosure has overheated."),
            _v("Check that its fans are running and that the vents are not "
               "blocked."),
            _v("Let the printer cool down, switched off, for 15 minutes."),
            _v(RESTART),
            _v(SUPPORT),
        ]
    return [
        _v("Overheating, or short-circuited temperature sensor."),
        _v("Let the printer cool down, switched off, for 15 minutes."),
        _v("Check the sensor cable and connector."),
        _v(RESTART),
        _v(SUPPORT),
    ]


def _fmt_temp(value):
    v = _to_float(value)
    if v is None:
        return "%s" % (value or "?")
    return ("%.1f" % v).rstrip("0").rstrip(".")


def _title_sensor_range(g):
    return _v("Abnormal temperature, {label}: {temp} °C (allowed: {min} to "
              "{max} °C)").format(
        label=_heater_label(g.get("sensor")), temp=_fmt_temp(g.get("temp")),
        min=_fmt_temp(g.get("min")), max=_fmt_temp(g.get("max")))


def _steps_heater(g):
    name = (g.get("heater") or "").lower()
    if name.startswith("extruder"):
        steps = [
            _v("Check that the silicone sock of the nozzle is in place."),
            _v("Check that the part cooling fan does not blow directly on the "
               "heater block."),
            _v("With the printer switched off, check the connectors of the "
               "heater cartridge and of the sensor on the head."),
        ]
    elif name == "heater_bed":
        steps = [
            _v("Check that the room is not too cold or exposed to a draught."),
            _v("With the printer switched off, check the bed connections."),
        ]
    else:
        steps = [_v("Check the heating element and its temperature sensor.")]
    return steps + [
        _v('Let it cool down, then press "Restart VyperOS".'),
        _v(SUPPORT),
    ]


# -----------------------------------------------------------------------------
# LISTE DES ERREURS
# (categorie, motif regex, titre, actions)
# Titre / actions : texte source anglais (traduit a l'affichage), ou fonction
# renvoyant le texte deja traduit.
# -----------------------------------------------------------------------------
_MCU = r"(?:Previous )?MCU '(?P<mcu>[^']+)' shutdown: "

ERRORS = [
    # ===== Connexion ecran <-> service API (Moonraker) =====================
    ("api", r"Errno 111\]|Connection refused",
     N_("The API service (Moonraker) is not responding"),
     [N_("Wait 1 to 2 minutes: the service may be starting or updating."),
      N_('Then press "Retry".'),
      POWERCYCLE,
      SUPPORT]),

    ("api", r"(?i)timed out|ConnectTimeout|ReadTimeout",
     N_("The API service (Moonraker) is taking too long to respond"),
     [N_("Wait 1 to 2 minutes (startup or file transfer in progress)."),
      N_('Then press "Retry".'),
      POWERCYCLE,
      SUPPORT]),

    ("api", r"401 Client Error|Unauthorized",
     N_("Access denied by the API service (Moonraker)"),
     [N_("The screen and the API service are no longer compatible, usually "
         "after a partial update."),
      N_("From a computer, open the printer's web interface and update the "
         "Display module (KlipperScreen)."),
      SUPPORT]),

    ("api", r"Unable to get printer info",
     N_("The API service is not sending the printer information"),
     [N_("Wait 1 minute, startup may be in progress."),
      N_('Then press "Retry".'),
      POWERCYCLE,
      SUPPORT]),

    ("api", r"Klippy Host not connected|Klippy Disconnected",
     N_("VyperOS is not connected to the API service"),
     [N_("Wait 1 minute, startup may be in progress."),
      RESTART,
      POWERCYCLE,
      SUPPORT]),

    # ===== Carte electronique (MCU) ========================================
    ("mcu", r"MCU Protocol error",
     N_("Incompatible electronic board firmware"),
     [N_("VyperOS was updated but not the firmware of the electronic board."),
      N_('Run a "Full Update": it reprograms the board automatically.'),
      N_("Do not unplug the printer during the whole update."),
      SUPPORT]),

    ("mcu", r"(?:mcu '(?P<mcu>[^']+)': )?Unable to connect",
     N_("Unable to connect to the {mcu_l}"),
     [N_("Check that the printer is switched on (main switch)."),
      N_("Check that the USB cable of the board is properly plugged in."),
      POWERCYCLE,
      SUPPORT]),

    ("mcu", r"Lost communication with MCU '(?P<mcu>[^']+)'",
     N_("Lost communication with the {mcu_l}"),
     [N_("Common cause: USB cable badly plugged in or disturbed, or a brief "
         "power cut."),
      N_("Check the USB cable of the board and that it does not run along the "
         "motor cables."),
      POWERCYCLE,
      REPRINT,
      SUPPORT]),

    ("mcu", r"MCU '(?P<mcu>[^']+)' spontaneous restart",
     N_("The {mcu_l} restarted by itself"),
     [N_("Usually caused by a voltage drop or an electrical disturbance."),
      N_("Plug the printer directly into a wall socket, without a power strip "
         "shared with powerful appliances."),
      RESTART,
      SUPPORT]),

    ("mcu", r"Serial connection closed|Timeout on wait for '[^']+' response"
            r"|Unable to obtain '[^']+' response",
     N_("The electronic board no longer responds"),
     [N_("Check that the USB cable of the board is properly plugged in."),
      POWERCYCLE,
      SUPPORT]),

    ("mcu", r"MCU '(?P<mcu>[^']+)' CRC does not match config"
            r"|Can not update MCU '[^']+' config",
     N_("The electronic board configuration must be reloaded"),
     [POWERCYCLE,
      SUPPORT]),

    ("mcu", r"Communication timeout during homing",
     N_("Communication lost during homing"),
     [N_("Often due to a momentary overload or to the USB cable."),
      RESTART,
      N_("Start the homing again."),
      SUPPORT]),

    # ----- Mises en securite de la carte (MCU shutdown) --------------------
    # La ligne "Sensor ... not in range" doit rester AVANT "ADC out of range"
    ("temperature",
     r"Sensor '(?P<sensor>[^']+)' temperature (?P<temp>\S+) not in range "
     r"(?P<min>[-\d.]+):(?P<max>[-\d.]+)",
     _title_sensor_range,
     _steps_sensor_range),

    ("temperature", _MCU + r"ADC out of range",
     N_("Temperature out of limits detected by the {mcu_l}"),
     [N_("A temperature sensor reports an abnormal value (overheating, "
         "disconnected or faulty sensor)."),
      N_("Let the printer cool down, switched off, for 15 minutes and check "
         "the sensor connectors."),
      RESTART,
      SUPPORT]),

    ("mcu", _MCU + r"Timer too close",
     N_("System overloaded: the {mcu_l} has put itself in safe mode"),
     [N_("The printer's computer could not keep up."),
      N_("During a print, avoid large file transfers, the webcam and multiple "
         "tabs of the web interface."),
      RESTART,
      REPRINT,
      SUPPORT]),

    ("mcu", _MCU + r"Missed scheduling of next",
     N_("Intermittent communication with the {mcu_l}"),
     [N_("Check that the USB cable is properly plugged in and does not run "
         "along the motor cables."),
      RESTART,
      REPRINT,
      SUPPORT]),

    ("mcu", _MCU + r"(?:Rescheduled timer in the past|Stepper too far in past)",
     N_("Movement too fast requested from the {mcu_l}"),
     [N_("The file requests speeds or accelerations that are too high."),
      SLICER,
      RESTART]),

    ("mcu", _MCU + r"Move queue overflow",
     N_("Movement queue full on the {mcu_l}"),
     [N_("The file contains too many very small movements."),
      SLICER,
      RESTART,
      SUPPORT]),

    ("mcu", _MCU + r"Watchdog timer",
     N_("The {mcu_l} has frozen"),
     [POWERCYCLE,
      SUPPORT]),

    ("mcu", _MCU + r"Command request",
     N_("Emergency stop"),
     [N_("The emergency stop was triggered (button, web interface or M112 "
         "command)."),
      N_('Check that nothing obstructs the machine, then press "Restart '
         'VyperOS".')]),

    ("temperature", _MCU + r"(?:Thermocouple reader fault|.*MAX31\d\d|"
                    r".*MAX6675)",
     N_("Temperature sensor fault (thermocouple)"),
     [N_("With the printer switched off, check the thermocouple connection."),
      RESTART,
      SUPPORT]),

    ("mcu", _MCU + r"(?i:.*(?:i2c|spi|sercom))",
     N_("Internal communication fault on the {mcu_l}"),
     [POWERCYCLE,
      SUPPORT]),

    ("mcu", _MCU,
     N_("The {mcu_l} has put itself in safe mode"),
     [RESTART,
      POWERCYCLE,
      SUPPORT]),

    # ===== Temperatures ====================================================
    ("temperature", r"Heater (?P<heater>\S+) not heating at expected rate",
     N_("The {heater_l} is not heating up normally"),
     _steps_heater),

    ("temperature", r"HOST temperature (?P<temp>[-\d.]+) (?:above|below)",
     N_("Abnormal temperature of the printer's computer ({temp} °C)"),
     [N_("Check that the electronics enclosure ventilation is working."),
      N_("Check that the room temperature is normal."),
      POWERCYCLE,
      SUPPORT]),

    ("temperature", r"Requested temperature \((?P<req>[-\d.]+)\) out of range "
                    r"\((?P<min>[-\d.]+):(?P<max>[-\d.]+)\)",
     N_("Requested temperature not possible: {req} °C (maximum {max} °C)"),
     [N_("The file or the command requests a temperature outside the machine "
         "limits."),
      N_("Check the material temperature in your slicer.")]),

    ("temperature", r"Extrude below minimum temp"
                    r"|Temperature too low to extrude",
     N_("Nozzle too cold to extrude"),
     [N_("Heat the nozzle to the filament temperature before loading, "
         "unloading or extruding."),
      N_("During a print: check the temperature requested in the file.")]),

    ("temperature", r"pid_calibrate interrupted",
     N_("Heater calibration (PID) interrupted"),
     [N_("Start the calibration again without using the printer during the "
         "operation.")]),

    # ===== Mouvements / prise d'origine / palpage ==========================
    ("mouvement", r"Must home (?:axis first|first|X and Y axes first"
                  r"|before probe)",
     N_("Homing required"),
     [N_("Home all axes before moving the head."),
      N_("If this happens at the start of a print: the slicer start code must "
         "contain G28.")]),

    ("mouvement", r"Move out of range",
     N_("Movement outside the print area"),
     [N_("The file or the command moves the head outside the allowed area."),
      N_("Check that the part fits in the print volume."),
      SLICER]),

    ("mouvement", r"No trigger on (?P<endstop>\S+) after full movement",
     N_("The {endstop_l} was not triggered"),
     [N_("Check that nothing blocks the axis movement."),
      N_("With the printer switched off, check the sensor connection."),
      N_("For the Z axis: clean the nozzle (no stuck filament)."),
      RESTART,
      SUPPORT]),

    ("mouvement", r"Endstop (?P<endstop>\S+) still triggered after retract",
     N_("The {endstop_l} remains triggered"),
     [N_("Check that the sensor is not blocked, dirty or disconnected."),
      RESTART,
      SUPPORT]),

    ("mouvement", r"Probe triggered prior to movement",
     N_("The probe was already triggered before the measurement"),
     [N_("Remove the filament or material stuck under the nozzle."),
      N_("Check that the nozzle is not already touching the bed."),
      RESTART,
      SUPPORT]),

    ("mouvement", r"Probe samples exceed",
     N_("Inconsistent probe measurements"),
     [N_("Clean the nozzle (no drop of filament) and the bed."),
      N_("Check that the bed is firmly fixed and that nothing vibrates."),
      N_("Start the calibration again."),
      SUPPORT]),

    ("mouvement", r"Timeout during (?:endstop )?homing",
     N_("Timeout during homing"),
     [N_("Check that nothing blocks the axes."),
      RESTART,
      SUPPORT]),

    ("mouvement", r"(?:Homing|Probing) failed due to printer shutdown",
     N_("Homing interrupted by a safety shutdown"),
     [N_("The cause is given in the previous error message.")]),

    ("mouvement", r"Retries aborting|Too many retries",
     N_("The automatic parallelism adjustment failed"),
     [N_("Clean the nozzle and the bed."),
      N_("Check that nothing obstructs the axis mechanics."),
      N_("Start the calibration again."),
      SUPPORT]),

    ("mouvement", r"bed level exceeds configured limits",
     N_("Bed tilted too much"),
     [N_("Adjust the bed screws (Bed Level menu), then start again.")]),

    ("mouvement", r"bed_mesh: Unknown profile \[(?P<profile>[^\]]*)\]",
     N_("Bed mesh '{profile}' not found"),
     [N_("Run a new bed calibration from the Bed Mesh menu, then save.")]),

    # ===== Extrusion =======================================================
    ("extrusion", r"Extrude only move too long \((?P<req>[\d.]+)mm vs "
                  r"(?P<max>[\d.]+)mm\)",
     N_("Requested extrusion too long ({req} mm, maximum {max} mm)"),
     [N_("To load or unload the filament, use the Extrude menu."),
      N_("Otherwise, extrude in several short lengths.")]),

    ("extrusion", r"Move exceeds maximum extrusion",
     N_("Requested material flow too high"),
     [N_("The file requests more material than the nozzle can deliver."),
      N_("In the slicer, check the filament diameter, the extrusion width and "
         "the layer height."),
      SLICER]),

    # ===== Pilotes moteurs (TMC) ===========================================
    ("moteur", r"TMC '(?P<stepper>[^']+)' reports error: .*\b(?:ot|otpw)=1",
     N_("Overheating of the {stepper_l} driver"),
     [N_("Check that the electronics enclosure fans are running and that the "
         "vents are clear."),
      N_("Let the printer cool down, switched off, for 15 minutes."),
      RESTART,
      SUPPORT]),

    ("moteur", r"TMC '(?P<stepper>[^']+)' reports error: "
               r".*\b(?:s2ga|s2gb|s2vsa|s2vsb)=1",
     N_("Short circuit detected on the {stepper_l}"),
     [N_("Switch the printer off immediately."),
      N_("Check that the motor cable is not damaged, pinched or badly "
         "plugged in."),
      SUPPORT]),

    ("moteur", r"TMC '(?P<stepper>[^']+)' reports error: "
               r".*\b(?:uv_cp|reset)=1",
     N_("Power loss on the {stepper_l} driver"),
     [N_("The motor driver lost its power supply (brief power cut or voltage "
         "drop)."),
      N_("Plug the printer directly into a wall socket."),
      RESTART,
      SUPPORT]),

    ("moteur", r"TMC '(?P<stepper>[^']+)' reports error",
     N_("Fault on the {stepper_l} driver"),
     [RESTART,
      POWERCYCLE,
      SUPPORT]),

    ("moteur", r"Unable to (?:read|write) tmc uart '(?P<stepper>[^']+)'",
     N_("The {stepper_l} driver is not responding"),
     [N_("Most common cause: the power supply (24V) is off while the screen "
         "is on."),
      N_("Check the main switch and the printer power supply."),
      POWERCYCLE,
      SUPPORT]),

    ("moteur", r"TMC (?P<stepper>\S+) failed to init",
     N_("The {stepper_l} driver does not start"),
     [N_("Most common cause: the power supply (24V) is off while the screen "
         "is on."),
      N_("Check the main switch and the printer power supply."),
      POWERCYCLE,
      SUPPORT]),

    # ===== Accelerometre ===================================================
    ("accelerometre", r"Invalid (?:adxl345|lis2dw|lis3dh|mpu) id"
                      r"|No accelerometer measurements found"
                      r"|accelerometer measured no data",
     N_("The accelerometer is not responding"),
     [N_("With the printer switched off, check the accelerometer cable "
         "connection."),
      POWERCYCLE,
      N_("Start the calibration again."),
      SUPPORT]),

    # ===== Fichiers / commandes ============================================
    ("fichier", r"Unable to open file",
     N_("Unable to open the print file"),
     [N_("The file may have been deleted, renamed or be corrupted."),
      N_("Copy it again (USB stick or web interface) and restart the "
         "print.")]),

    ("fichier", r"SD busy",
     N_("A print is already in progress"),
     [N_("Wait for the current print to finish or cancel it before starting "
         "another one.")]),

    ("fichier", r"Unknown command:\s*\"?(?P<cmd>[^\"\s]+)",
     N_("Unknown command in the file: {cmd}"),
     [N_("The file contains a command the printer does not know (file "
         "prepared for another printer?)."),
      SLICER,
      N_("This alert does not stop the print.")]),

    ("fichier", r"Malformed command",
     N_("Malformed command in the file"),
     [N_("The file is probably corrupted: generate it again and copy it "
         "again.")]),

    ("fichier", r"Error on '(?P<cmd>[^']+)':",
     N_("Invalid parameter for the command {cmd}"),
     [N_("Check the custom start / end code in your slicer."),
      SUPPORT]),

    ("securite", r"Shutdown due to (?:M112 command|webhooks request)",
     N_("Emergency stop"),
     [N_("The emergency stop was triggered (screen, web interface or file)."),
      N_('Check that nothing obstructs the machine, then press "Restart '
         'VyperOS".')]),

    # ===== Configuration ===================================================
    ("configuration", r"Option '(?P<opt>[^']+)' in section '(?P<sect>[^']+)' "
                      r"must be specified",
     N_("Required setting missing: {opt} in [{sect}]"),
     CONFIG_STEPS),

    ("configuration", r"Option '(?P<opt>[^']+)' is not valid in section "
                      r"'(?P<sect>[^']+)'",
     N_("Unknown setting: {opt} in [{sect}]"),
     CONFIG_STEPS),

    ("configuration", r"Section '(?P<sect>[^']+)' is not a valid config section",
     N_("Unknown configuration section: [{sect}]"),
     CONFIG_STEPS),

    ("configuration", r"Unable to parse option '(?P<opt>[^']+)' in section "
                      r"'(?P<sect>[^']+)'",
     N_("Unreadable value: {opt} in [{sect}]"),
     CONFIG_STEPS),

    ("configuration", r"Option '(?P<opt>[^']+)' in section '(?P<sect>[^']+)' "
                      r"must (?:be|have)",
     N_("Value out of limits: {opt} in [{sect}]"),
     CONFIG_STEPS),

    ("configuration", r"Include file '(?P<file>[^']+)' does not exist",
     N_("Missing configuration file: {file}"),
     CONFIG_STEPS),

    ("configuration", r"Existing config autosave is corrupted",
     N_("Configuration automatic backup corrupted"),
     CONFIG_STEPS),

    ("configuration", r"pin \S+ used multiple times|is not a valid pin name"
                      r"|Unknown pin chip name|Unknown config object",
     N_("Error in the printer configuration"),
     CONFIG_STEPS),

    # ===== Service API (Moonraker) : avertissements / mises a jour =========
    ("api", r"Unparsed config (?:section|option)",
     N_("API service configuration warning"),
     [N_("This message does not prevent printing."),
      N_("It will disappear at the next update of the VyperOS module.")]),

    ("api", r"(?i)failed components",
     N_("A module of the API service did not start"),
     [N_("Printing is still possible, some functions may be missing."),
      N_('Run a "Full Update".'),
      SUPPORT]),

    ("api", r"Missing Klipper configuration",
     N_("Incomplete VyperOS configuration for the API service"),
     CONFIG_STEPS),

    ("update", r"(?i)Git Repo (?P<repo>[^:\s]+):.*(?:dirty|diverged|invalid"
               r"|detached)|Repo has diverged",
     N_("The {repo} module cannot be updated automatically"),
     [N_('Run a "Full Update" from the Update menu.'),
      SUPPORT]),

    ("update", r"(?i)(?:error|failed).{0,40}updat|updat.{0,40}(?:error|failed)",
     N_("Update failed"),
     [N_("Check that the printer is connected to the Internet."),
      N_("Start the update again without switching the machine off during the "
         "operation."),
      SUPPORT]),

    # ===== Erreurs internes (a garder en dernier) ==========================
    ("interne", r"Internal error|Exception in |Unhandled exception",
     N_("Internal software error"),
     [RESTART,
      POWERCYCLE,
      SUPPORT_LOGS]),
]

_COMPILED = [(cat, re.compile(pat, re.S), title, steps)
             for cat, pat, title, steps in ERRORS]


# -----------------------------------------------------------------------------
# Textes d'aide anglais de Klipper a retirer avant analyse / affichage
# -----------------------------------------------------------------------------
def _loose(text):
    """Motif tolerant aux sauts de ligne / espaces multiples."""
    words = [re.escape(w) for w in text.split()]
    return r"\s*" + r"\s+".join(words) + r"\s*"


_BOILERPLATE = [re.compile(_loose(t), re.S) for t in (
    'Once the underlying issue is corrected, use the "FIRMWARE_RESTART" '
    'command to reset the firmware, reload the config, and restart the host '
    'software.',
    'Once the underlying issue is corrected, use the "RESTART" command to '
    'reload the config and restart the host software.',
    'Printer is shutdown',
    'Printer is halted',
    'Error configuring printer',
    'This often indicates the host computer is overloaded. Check for other '
    'processes consuming excessive CPU time, high swap usage, disk errors, '
    'overheating, unstable voltage, or similar system problems on the host '
    'computer.',
    'This is generally indicative of an intermittent communication failure '
    'between micro-controller and host.',
    'This generally occurs when a heater temperature exceeds its configured '
    'min_temp or max_temp.',
    'This generally occurs when the micro-controller has been requested to '
    'step at a rate higher than it is capable of obtaining.',
    'This generally occurs in response to an M112 G-Code command or in '
    'response to an internal error in the host software.',
    "See the 'verify_heater' section in docs/Config_Reference.md for the "
    "parameters that control this check.",
    'This is frequently caused by running an older version of the firmware '
    'on the MCU(s). Fix by recompiling and flashing the firmware.',
)] + [
    re.compile(r"See the '[^']+' config option(?: for details)?\.?", re.S),
    re.compile(r"This is generally indicative of connection problems\s*"
               r"\(e\.g\. faulty wiring\) or a faulty \w+ chip\.?", re.S),
]


def clean(message):
    """Retire les textes d'aide anglais et les lignes vides superflues."""
    text = "%s" % (message or "")
    if text.startswith("!! "):
        text = text[3:]
    for rx in _BOILERPLATE:
        text = rx.sub("\n", text)
    lines = [ln.rstrip() for ln in text.splitlines()]
    out = []
    for ln in lines:
        if ln.strip() or (out and out[-1].strip()):
            out.append(ln)
    return "\n".join(out).strip()


class _SafeDict(dict):
    def __missing__(self, key):
        return ""


def translate(message):
    """
    Analyse un message d'erreur.
    Retourne un dict {category, title, steps, ref} (textes traduits dans la
    langue courante) ou None si inconnu.
    """
    text = clean(message)
    if not text:
        return None
    for cat, rx, title, steps in _COMPILED:
        m = rx.search(text)
        if not m:
            continue
        groups = {k: v for k, v in m.groupdict().items() if v is not None}
        values = _SafeDict(groups)
        for key, labeler in _LABELS.items():
            values[key + "_l"] = labeler(groups.get(key))
        if callable(title):
            title_txt = title(values)
        else:
            title_txt = _v(title).format_map(values)
        if callable(steps):
            step_list = steps(values)
        else:
            step_list = [_v(s).format_map(values) for s in steps]
        # Ref = ligne d'origine ou le motif a ete trouve
        start = text.rfind("\n", 0, m.start()) + 1
        end = text.find("\n", m.start())
        ref = text[start:end if end != -1 else len(text)].strip()
        return {
            "category": cat,
            "title": title_txt,
            "steps": step_list,
            "ref": ref,
        }
    return None


def format_message(message, context=None, fallback=True, show_ref=True):
    """Version securisee : en cas de bug, renvoie le message d'origine."""
    try:
        return _format_message(message, context, fallback, show_ref)
    except Exception:
        return "%s" % (message or "")


def _format_message(message, context=None, fallback=True, show_ref=True):
    """
    Texte pret a afficher, dans la langue courante.
      context  : "shutdown", "error", "moonraker" ou None (popup)
      fallback : si le message est inconnu, True = texte generique +
                 message d'origine ; False = message d'origine inchange
      show_ref : ajoute la ligne "Ref :" (message d'origine) pour le support
    """
    info = translate(message)
    header = CONTEXT_HEADERS.get(context)
    lines = []
    if header:
        lines += [_v(header), ""]
    what_to_do = _v("What to do:")
    if info is None:
        if not fallback:
            return "%s" % (message or "")
        detail = clean(message)
        if detail:
            lines += [detail, ""]
        if context == "moonraker":
            first = _v('Wait 1 to 2 minutes, then press "Retry".')
        else:
            first = _v(RESTART)
        lines += [what_to_do,
                  "- " + first,
                  "- " + _v(POWERCYCLE),
                  "- " + _v(SUPPORT)]
        return "\n".join(lines)
    lines.append(info["title"])
    lines += ["", what_to_do]
    lines += ["- " + s for s in info["steps"]]
    if show_ref and info["ref"]:
        lines += ["", _v("Ref: {ref}").format(ref=info["ref"])]
    return "\n".join(lines)


def klippy_state_label(state):
    """Libelle de l'etat Klipper renvoye par le service API."""
    labels = {
        "ready": N_("ready"),
        "startup": N_("starting up"),
        "disconnected": N_("waiting for connection"),
        "shutdown": N_("in safe mode"),
        "error": N_("in error"),
    }
    return _v(labels[state]) if state in labels else state
