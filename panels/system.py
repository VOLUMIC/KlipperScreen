import logging
import os
import subprocess
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel
from ks_includes.vyper_i18n import _v  # VOLUMIC MODIF : textes VOLUMIC traduits


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("System")
        super().__init__(screen, title)
        self.current_row = 0
        self.mem_multiplier = None
        self.scales = {}
        self.labels = {}
        self.grid = Gtk.Grid(column_spacing=10, row_spacing=5)

        self.sysinfo = screen.printer.system_info
        if not self.sysinfo:
            logging.debug("Asking for info")
            self.sysinfo = screen.apiclient.send_request("machine/system_info")
            if 'system_info' in self.sysinfo:
                screen.printer.system_info = self.sysinfo['system_info']
                self.sysinfo = self.sysinfo['system_info']
        logging.debug(self.sysinfo)
        if self.sysinfo:
            self.content.add(self.create_layout())
        else:
            self.content.add(Gtk.Label(label=_("No info available"), vexpand=True))

    def back(self):
        if not self.sysinfo:
            self._screen.panels_reinit.append("system")
        return False

    def create_layout(self):
        self.cpu_count = int(self.sysinfo["cpu_info"]["cpu_count"])

        # CSS pour forcer la hauteur des ProgressBar - set_size_request ne suffit pas
        from gi.repository import Gdk
        css = b"""
        progressbar.slim-bar { min-height: 6px; }
        progressbar.slim-bar trough { min-height: 6px; }
        progressbar.slim-bar progress { min-height: 6px; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        # CPU global
        self.labels["cpu_usage"] = Gtk.Label(label="", xalign=0)
        self.grid.attach(self.labels["cpu_usage"], 0, self.current_row, 1, 1)
        self.scales["cpu_usage"] = Gtk.ProgressBar(hexpand=True, show_text=False, fraction=0)
        self.scales["cpu_usage"].get_style_context().add_class("slim-bar")
        self.grid.attach(self.scales["cpu_usage"], 1, self.current_row, 1, 1)
        self.current_row += 1

        # CPU par coeur
        for i in range(self.cpu_count):
            self.labels[f"cpu_usage_{i}"] = Gtk.Label(label="", xalign=0)
            self.grid.attach(self.labels[f"cpu_usage_{i}"], 0, self.current_row, 1, 1)
            self.scales[f"cpu_usage_{i}"] = Gtk.ProgressBar(hexpand=True, show_text=False, fraction=0)
            self.scales[f"cpu_usage_{i}"].get_style_context().add_class("slim-bar")
            self.grid.attach(self.scales[f"cpu_usage_{i}"], 1, self.current_row, 1, 1)
            self.current_row += 1

        # Memoire
        self.labels["memory_usage"] = Gtk.Label(label="", xalign=0)
        self.grid.attach(self.labels["memory_usage"], 0, self.current_row, 1, 1)
        self.scales["memory_usage"] = Gtk.ProgressBar(hexpand=True, show_text=False, fraction=0)
        self.scales["memory_usage"].get_style_context().add_class("slim-bar")
        self.grid.attach(self.scales["memory_usage"], 1, self.current_row, 1, 1)
        self.current_row += 1

        # Fuseau horaire
        self._build_timezone_row()

        # Bouton reset reseau
        btn_reset = self._gtk.Button("network", _v("RESET NETWORK"), "color1")
        btn_reset.connect("clicked", self._on_reset_network)
        self.grid.attach(btn_reset, 0, self.current_row, 2, 1)
        self.current_row += 1

        scroll = self._gtk.ScrolledWindow()
        scroll.add(self.grid)
        return scroll

    def _build_timezone_row(self):
        """Liste les timezones et permet de changer en temps reel."""
        import subprocess as _sp

        # Recuperer la timezone courante
        try:
            current_tz = _sp.check_output(
                ["timedatectl", "show", "--property=Timezone", "--value"],
                stderr=_sp.DEVNULL
            ).decode().strip()
        except Exception:
            current_tz = "UTC"

        # Recuperer la liste des timezones
        try:
            tz_list = _sp.check_output(
                ["timedatectl", "list-timezones"],
                stderr=_sp.DEVNULL
            ).decode().strip().splitlines()
        except Exception:
            tz_list = ["UTC"]

        # Label
        lbl = Gtk.Label(label="Fuseau horaire", xalign=0)
        lbl.set_markup("<b>" + _v("Time zone") + "</b>")
        self.grid.attach(lbl, 0, self.current_row, 1, 1)

        # Label timezone actuelle
        self.labels["current_tz"] = Gtk.Label(xalign=0)
        self.labels["current_tz"].set_markup(
            "<span foreground='#96FF00'>" + current_tz + "</span>"
        )
        self.grid.attach(self.labels["current_tz"], 1, self.current_row, 1, 1)
        self.current_row += 1

        # ComboBox avec liste des timezones
        tz_store = Gtk.ListStore(str)
        current_index = 0
        for i, tz in enumerate(tz_list):
            tz_store.append([tz])
            if tz == current_tz:
                current_index = i

        combo = Gtk.ComboBox.new_with_model(tz_store)
        renderer = Gtk.CellRendererText()
        combo.pack_start(renderer, True)
        combo.add_attribute(renderer, "text", 0)
        combo.set_active(current_index)
        combo.connect("changed", self._on_tz_changed, tz_list)
        self.labels["tz_combo"] = combo

        self.grid.attach(combo, 0, self.current_row, 2, 1)
        self.current_row += 1

    def _on_tz_changed(self, combo, tz_list):
        idx = combo.get_active()
        if idx < 0 or idx >= len(tz_list):
            return
        tz = tz_list[idx]

        lbl = Gtk.Label()
        lbl.set_text(
            _v("Set the time zone to:") + "\n\n"
            + tz
            + "\n\n" + _v("The machine must restart to apply the changes.")
        )
        self._gtk.Dialog(
            _v("Time zone"),
            [
                {"name": _("Cancel"), "response": Gtk.ResponseType.CANCEL},
                {"name": _("OK"),      "response": Gtk.ResponseType.OK, "style": "color3"},
            ],
            lbl,
            self._confirm_tz_change,
            tz,
        )

    def _confirm_tz_change(self, dialog, response, tz):
        self._gtk.remove_dialog(dialog)
        if response != Gtk.ResponseType.OK:
            return
        try:
            result = subprocess.run(
                ["sudo", "timedatectl", "set-timezone", tz],
                capture_output=True,
            )
            if result.returncode == 0:
                logging.info(f"system: timezone changee en {tz}")
                self.labels["current_tz"].set_markup(
                    "<span foreground='#96FF00'>" + tz + "</span>"
                )
                subprocess.Popen(
                    ["sudo", "reboot"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                logging.error(f"system: echec timezone : {result.stderr.decode()}")
                lbl_err = Gtk.Label()
                lbl_err.set_text(_v("Error while changing the time zone:") + "\n" + result.stderr.decode())
                self._gtk.Dialog(
                    _("Error"),
                    [{"name": _("OK"), "response": Gtk.ResponseType.OK, "style": "color1"}],
                    lbl_err, lambda d, r: self._gtk.remove_dialog(d),
                )
        except Exception as e:
            logging.error(f"system: timezone exception : {e}")

    def set_mem_multiplier(self, data):
        memory_units = data.get("memory_units", "kB").lower()
        units_mapping = {
            "kb": 1024,
            "mb": 1024**2,
            "gb": 1024**3,
            "tb": 1024**4,
            "pb": 1024**5,
        }
        self.mem_multiplier = units_mapping.get(memory_units, 1)

    def add_label_to_grid(self, text, column, bold=False):
        if bold:
            text = f"<b>{text}</b>"
        label = Gtk.Label(label=text, use_markup=True, xalign=0, wrap=True)
        self.grid.attach(label, column, self.current_row, 1, 1)
        self.current_row += 1

    def populate_info(self):
        # Categories a afficher - on exclut python, sd_info et tout le reste
        ALLOWED = ("network_info",)

        for category, data in self.sysinfo.items():
            if category not in ALLOWED:
                continue
            if not self.sysinfo[category]:
                continue

            self.add_label_to_grid(self.prettify(category), 0, bold=True)

            if isinstance(data, dict):
                for key, value in data.items():
                    if key in ("version_parts", "memory_units") or not value:
                        continue
                    if key == "total_memory":
                        if not self.mem_multiplier:
                            self.set_mem_multiplier(data)
                        value = self.format_size(int(value) * self.mem_multiplier)
                    if isinstance(value, dict):
                        self.add_label_to_grid(self.prettify(key), 0)
                        self.current_row -= 1
                        for sub_key, sub_value in value.items():
                            if not sub_value:
                                continue
                            elif (
                                isinstance(sub_value, list)
                                and sub_key == "ip_addresses"
                            ):
                                for _ip in sub_value:
                                    self.add_label_to_grid(
                                        f"{self.prettify(sub_key)}: {_ip['address']}", 1
                                    )
                                continue
                            self.add_label_to_grid(
                                f"{self.prettify(sub_key)}: {sub_value}", 1
                            )
                    else:
                        self.add_label_to_grid(f"{self.prettify(key)}: {value}", 1)

    def _on_reset_network(self, widget):
        lbl = Gtk.Label()
        lbl.set_text(
            _v("Reset the network to DHCP?\n\nThe machine will restart after the reset.\nAll connections will be cut.")
        )
        self._gtk.Dialog(
            _v("RESET NETWORK"),
            [
                {"name": _("Cancel"),   "response": Gtk.ResponseType.CANCEL},
                {"name": _v("Confirm"), "response": Gtk.ResponseType.OK, "style": "color1"},
            ],
            lbl,
            self._confirm_reset_network,
        )

    def _confirm_reset_network(self, dialog, response):
        self._gtk.remove_dialog(dialog)
        if response == Gtk.ResponseType.OK:
            script = os.path.join(
                os.path.expanduser("~"), "VyperOS", "resetnetwork.sh"
            )
            try:
                subprocess.Popen(
                    ["sudo", "bash", script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                logging.error("reset_network: %s", e)

    def process_update(self, action, data):
        if not self.sysinfo:
            return
        if action == "notify_proc_stat_update":
            self.labels["cpu_usage"].set_label(
                f'CPU: {data["system_cpu_usage"]["cpu"]:.0f}%'
            )
            self.scales["cpu_usage"].set_fraction(
                float(data["system_cpu_usage"]["cpu"]) / 100
            )
            for i in range(self.cpu_count):
                self.labels[f"cpu_usage_{i}"].set_label(
                    f'CPU {i}: {data["system_cpu_usage"][f"cpu{i}"]:.0f}%'
                )
                self.scales[f"cpu_usage_{i}"].set_fraction(
                    float(data["system_cpu_usage"][f"cpu{i}"]) / 100
                )

            self.labels["memory_usage"].set_label(
                _("Memory")
                + f': {(data["system_memory"]["used"] / data["system_memory"]["total"]) * 100:.0f}%'
            )
            self.scales["memory_usage"].set_fraction(
                float(data["system_memory"]["used"])
                / float(data["system_memory"]["total"])
            )