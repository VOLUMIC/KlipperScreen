import logging
import os
import re
import subprocess
import threading
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from ks_includes.screen_panel import ScreenPanel
from ks_includes.vyper_i18n import _v  # VOLUMIC MODIF : textes VOLUMIC traduits

INTERFACES_FILE    = "/etc/network/interfaces"
INTERFACES_DEFAULT = "/etc/network/interfaces.default"


def _get_iface_ip(iface):
    try:
        out = subprocess.check_output(
            ["ip", "-4", "addr", "show", iface],
            stderr=subprocess.DEVNULL
        ).decode("utf-8", errors="replace")
        m = re.search(r"inet\s+([\d.]+)", out)
        return m.group(1) if m else None
    except Exception:
        return None


def _netmask_to_prefix(netmask):
    try:
        return str(sum(bin(int(x)).count('1') for x in netmask.split('.')))
    except Exception:
        return "24"


def _prefix_to_netmask(prefix):
    try:
        p = int(prefix)
        mask = (0xFFFFFFFF >> (32 - p)) << (32 - p)
        return ".".join([str((mask >> (8 * i)) & 0xFF) for i in range(3, -1, -1)])
    except Exception:
        return "255.255.255.0"


class OctetSpin(Gtk.Box):
    _css_loaded = False

    def __init__(self, value=0):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._value = max(0, min(255, int(value)))

        if not OctetSpin._css_loaded:
            self._apply_css()
            OctetSpin._css_loaded = True

        self._btn_dn = Gtk.Button(label="-")
        self._btn_dn.set_relief(Gtk.ReliefStyle.NONE)
        self._btn_dn.connect("clicked", self._decrement)
        self._btn_dn.get_style_context().add_class("octet-btn")

        self._lbl = Gtk.Label()
        self._lbl.set_width_chars(3)
        self._lbl.set_xalign(0.5)
        self._lbl.get_style_context().add_class("octet-lbl")
        self._update()

        self._btn_up = Gtk.Button(label="+")
        self._btn_up.set_relief(Gtk.ReliefStyle.NONE)
        self._btn_up.connect("clicked", self._increment)
        self._btn_up.get_style_context().add_class("octet-btn")

        self.pack_start(self._btn_dn, False, False, 0)
        self.pack_start(self._lbl,    True,  True,  0)
        self.pack_start(self._btn_up, False, False, 0)
        self.get_style_context().add_class("octet-cell")

    def _apply_css(self):
        css = b"""
        .octet-cell {
            border: 1px solid #96FF00;
            background-color: #111111;
        }
        .octet-btn {
            background-color: #96FF00;
            color: #000000;
            border-radius: 0;
            padding: 10px 8px;
            min-width: 32px;
            min-height: 48px;
            font-weight: bold;
            font-size: 20px;
            border: none;
            -gtk-icon-shadow: none;
            text-shadow: none;
        }
        .octet-btn:hover { background-color: #7ACC00; }
        .octet-btn:active { background-color: #5E9900; }
        .octet-btn:disabled { background-color: #333333; color: #555555; }
        .octet-lbl {
            color: #96FF00;
            font-size: 18px;
            font-weight: bold;
            background-color: transparent;
        }
        .octet-lbl:disabled { color: #444444; }
        """
        from gi.repository import Gdk
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _update(self):
        self._lbl.set_text(str(self._value))

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
    def __init__(self, ip="0.0.0.0"):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        parts = (ip or "0.0.0.0").split(".")
        if len(parts) != 4:
            parts = ["0", "0", "0", "0"]
        self._octets = []
        for i, p in enumerate(parts):
            spin = OctetSpin(value=int(p) if p.isdigit() else 0)
            self._octets.append(spin)
            self.pack_start(spin, True, True, 0)
            if i < 3:
                sep = Gtk.Label()
                sep.set_markup("<span size='large' weight='bold' foreground='#96FF00'>.</span>")
                self.pack_start(sep, False, False, 2)

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
        title = title or _v("Network")
        super().__init__(screen, title)
        self.labels = {}

        # ETH0 - valeurs par defaut
        self._mac_eth0    = "00:00:00:00:00:00"
        self._eth_dhcp    = True
        self._eth_address = "192.168.0.30"
        self._eth_netmask = "255.255.255.0"
        self._eth_gateway = "192.168.0.1"
        self._eth_dns     = "8.8.8.8"

        # WLAN0 - valeurs par defaut
        self._wlan_conn   = None    # nom connexion NM active sur wlan0
        self._mac_wlan0   = "00:00:00:00:00:00"
        self._wlan_dhcp   = True
        self._wlan_address = "192.168.0.30"
        self._wlan_netmask = "255.255.255.0"
        self._wlan_gateway = "192.168.0.1"
        self._wlan_dns     = "8.8.8.8"
        self._wlan_connected = False  # False = section masquee

        self._read_eth0()
        self._read_wlan0()
        self.content.add(self._build_layout())

    # ------------------------------------------------------------------
    # Lecture ETH0 depuis /etc/network/interfaces
    # ------------------------------------------------------------------
    def _read_eth0(self):
        path = INTERFACES_FILE if os.path.exists(INTERFACES_FILE) else INTERFACES_DEFAULT
        try:
            with open(path, "r") as f:
                content = f.read()
        except Exception as e:
            logging.error("networkcfg: lecture interfaces : %s", e)
            return

        blocks = re.split(r'(?=^iface\s)', content, flags=re.MULTILINE)
        for block in blocks:
            if not re.match(r"iface\s+eth", block):
                continue
            mac_m = re.search(r"hwaddress ether\s+([\da-fA-F:]+)", block)
            if mac_m:
                self._mac_eth0 = mac_m.group(1)
            self._eth_dhcp = "inet dhcp" in block
            m = re.search(r"address\s+([\d.]+)", block)
            if m: self._eth_address = m.group(1)
            m = re.search(r"netmask\s+([\d.]+)", block)
            if m: self._eth_netmask = m.group(1)
            m = re.search(r"gateway\s+([\d.]+)", block)
            if m: self._eth_gateway = m.group(1)
            m = re.search(r"dns-nameservers\s+([\d.]+)", block)
            if m: self._eth_dns = m.group(1)

    # ------------------------------------------------------------------
    # Lecture WLAN0 depuis NetworkManager (nmcli)
    # ------------------------------------------------------------------
    def _read_wlan0(self):
        # MAC wlan0 depuis ip link
        try:
            out = subprocess.check_output(
                ["ip", "link", "show", "wlan0"],
                stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="replace")
            m = re.search(r"link/ether\s+([\da-fA-F:]+)", out)
            if m:
                self._mac_wlan0 = m.group(1)
        except Exception:
            pass

        # Connexion NM active sur wlan0
        try:
            out = subprocess.check_output(
                ["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"],
                stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="replace")
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) >= 2 and parts[1].strip() == "wlan0":
                    self._wlan_conn = parts[0].strip()
                    self._wlan_connected = True
                    break
        except Exception as e:
            logging.warning("networkcfg: nmcli active : %s", e)
            return

        if not self._wlan_conn:
            return

        # Lire la config IPv4 de la connexion active
        try:
            out = subprocess.check_output(
                ["nmcli", "-t", "-f",
                 "ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns",
                 "connection", "show", self._wlan_conn],
                stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="replace")
            for line in out.splitlines():
                if line.startswith("ipv4.method:"):
                    self._wlan_dhcp = "auto" in line
                elif line.startswith("ipv4.addresses:"):
                    val = line.split(":", 1)[-1].strip()
                    if val and val != "--" and "/" in val:
                        addr, prefix = val.split("/", 1)
                        self._wlan_address = addr.strip()
                        self._wlan_netmask = _prefix_to_netmask(prefix.strip())
                elif line.startswith("ipv4.gateway:"):
                    val = line.split(":", 1)[-1].strip()
                    if val and val != "--":
                        self._wlan_gateway = val
                elif line.startswith("ipv4.dns:"):
                    val = line.split(":", 1)[-1].strip()
                    if val and val != "--":
                        self._wlan_dns = val.split(",")[0].strip()
        except Exception as e:
            logging.warning("networkcfg: nmcli config : %s", e)

    # ------------------------------------------------------------------
    # Construction du layout
    # ------------------------------------------------------------------
    def _build_iface_section(self, main_box, iface_name, ip_current,
                              is_dhcp, field_defaults):
        hdr_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        iface_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        lbl_iface = Gtk.Label()
        display_name = "Ethernet" if iface_name == "eth0" else "WiFi"
        lbl_iface.set_markup(
            "<span size='x-large' weight='bold'>" + display_name + "</span>"
        )
        lbl_iface.set_halign(Gtk.Align.START)
        lbl_ip = Gtk.Label()
        lbl_ip.set_markup(
            "<span size='large' weight='bold'>" + (ip_current or _v("Not connected")) + "</span>"
        )
        lbl_ip.set_halign(Gtk.Align.START)
        self.labels[iface_name + "_ip"] = lbl_ip
        iface_box.pack_start(lbl_iface, False, False, 0)
        iface_box.pack_start(lbl_ip,    False, False, 0)
        hdr_box.pack_start(iface_box, True, True, 0)

        toggle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toggle_box.set_valign(Gtk.Align.CENTER)
        toggle_box.pack_start(Gtk.Label(label="Auto"),  False, False, 0)
        toggle = Gtk.Switch()
        toggle.set_active(not is_dhcp)
        toggle.set_valign(Gtk.Align.CENTER)
        self.labels[iface_name + "_toggle"] = toggle
        toggle_box.pack_start(toggle,                   False, False, 0)
        toggle_box.pack_start(Gtk.Label(label="Fixe"),  False, False, 0)
        hdr_box.pack_start(toggle_box, False, False, 0)

        main_box.pack_start(hdr_box, False, False, 0)

        # Conteneur des champs IP - masque en mode DHCP
        fields_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.labels[iface_name + "_fields_box"] = fields_box

        fields = [
            ("address", _v("IP address"), field_defaults.get("address", "0.0.0.0")),
            ("netmask", _v("Netmask"),   field_defaults.get("netmask", "255.255.255.0")),
            ("gateway", _v("Gateway"), field_defaults.get("gateway", "0.0.0.0")),
            ("dns",     "DNS",        field_defaults.get("dns",     "8.8.8.8")),
        ]
        for key, label_text, default_val in fields:
            lbl = Gtk.Label()
            lbl.set_markup("<b>" + label_text + "</b>")
            lbl.set_halign(Gtk.Align.START)
            ip_widget = IpWidget(ip=default_val)
            self.labels[iface_name + "_ip_" + key] = ip_widget
            field_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            field_box.pack_start(lbl,       False, False, 0)
            field_box.pack_start(ip_widget, False, False, 0)
            fields_box.pack_start(field_box, False, False, 0)

        main_box.pack_start(fields_box, False, False, 0)

        toggle.connect("notify::active", self._on_toggle, iface_name)
        self._update_iface_sensitivity(iface_name, is_dhcp)

        # Appliquer la visibilite initiale apres que KlipperScreen ait fait show_all
        if is_dhcp:
            from gi.repository import GLib
            GLib.idle_add(fields_box.hide)

    def _build_layout(self):
        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        # Section ETH0
        self._build_iface_section(
            main_box, "eth0",
            ip_current=_get_iface_ip("eth0"),
            is_dhcp=self._eth_dhcp,
            field_defaults={
                "address": self._eth_address,
                "netmask": self._eth_netmask,
                "gateway": self._eth_gateway,
                "dns":     self._eth_dns,
            }
        )

        # Section WLAN0 - affichee seulement si connecte
        if self._wlan_connected:
            sep = Gtk.Separator()
            sep.set_margin_top(4)
            sep.set_margin_bottom(4)
            main_box.pack_start(sep, False, False, 0)

            self._build_iface_section(
                main_box, "wlan0",
                ip_current=_get_iface_ip("wlan0"),
                is_dhcp=self._wlan_dhcp,
                field_defaults={
                    "address": self._wlan_address,
                    "netmask": self._wlan_netmask,
                    "gateway": self._wlan_gateway,
                    "dns":     self._wlan_dns,
                }
            )

        main_box.pack_start(Gtk.Separator(), False, False, 2)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_reset = self._gtk.Button("refresh", _v("Reset to DHCP"), "color1")
        btn_reset.connect("clicked", self._on_reset)
        btn_reset.set_hexpand(True)
        btn_save = self._gtk.Button("complete", _v("Save"), "color3")
        btn_save.connect("clicked", self._on_save)
        btn_save.set_hexpand(True)
        btn_box.pack_start(btn_reset, True, True, 0)
        btn_box.pack_start(btn_save,  True, True, 0)
        main_box.pack_start(btn_box, False, False, 0)

        scroll.add(main_box)
        return scroll

    def _on_toggle(self, switch, gparam, iface_name):
        is_dhcp = not switch.get_active()
        self._update_iface_sensitivity(iface_name, is_dhcp)
        fields_box = self.labels.get(iface_name + "_fields_box")
        if fields_box:
            if is_dhcp:
                fields_box.hide()
            else:
                fields_box.show_all()

    def _update_iface_sensitivity(self, iface_name, is_dhcp):
        sensitive = not is_dhcp
        for key in ("address", "netmask", "gateway", "dns"):
            lbl_key = iface_name + "_ip_" + key
            if lbl_key in self.labels:
                self.labels[lbl_key].set_sensitive(sensitive)

    def _centered_content(self, text):
        """Cree un widget avec texte centre horizontalement et verticalement."""
        lbl = Gtk.Label()
        lbl.set_text(text)
        lbl.set_justify(Gtk.Justification.CENTER)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.set_vexpand(True)
        box.set_hexpand(True)
        box.pack_start(lbl, True, True, 0)
        return box

    # ------------------------------------------------------------------
    # Reset et sauvegarde
    # ------------------------------------------------------------------
    def _on_reset(self, widget):
        self._gtk.Dialog(
            _v("Network reset"),
            [
                {"name": _("Cancel"),   "response": Gtk.ResponseType.CANCEL},
                {"name": _v("Confirm"), "response": Gtk.ResponseType.OK, "style": "color1"},
            ],
            self._centered_content(_v("Reset all interfaces to DHCP?")),
            self._confirm_reset,
        )

    def _confirm_reset(self, dialog, response):
        self._gtk.remove_dialog(dialog)
        if response != Gtk.ResponseType.OK:
            return
        self.labels["eth0_toggle"].set_active(False)
        self._update_iface_sensitivity("eth0", True)
        if self._wlan_connected and "wlan0_toggle" in self.labels:
            self.labels["wlan0_toggle"].set_active(False)
            self._update_iface_sensitivity("wlan0", True)
        self._save(eth_dhcp=True, wlan_dhcp=True)

    def _on_save(self, widget):
        # Dialog immediat "en cours" pendant l'ecriture
        self._wait_dialog = self._gtk.Dialog(
            _v("Network"),
            None,
            self._centered_content(_v("Applying the configuration...")),
            lambda *a: None,
        )

        eth_dhcp  = not self.labels["eth0_toggle"].get_active()
        wlan_dhcp = not self.labels.get("wlan0_toggle", Gtk.Switch()).get_active() \
                    if self._wlan_connected else True
        self._save(
            eth_dhcp=eth_dhcp,
            eth_address=self.labels["eth0_ip_address"].get_ip(),
            eth_netmask=self.labels["eth0_ip_netmask"].get_ip(),
            eth_gateway=self.labels["eth0_ip_gateway"].get_ip(),
            eth_dns=self.labels["eth0_ip_dns"].get_ip(),
            wlan_dhcp=wlan_dhcp,
            wlan_address=self.labels.get("wlan0_ip_address", IpWidget()).get_ip() if self._wlan_connected else "",
            wlan_netmask=self.labels.get("wlan0_ip_netmask", IpWidget()).get_ip() if self._wlan_connected else "",
            wlan_gateway=self.labels.get("wlan0_ip_gateway", IpWidget()).get_ip() if self._wlan_connected else "",
            wlan_dns=self.labels.get("wlan0_ip_dns",     IpWidget()).get_ip() if self._wlan_connected else "",
        )

    # ------------------------------------------------------------------
    # Ecriture
    # ------------------------------------------------------------------
    def _save(self,
              eth_dhcp=True,  eth_address="", eth_netmask="",
              eth_gateway="", eth_dns="",
              wlan_dhcp=True, wlan_address="", wlan_netmask="",
              wlan_gateway="", wlan_dns=""):

        # Contenu pour interfaces (eth0 uniquement)
        if eth_dhcp:
            eth_block = (
                "auto eth0\n"
                "iface eth0 inet dhcp\n"
                "        hwaddress ether " + self._mac_eth0 + "\n"
            )
        else:
            eth_block = (
                "auto eth0\n"
                "iface eth0 inet static\n"
                "    hwaddress ether " + self._mac_eth0 + "\n"
                "    address " + eth_address + "\n"
                "    netmask " + eth_netmask + "\n"
                "    gateway " + eth_gateway + "\n"
                "    dns-nameservers " + eth_dns + "\n"
            )

        interfaces_content = (
            "source /etc/network/interfaces.d/*\n"
            "# Network is managed by Network manager\n"
            "auto lo\n"
            "iface lo inet loopback\n\n"
            + eth_block
        )

        wlan_conn = self._wlan_conn

        def _do_write():
            errors = []

            # Ecrire interfaces pour eth0
            try:
                r = subprocess.run(
                    ["sudo", "tee", INTERFACES_FILE],
                    input=interfaces_content.encode("utf-8"),
                    capture_output=True,
                )
                if r.returncode != 0:
                    errors.append("interfaces: " + r.stderr.decode())
            except Exception as e:
                errors.append("interfaces: " + str(e))

            # Configurer wlan0 via nmcli si connecte
            if wlan_conn:
                try:
                    if wlan_dhcp:
                        cmd = ["sudo", "nmcli", "connection", "modify", wlan_conn,
                               "ipv4.method", "auto",
                               "ipv4.addresses", "",
                               "ipv4.gateway",   "",
                               "ipv4.dns",       ""]
                    else:
                        prefix = _netmask_to_prefix(wlan_netmask)
                        cmd = ["sudo", "nmcli", "connection", "modify", wlan_conn,
                               "ipv4.method",    "manual",
                               "ipv4.addresses", wlan_address + "/" + prefix,
                               "ipv4.gateway",   wlan_gateway,
                               "ipv4.dns",       wlan_dns]
                    r = subprocess.run(cmd, capture_output=True)
                    if r.returncode != 0:
                        errors.append("nmcli modify: " + r.stderr.decode())
                    else:
                        # Reappliquer la connexion pour prise en compte immediate
                        subprocess.run(
                            ["sudo", "nmcli", "connection", "up", wlan_conn],
                            capture_output=True,
                        )
                except Exception as e:
                    errors.append("nmcli: " + str(e))

            if errors:
                GLib.idle_add(self._on_write_done, False, "\n".join(errors))
            else:
                GLib.idle_add(self._on_write_done, True, "")

        threading.Thread(target=_do_write, daemon=True).start()

    def _on_write_done(self, success, error_msg):
        # Fermer le dialog d'attente
        if hasattr(self, "_wait_dialog") and self._wait_dialog:
            self._gtk.remove_dialog(self._wait_dialog)
            self._wait_dialog = None
        if success:
            if "eth0_ip" in self.labels:
                ip = _get_iface_ip("eth0")
                self.labels["eth0_ip"].set_markup(
                    "<span size='large' weight='bold'>" + (ip or _v("Not connected")) + "</span>"
                )
            if "wlan0_ip" in self.labels:
                ip = _get_iface_ip("wlan0")
                self.labels["wlan0_ip"].set_markup(
                    "<span size='large' weight='bold'>" + (ip or _v("Not connected")) + "</span>"
                )
            self._gtk.Dialog(
                _v("Network"),
                [{"name": _("OK"), "response": Gtk.ResponseType.OK, "style": "color3"}],
                self._centered_content(_v("Configuration saved.\nThe machine will restart to apply it.")),
                self._on_reboot_confirm,
            )
        else:
            self._gtk.Dialog(
                _("Error"),
                [{"name": _("OK"), "response": Gtk.ResponseType.OK, "style": "color1"}],
                self._centered_content(_v("Error:") + "\n" + error_msg),
                lambda d, r: self._gtk.remove_dialog(d),
            )
        return False

    def _on_reboot_confirm(self, dialog, response):
        self._gtk.remove_dialog(dialog)
        subprocess.Popen(
            ["sudo", "reboot"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )