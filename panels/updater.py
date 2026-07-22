import logging
import os
import subprocess
from gettext import ngettext

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or _("Update")
        super().__init__(screen, title)
        self.labels = {}
        self.update_status = None

        self.buttons = {
            "update_all": self._gtk.Button(
                image_name="arrow-up",
                label=_("Full Update"),
                style="color1",
                scale=self.bts * 0.8,
                position=Gtk.PositionType.LEFT,
                lines=2,
            ),
            "refresh": self._gtk.Button(
                image_name="arrow-down",
                label=_("Refresh"),
                style="color3",
                scale=self.bts * 0.8,
                position=Gtk.PositionType.LEFT,
                lines=2,
            ),
        }
        self.buttons["update_all"].connect("clicked", self.show_update_info, "full")
        self.buttons["update_all"].set_vexpand(False)
        self.buttons["refresh"].connect("clicked", self.refresh_updates)
        self.buttons["refresh"].set_vexpand(False)

        top_box = Gtk.Box(vexpand=False)
        top_box.pack_start(self.buttons["update_all"], True, True, 0)
        top_box.pack_start(self.buttons["refresh"], True, True, 0)

        self.update_msg = Gtk.Label(label=_("Checking for updates, please wait..."), vexpand=True)

        self.scroll = self._gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.add(self.update_msg)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        self.main_box.pack_start(top_box, False, False, 0)
        self.main_box.pack_start(self.scroll, True, True, 0)

        self.content.add(self.main_box)

        mcutype = 2
        try:
            section = self._printer.get_macro("VOLUMIC_Type")
            if "variable_mcutype" in section:
                mcutype = section["variable_mcutype"]
        except Exception as e:
            logging.exception(e)
        if mcutype == "0":
           os.system('mkdir /home/Volumic/VyperOS/SAM3X8E')
           os.system('rmdir /home/Volumic/VyperOS/STM32H723')
           os.system('rmdir /home/Volumic/VyperOS/STM32H723M8')
        elif mcutype == "1":
           os.system('mkdir /home/Volumic/VyperOS/SAM3X8E')
           os.system('rmdir /home/Volumic/VyperOS/STM32H723')
           os.system('rmdir /home/Volumic/VyperOS/STM32H723M8')
        elif mcutype == "3":
           os.system('rmdir /home/Volumic/VyperOS/SAM3X8E')
           os.system('rmdir /home/Volumic/VyperOS/STM32H723')
           os.system('mkdir /home/Volumic/VyperOS/STM32H723M8')
        else:
           os.system('rmdir /home/Volumic/VyperOS/SAM3X8E')
           os.system('rmdir /home/Volumic/VyperOS/STM32H723M8')
           os.system('mkdir /home/Volumic/VyperOS/STM32H723')

    def activate(self):
        self.clear_scroll()
        self.scroll.add(self.update_msg)
        self.update_msg.show()
        self.buttons["update_all"].set_sensitive(False)
        self.buttons["refresh"].set_sensitive(False)
        logging.info("Auto-refresh on activate")
        self._screen._ws.send_method(
            "machine.update.refresh", callback=self.get_updates
        )

    def create_info_grid(self):
        infogrid = Gtk.Grid()
        infogrid.get_style_context().add_class("system-program-grid")
        for i, prog in enumerate(sorted(list(self.update_status["version_info"]))):
            self.labels[prog] = Gtk.Label(hexpand=True, halign=Gtk.Align.START, ellipsize=Pango.EllipsizeMode.END)
            self.labels[prog].get_style_context().add_class("updater-item")

            self.labels[f"{prog}_status"] = Gtk.Label(hexpand=True, halign=Gtk.Align.START, ellipsize=Pango.EllipsizeMode.END)
            self.labels[f"{prog}_status"].get_style_context().add_class("updater-item")

            # Bouton "Mettre a jour" - desactive par defaut, active par _needs_update
            self.buttons[f"{prog}_update"] = self._gtk.Button(
                "arrow-up",
                _("Update"),
                "color1",
                position=Gtk.PositionType.LEFT,
                scale=self.bts,
            )
            self.buttons[f"{prog}_update"].set_sensitive(False)
            self.buttons[f"{prog}_update"].connect(
                "clicked", self._update_single, prog
            )
            infogrid.attach(self.buttons[f"{prog}_update"], 2, i, 1, 1)

            infogrid.attach(self.labels[prog], 0, i, 1, 1)
            infogrid.attach(self.labels[f"{prog}_status"], 1, i, 1, 1)
            self.update_program_info(prog)
        self.clear_scroll()
        self.scroll.add(infogrid)

    def clear_scroll(self):
        for child in self.scroll.get_children():
            self.scroll.remove(child)

    def refresh_updates(self, widget=None):
        self.clear_scroll()
        self.scroll.add(self.update_msg)
        self.buttons["update_all"].set_sensitive(False)
        self.buttons["refresh"].set_sensitive(False)
        self._gtk.Button_busy(widget, True)
        logging.info("Sending machine.update.refresh")
        self._screen._ws.send_method(
            "machine.update.refresh", callback=self.get_updates
        )

    def get_updates(self, response, method, params):
        self._gtk.Button_busy(self.buttons["refresh"], False)
        self.buttons["refresh"].set_sensitive(True)
        logging.info(response)
        if not response or "result" not in response:
            self.buttons["update_all"].set_sensitive(False)
            self.clear_scroll()
            if "error" in response:
                self.scroll.add(
                    Gtk.Label(
                        label=f"Moonraker: {response['error']['message']}", vexpand=True
                    )
                )
            else:
                self.scroll.add(
                    Gtk.Label(label=_("Not working or not configured"), vexpand=True)
                )
        else:
            self.update_status = response["result"]
            self.buttons["update_all"].set_sensitive(True)
            self.create_info_grid()
        self.scroll.show_all()

    def restart(self, widget, program):
        if self._printer.state in ("printing", "paused"):
            self._screen._confirm_send_action(
                widget,
                f'{_("Are you sure?")}\n\n' f'{_("Restart")}: {program}',
                "machine.services.restart",
                {"service": program},
            )
        else:
            self._screen._send_action(
                widget, "machine.services.restart", {"service": program}
            )

    # Mapping programme Moonraker -> script bash dans updater/
    UPDATE_SCRIPTS = {
        "klipper":          "update_klipper.sh",
        "moonraker":        "update_moonraker.sh",
        "KlipperScreen":    "update_klipperscreen.sh",
        "mainsail":         "update_mainsail.sh",
        "moonraker-obico":  "update_obico.sh",
        "system":           "update_system.sh",
        "configurations":   "update_configurations.sh",
    }
    SCRIPTS_DIR = "/home/Volumic/VyperOS"

    def _update_single(self, widget, program):
        script_name = self.UPDATE_SCRIPTS.get(program)
        if not script_name:
            logging.warning(f"updater: pas de script pour {program}")
            lbl = Gtk.Label()
            lbl.set_text(f"Aucun script defini pour :\n{program}")
            self._gtk.Dialog(
                "Info",
                [{"name": _("OK"), "response": Gtk.ResponseType.OK}],
                lbl, lambda d, r: self._gtk.remove_dialog(d),
            )
            return

        script_path = os.path.join(self.SCRIPTS_DIR, script_name)
        if not os.path.exists(script_path):
            logging.warning(f"updater: script introuvable : {script_path}")
            lbl = Gtk.Label()
            lbl.set_text(f"Script introuvable :\n{script_path}")
            self._gtk.Dialog(
                "Erreur",
                [{"name": _("OK"), "response": Gtk.ResponseType.OK, "style": "color1"}],
                lbl, lambda d, r: self._gtk.remove_dialog(d),
            )
            return

        lbl = Gtk.Label()
        lbl.set_text(f"\n\nMettre a jour {program} ?")
        self._gtk.Dialog(
            "Mise a jour",
            [
                {"name": _("Annuler"),   "response": Gtk.ResponseType.CANCEL},
                {"name": _("Confirmer"), "response": Gtk.ResponseType.OK, "style": "color1"},
            ],
            lbl,
            self._confirm_update_single,
            program,
            script_path,
        )

    def _confirm_update_single(self, dialog, response, program, script_path):
        self._gtk.remove_dialog(dialog)
        if response != Gtk.ResponseType.OK:
            return
        logging.info(f"updater: mise a jour {program} via {script_path}")

        # Afficher un spinner dans le scroll pendant la mise a jour
        # sans bloquer KlipperScreen (pas de show_update_dialog)
        spinner = Gtk.Spinner()
        spinner.set_size_request(48, 48)
        spinner.start()
        lbl = Gtk.Label()
        lbl.set_text(f"Mise a jour de {program} en cours...")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.pack_start(spinner, False, False, 0)
        box.pack_start(lbl,     False, False, 0)
        box.show_all()
        self.clear_scroll()
        self.scroll.add(box)
        self.scroll.show_all()

        # Desactiver les boutons pendant la mise a jour
        self.buttons["update_all"].set_sensitive(False)
        self.buttons["refresh"].set_sensitive(False)

        import threading
        from gi.repository import GLib

        def _run():
            try:
                logfile = open(f'/home/Volumic/VyperOS/update_{program}.log', 'w')
                proc = subprocess.Popen(
                    ['sudo', 'bash', script_path],
                    stdout=logfile,
                    stderr=logfile,
                )
                proc.wait()   # attendre la fin du script
            except Exception as e:
                logging.error(f"updater: lancement echoue : {e}")
            finally:
                GLib.idle_add(_on_done)

        def _on_done():
            spinner.stop()
            # Relancer le refresh pour mettre a jour l'affichage
            self.activate()
            return False

        threading.Thread(target=_run, daemon=True).start()

    def show_update_info(self, widget, program):
        info = (
            self.update_status["version_info"][program]
            if program in self.update_status["version_info"]
            else {}
        )

        scroll = self._gtk.ScrolledWindow(steppers=False)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        label = Gtk.Label(wrap=True, vexpand=True)
        if program == "full":
            label.set_markup("<b>" + _("Perform a full upgrade?") + "</b>")
            vbox.add(label)
        elif "configured_type" in info and info["configured_type"] == "git_repo":
            if not info["is_valid"] or info["is_dirty"]:
                label.set_markup(_("Do you want to recover %s?") % program)
                recoverybuttons = [
                    {
                        "name": _("Recover Hard"),
                        "response": Gtk.ResponseType.OK,
                        "style": "dialog-warning",
                    },
                    {
                        "name": _("Recover Soft"),
                        "response": Gtk.ResponseType.APPLY,
                        "style": "dialog-info",
                    },
                    {
                        "name": _("Cancel"),
                        "response": Gtk.ResponseType.CANCEL,
                        "style": "dialog-error",
                    },
                ]
                self._gtk.Dialog(
                    _("Recover"), recoverybuttons, label, self.reset_confirm, program
                )
                return
            else:
                if info["version"] == info["remote_version"]:
                    return
                ncommits = len(info["commits_behind"])
                label.set_markup(
                    "<b>"
                    + _("Outdated by %d") % ncommits
                    + " "
                    + ngettext("commit", "commits", ncommits)
                    + ":</b>\n"
                )
                vbox.add(label)
                label.set_vexpand(False)
                for c in info["commits_behind"]:
                    commit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                    title = Gtk.Label(wrap=True, hexpand=True)
                    title.set_markup(f"\n<b>{c['subject']}</b>\n<i>{c['author']}</i>\n")
                    commit_box.add(title)

                    details = Gtk.Label(label=c["message"], wrap=True, hexpand=True)
                    commit_box.add(details)
                    commit_box.add(Gtk.Separator())
                    vbox.add(commit_box)

        elif "package_count" in info:
            label.set_markup(
                (
                    f'<b>{info["package_count"]} '
                    + ngettext(
                        "Package will be updated",
                        "Packages will be updated",
                        info["package_count"],
                    )
                    + ":</b>\n"
                )
            )
            label.set_vexpand(False)
            vbox.set_valign(Gtk.Align.CENTER)
            vbox.add(label)
            grid = Gtk.Grid(
                column_homogeneous=True,
                halign=Gtk.Align.CENTER,
                valign=Gtk.Align.CENTER,
            )
            i = 0
            for j, c in enumerate(info["package_list"]):
                label = Gtk.Label(
                    halign=Gtk.Align.START, ellipsize=Pango.EllipsizeMode.END
                )
                label.set_markup(f"  {c}  ")
                pos = j % 3
                grid.attach(label, pos, i, 1, 1)
                if pos == 2:
                    i += 1
            vbox.add(grid)
        else:
            label.set_markup(
                "<b>"
                + _("%s will be updated to version") % program.capitalize()
                + f": {info['remote_version']}</b>"
            )
            vbox.add(label)

        scroll.add(vbox)

        buttons = [
            {
                "name": _("Accept"),
                "response": Gtk.ResponseType.OK,
                "style": "dialog-info",
            },
            {
                "name": _("Cancel"),
                "response": Gtk.ResponseType.CANCEL,
                "style": "dialog-error",
            },
        ]
        self._gtk.Dialog(_("Update"), buttons, scroll, self.update_confirm, program)

    def update_confirm(self, dialog, response_id, program):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            logging.debug(f"Updating {program}")
            self.update_program(self, program)

    def reset_confirm(self, dialog, response_id, program):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            logging.debug(f"Recovering hard {program}")
            self.reset_repo(self, program, True)
        if response_id == Gtk.ResponseType.APPLY:
            logging.debug(f"Recovering soft {program}")
            self.reset_repo(self, program, False)

    def reset_repo(self, widget, program, hard):
        if self._screen.updating:
            return
        self._screen.base_panel.show_update_dialog()
        msg = _("Starting recovery for") + f" {program}..."
        self._screen._websocket_callback(
            "notify_update_response",
            {"application": {program}, "message": msg, "complete": False},
        )
        logging.info(f"Sending machine.update.recover name: {program} hard: {hard}")
        self._screen._ws.send_method(
            "machine.update.recover", {"name": program, "hard": hard}
        )

    def update_program(self, widget, program):
        if self._screen.updating or not self.update_status:
            return

        if program in self.update_status["version_info"]:
            info = self.update_status["version_info"][program]
            logging.info(f"program: {info}")
            if (
                "package_count" in info
                and info["package_count"] == 0
                or "version" in info
                and info["version"] == info["remote_version"]
            ):
                return
        self._screen.base_panel.show_update_dialog()
        #msg = ("Mise a jour de VyperOS\nVeuillez patienter...")
        msg = ("Mise a jour de VyperOS\nVeuillez patienter...\n\nSi l'écran devient entièrement noir et ne change plus\nou si la machine ne redémarre pas correctement\néteignez-la et rallumez-la.")
        self._screen._websocket_callback(
            "notify_update_response",
            {"application": {program}, "message": msg, "complete": False},
        )

        if program in ["full"]:
            logging.info(f"Sending machine.update.{program}")
            self._screen.base_panel.show_update_dialog()
            self._screen._send_action(widget, "printer.gcode.script", {"script": 'SET_LED LED="Eclairage_LEDs" RED=1 GREEN=0 BLUE=0 SYNC=0 TRANSMIT=1'})
            self._screen._send_action(widget, "printer.gcode.script", {"script": 'SET_FAN_SPEED FAN=_Alimentation SPEED=0.6'})
            #self._screen._send_action(widget, "machine.services.stop", {"service": "klipper"})
            #self._screen._send_action(widget, "machine.services.stop", {"service": "mainsail"})
            try:
                logfile = open('/home/Volumic/VyperOS/vyperos_lastupdate.log', 'w')
                subprocess.Popen(
                    ['sudo', 'bash', '/home/Volumic/VyperOS/vyperos_update.sh'],
                    stdout=logfile,
                    stderr=logfile,
                )
            except Exception as e:
                logging.error(f"updater: launch failed: {e}")
        else:
            logging.info(f"Sending machine.update.client name: {program}")
            self._screen._ws.send_method("machine.update.client", {"name": program})

    def update_program_info(self, p):

        if not self.update_status or p not in self.update_status["version_info"]:
            logging.info(f"Unknown version: {p}")
            return

        info = self.update_status["version_info"][p]

        if p == "system":
            distro = (
                self._printer.system_info["distribution"]["name"]
                if "distribution" in self._printer.system_info
                and "name" in self._printer.system_info["distribution"]
                else _("System")
            )
            self.labels[p].set_markup(f"<b>{distro}</b>")
            if info["package_count"] == 0:
                self._already_updated(p)
            else:
                self._needs_update(p, local="", remote=info["package_count"])

        elif "configured_type" in info and info["configured_type"] == "git_repo":
            if info["is_valid"] and not info["is_dirty"]:
                if info["version"] == info["remote_version"]:
                    self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']}")
                    self._already_updated(p)
                    self.labels[f"{p}_status"].get_style_context().remove_class(
                        "invalid"
                    )
                else:
                    self.labels[p].set_markup(
                        f"<b>{p}</b>\n{info['version']} -> {info['remote_version']}"
                    )
                    self._needs_update(p, info["version"], info["remote_version"])
            else:
                logging.info(f"Invalid {p} {info['version']}")
                self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']}")
                self.labels[f"{p}_status"].set_label(_("Updating"))
                self.labels[f"{p}_status"].get_style_context().add_class("invalid")
                self.labels[f"{p}_status"].set_sensitive(True)
                if f"{p}_update" in self.buttons:
                    self.buttons[f"{p}_update"].set_sensitive(True)
        elif "version" in info and info["version"] == info["remote_version"]:
            self.labels[p].set_markup(f"<b>{p}</b>\n{info['version']}")
            self._already_updated(p)
        else:
            self.labels[p].set_markup(
                f"<b>{p}</b>\n{info['version']} -> {info['remote_version']}"
            )
            self._needs_update(p, info["version"], info["remote_version"])

    def _already_updated(self, p):
        self.labels[f"{p}_status"].set_label(_("Up To Date"))
        self.labels[f"{p}_status"].get_style_context().remove_class("update")
        self.labels[f"{p}_status"].set_sensitive(False)
        if f"{p}_update" in self.buttons:
            self.buttons[f"{p}_update"].set_sensitive(False)

    def _needs_update(self, p, local="", remote=""):
        logging.info(f"{p} {local} -> {remote}")
        self.labels[f"{p}_status"].set_label(_("Updating"))
        self.labels[f"{p}_status"].get_style_context().add_class("update")
        self.labels[f"{p}_status"].set_sensitive(True)
        if f"{p}_update" in self.buttons:
            self.buttons[f"{p}_update"].set_sensitive(True)