import logging
import os
import re
import socket
import subprocess
import threading
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from ks_includes.screen_panel import ScreenPanel

INTERFACES_FILE    = "/etc/network/interfaces"
INTERFACES_DEFAULT = "/etc/network/interfaces.default"

DHCP_TEMPLATE = """source /etc/network/interfaces.d/*
# Network is managed by Network manager
auto lo
iface lo inet loopback
 
auto eth0
iface eth0 inet dhcp
        hwaddress ether {mac}

auto wlan0
iface wlan0 inet dhcp
        hwaddress ether {mac}
"""

STATIC_TEMPLATE = """source /etc/network/interfaces.d/*
# Network is managed by Network manager
auto lo
iface lo inet loopback
 
auto eth0
iface eth0 inet static
    hwaddress ether {mac}
    address {address}
    netmask {netmask}
    gateway {gateway}
    dns-nameservers {dns}

auto wlan0
iface wlan0 inet static
    hwaddress ether {mac}
    address {address}
    netmask {netmask}
    gateway {gateway}
    dns-nameservers {dns}
"""


def _get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "Non disponible"


class OctetSpin(Gtk.Box):
    """[-][valeur][+] pour un octet 0-255, grande taille tactile."""

    def __init__(self, value=0):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self._value = max(0, min(255, int(value)))

        self._btn_dn = Gtk.Button(label=" - ")
        self._btn_dn.set_relief(Gtk.ReliefStyle.NONE)
        self._btn_dn.connect("clicked", self._decrement)

        self._lbl = Gtk.Label()
        self._lbl.set_markup("<span size='x-large' weight='bold'>" + str(self._value) + "</span>")
        self._lbl.set_width_chars(3)
        self._lbl.set_xalign(0.5)

        self._btn_up = Gtk.Button(label=" + ")
        self._btn_up.set_relief(Gtk.ReliefStyle.NONE)
        self._btn_up.connect("clicked", self._increment)

        self.pack_start(self._btn_dn, False, False, 0)
        self.pack_start(self._lbl,    False, False, 0)
        self.pack_start(self._btn_up, False, False, 0)

    def _update(self):
        self._lbl.set_markup("<span size='x-large' weight='bold'>" + str(self._value) + "</span>")

    def _increment(self, *a):
        self._value = min(255, self._value + 1)
        self._update()

    def _decrement(self, *a):
        self._value = max(0, self._value - 1)
        self._update()

    def get_value(self):
        return self._value

    def set_value(self, v):
        try:
            self._value = max(0, min(255, int(v)))
        except Exception:
            self._value = 0
        self._update()

    def set_sensitive(self, s):
        super().set_sensitive(s)
        self._btn_up.set_sensitive(s)
        self._btn_dn.set_sensitive(s)
        self._lbl.set_sensitive(s)


class IpWidget(Gtk.Box):
    """4 OctetSpin avec points fixes entre eux."""

    def __init__(self, ip="0.0.0.0"):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        parts = (ip or "0.0.0.0").split(".")
        if len(parts) != 4:
            parts = ["0", "0", "0", "0"]
        self._octets = []
        for i, p in enumerate(parts):
            spin = OctetSpin(value=int(p) if p.isdigit() else 0)
            self._octets.append(spin)
            self.pack_start(spin, False, False, 0)
            if i < 3:
                dot = Gtk.Label()
                dot.set_markup("<span size='x-large' weight='bold'>.</span>")
                self.pack_start(dot, False, False, 4)

    def get_ip(self):
        return ".".join(str(o.get_value()) for o in self._octets)

    def set_ip(self, ip):
        parts = (ip or "0.0.0.0").split(".")
        if len(parts) != 4:
            parts = ["0", "0", "0", "0"]
        for i, o in enumerate(self._octets):
            o.set_value(parts[i])

    def set_sensitive(self, s):
        super().set_sensitive(s)
        for o in self._octets:
            o.set_sensitive(s)


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Reseau")
        super().__init__(screen, title)
        self.labels   = {}
        self._iface   = "eth0"
        self._mac     = "00:00:00:00:00:00"
        self._is_dhcp = True
        self._address = "192.168.0.30"
        self._netmask = "255.255.255.0"
        self._gateway = "192.168.0.1"
        self._dns     = "8.8.8.8"

        self._read_interfaces()
        self.content.add(self._build_layout())

    def _read_interfaces(self):
        path = INTERFACES_FILE if os.path.exists(INTERFACES_FILE) else INTERFACES_DEFAULT
        try:
            with open(path, "r") as f:
                content = f.read()
        except Exception as e:
            logging.error("networkcfg: lecture interfaces : %s", e)
            return

        m = re.search(r"hwaddress ether\s+([\da-fA-F:]+)", content)
        if m:
            self._mac = m.group(1)
        m = re.search(r"iface\s+(\w+)\s+inet", content)
        if m:
            self._iface = m.group(1)
        self._is_dhcp = "inet dhcp" in content
        m = re.search(r"address\s+([\d.]+)", content)
        if m:
            self._address = m.group(1)
        m = re.search(r"netmask\s+([\d.]+)", content)
        if m:
            self._netmask = m.group(1)
        m = re.search(r"gateway\s+([\d.]+)", content)
        if m:
            self._gateway = m.group(1)
        m = re.search(r"dns-nameservers\s+([\d.]+)", content)
        if m:
            self._dns = m.group(1)

    def _build_layout(self):
        # Container scrollable vertical - horizontal bloque
        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        # === IP courante + toggle sur une ligne ===
        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.labels["current_ip"] = Gtk.Label()
        self.labels["current_ip"].set_markup(
            "<span size='xx-large' weight='bold'>" + _get_local_ip() + "</span>"
            + "  <span size='small'>(" + self._iface + ")</span>"
        )
        self.labels["current_ip"].set_halign(Gtk.Align.START)
        top_box.pack_start(self.labels["current_ip"], False, False, 0)

        # Spacer
        top_box.pack_start(Gtk.Label(label=""), True, True, 0)

        # Toggle DHCP / STATIC
        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toggle_box.set_valign(Gtk.Align.CENTER)
        toggle_box.pack_start(Gtk.Label(label="DHCP"),   False, False, 0)
        self.labels["toggle"] = Gtk.Switch()
        self.labels["toggle"].set_active(not self._is_dhcp)
        self.labels["toggle"].set_valign(Gtk.Align.CENTER)
        self.labels["toggle"].connect("notify::active", self._on_toggle)
        toggle_box.pack_start(self.labels["toggle"],     False, False, 0)
        toggle_box.pack_start(Gtk.Label(label="STATIC"), False, False, 0)
        top_box.pack_start(toggle_box, False, False, 0)

        main_box.pack_start(top_box, False, False, 0)
        main_box.pack_start(Gtk.Separator(), False, False, 0)

        # === Champs IP en colonne unique ===
        fields = [
            ("address", "Adresse IP", self._address),
            ("netmask", "Masque",     self._netmask),
            ("gateway", "Passerelle", self._gateway),
            ("dns",     "DNS",        self._dns),
        ]

        for key, label_text, default_val in fields:
            lbl = Gtk.Label()
            lbl.set_markup("<b>" + label_text + "</b>")
            lbl.set_halign(Gtk.Align.START)

            ip_widget = IpWidget(ip=default_val)
            self.labels["ip_" + key] = ip_widget

            field_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            field_box.pack_start(lbl,       False, False, 0)
            field_box.pack_start(ip_widget, False, False, 0)
            main_box.pack_start(field_box, False, False, 4)

        self._update_fields_sensitivity()

        main_box.pack_start(Gtk.Separator(), False, False, 0)

        # === Boutons ===
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        btn_reset = self._gtk.Button("refresh", "Defaut en DHCP", "color1")
        btn_reset.connect("clicked", self._on_reset)
        btn_reset.set_hexpand(True)

        btn_save = self._gtk.Button("complete", "Sauvegarder", "color3")
        btn_save.connect("clicked", self._on_save)
        btn_save.set_hexpand(True)

        btn_box.pack_start(btn_reset, True, True, 0)
        btn_box.pack_start(btn_save,  True, True, 0)
        main_box.pack_start(btn_box, False, False, 0)

        scroll.add(main_box)
        return scroll

    def _on_toggle(self, switch, gparam):
        self._is_dhcp = not switch.get_active()
        self._update_fields_sensitivity()

    def _update_fields_sensitivity(self):
        sensitive = not self._is_dhcp
        for key in ("address", "netmask", "gateway", "dns"):
            self.labels["ip_" + key].set_sensitive(sensitive)

    def _on_reset(self, widget):
        lbl = Gtk.Label()
        lbl.set_text("Reinitialiser en DHCP et sauvegarder ?")
        self._gtk.Dialog(
            "Reset reseau",
            [
                {"name": _("Annuler"),   "response": Gtk.ResponseType.CANCEL},
                {"name": _("Confirmer"), "response": Gtk.ResponseType.OK, "style": "color1"},
            ],
            lbl, self._confirm_reset,
        )

    def _confirm_reset(self, dialog, response):
        self._gtk.remove_dialog(dialog)
        if response == Gtk.ResponseType.OK:
            self.labels["toggle"].set_active(False)
            self._is_dhcp = True
            self._update_fields_sensitivity()
            self._write_interfaces(dhcp=True)

    def _on_save(self, widget):
        if self._is_dhcp:
            self._write_interfaces(dhcp=True)
        else:
            self._write_interfaces(
                dhcp=False,
                address=self.labels["ip_address"].get_ip(),
                netmask=self.labels["ip_netmask"].get_ip(),
                gateway=self.labels["ip_gateway"].get_ip(),
                dns=self.labels["ip_dns"].get_ip(),
            )

    def _write_interfaces(self, dhcp=True, address="", netmask="", gateway="", dns=""):
        if dhcp:
            content = DHCP_TEMPLATE.format(iface=self._iface, mac=self._mac)
        else:
            content = STATIC_TEMPLATE.format(
                iface=self._iface, mac=self._mac,
                address=address, netmask=netmask,
                gateway=gateway, dns=dns,
            )

        def _do_write():
            try:
                for path in (INTERFACES_FILE, INTERFACES_DEFAULT):
                    r = subprocess.run(
                        ["sudo", "tee", path],
                        input=content.encode("utf-8"),
                        capture_output=True,
                    )
                    if r.returncode != 0:
                        raise Exception("tee %s : %s" % (path, r.stderr.decode()))
                GLib.idle_add(self._on_write_done, True, "")
            except Exception as e:
                logging.error("networkcfg: ecriture : %s", e)
                GLib.idle_add(self._on_write_done, False, str(e))

        threading.Thread(target=_do_write, daemon=True).start()

    def _on_write_done(self, success, error_msg):
        if success:
            self.labels["current_ip"].set_markup(
                "<span size='xx-large' weight='bold'>" + _get_local_ip() + "</span>"
                + "  <span size='small'>(" + self._iface + ")</span>"
            )
            lbl = Gtk.Label()
            lbl.set_text("Configuration sauvegardee.\nRedemarrez la machine pour l'appliquer.")
            self._gtk.Dialog(
                "Reseau",
                [{"name": _("OK"), "response": Gtk.ResponseType.OK, "style": "color3"}],
                lbl, lambda d, r: self._gtk.remove_dialog(d),
            )
        else:
            lbl = Gtk.Label()
            lbl.set_text("Erreur ecriture :\n" + error_msg)
            self._gtk.Dialog(
                "Erreur",
                [{"name": _("OK"), "response": Gtk.ResponseType.OK, "style": "color1"}],
                lbl, lambda d, r: self._gtk.remove_dialog(d),
            )
        return False
