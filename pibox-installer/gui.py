import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
from backend import catalog
from run_installation import run_installation
from set_path import set_path
import pytz
import re
import os
import sys
import threading
from cancel import CancelEvent

set_path()

if getattr(sys, "frozen", False):
    DATA_DIR = sys._MEIPASS
else:
    DATA_DIR = ""

class Logger:
    def __init__(self, text_buffer):
        self.text_buffer = text_buffer

    def step(self, step):
        GLib.idle_add(self.text_buffer.insert_at_cursor, "\033[00;34m--> " + step + "\033[00m\n")

    def err(self, err):
        GLib.idle_add(self.text_buffer.insert_at_cursor, "\033[00;31m" + err + "\033[00m\n")

    def raw_std(self, std):
        GLib.idle_add(self.text_buffer.insert_at_cursor, std)

    def std(self, std):
        GLib.idle_add(self.text_buffer.insert_at_cursor, std + "\n")

class Component:
    def __init__(self, builder):
        self.builder = builder

    def __getattr__(self, key):
        """Allow UI builder widgets to be accessed as self.widgetname"""
        widget = self.builder.get_object(key)
        if widget:
            setattr(self, key, widget)
            return widget
        raise AttributeError(key)

def validate_label(label, condition):
    color_invalid = Gdk.Color(65535, 30000, 30000)
    if condition:
        label.modify_bg(Gtk.StateFlags.NORMAL)
    else:
        label.modify_bg(Gtk.StateFlags.NORMAL, color_invalid)

class Application:
    def __init__(self, catalog):
        self.catalog = catalog

        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(DATA_DIR, "ui.glade"))

        self.component = Component(builder)

        self.component.window.connect("delete-event", Gtk.main_quit)

        self.component.done_window.set_transient_for(self.component.run_window)
        self.component.done_window.set_default_size(320, 240)
        self.component.done_window.set_modal(True)
        self.component.done_window_ok_button.connect("clicked", self.done_window_ok_button_clicked)

        self.cancel_event = CancelEvent()
        self.component.run_window.connect("delete-event", Gtk.main_quit)
        self.component.run_window.connect("delete-event", self.run_install_cancel)
        self.logger = Logger(self.component.run_text_view.get_buffer())

        self.component.run_abort_done_button.connect("clicked", self.run_abort_done_button_clicked)

        # wifi password
        self.component.wifi_password_switch.connect("state-set", lambda switch, state: self.component.wifi_password_revealer.set_reveal_child(state))

        # timezone
        for timezone in pytz.common_timezones:
            self.component.timezone_tree_store.append(None, [timezone])

        renderer = Gtk.CellRendererText()
        self.component.timezone_combobox.pack_start(renderer, True)
        self.component.timezone_combobox.add_attribute(renderer, "text", 0)

        # zim content
        self.component.zim_choose_content_button.connect("clicked", self.zim_choose_content_button_clicked)
        self.component.run_installation_button.connect("clicked", self.run_installation_button_clicked)

        self.component.zim_list_store = Gtk.ListStore(str, str, str, str, str, str, str, str, bool);

        for one_catalog in catalog:
            for (key, value) in one_catalog["all"].items():
                name = value["name"]
                url = value["url"]
                description = value.get("description") or "none"
                size = str(value["size"])
                language = value.get("language") or "none"
                typ = value["type"]
                version = str(value["version"])

                self.component.zim_list_store.append([key, name, url, description, size, language, typ, version, False])

        self.component.zim_choosen_filter = self.component.zim_list_store.filter_new()
        self.component.zim_choosen_filter.set_visible_func(self.zim_choosen_filter_func)
        self.component.zim_choosen_tree_view.set_model(self.component.zim_choosen_filter)

        renderer_text = Gtk.CellRendererText()
        column_text = Gtk.TreeViewColumn("Id", renderer_text, text=0)
        self.component.zim_choosen_tree_view.append_column(column_text)

        self.component.window.show()

    def run_install_cancel(self, widget, path):
        self.cancel_event.signal_and_wait_consumed()

    def zim_choosen_filter_func(self, model, iter, data):
        return model[iter][8]

    def zim_choose_content_button_clicked(self, button):
        ZimChooserWindow(self.component.window, self.component.zim_list_store)

    def run_installation_button_clicked(self, button):
        all_valid = True

        project_name = self.component.project_name_entry.get_text()
        condition = project_name != ""
        validate_label(self.component.project_name_label, condition)
        all_valid = all_valid and condition

        timezone_id = self.component.timezone_combobox.get_active()
        timezone = self.component.timezone_tree_store[timezone_id][0]
        condition = timezone_id != -1
        validate_label(self.component.timezone_label, condition)
        all_valid = all_valid and condition

        try:
            size = int(self.component.size_entry.get_text())
        except:
            size = 0
        condition = size > 0
        validate_label(self.component.size_label, condition)
        all_valid = all_valid and condition

        if self.component.wifi_password_switch.get_state:
            wifi_pwd = self.component.wifi_password_entry.get_text()
        else:
            wifi_pwd = None

        zim_install = []
        for zim in self.component.zim_list_store:
            if zim[8]:
                zim_install.append(zim[0])

        if all_valid:
            def target():
                run_installation(
                        name=project_name,
                        timezone=timezone,
                        wifi_pwd=wifi_pwd,
                        kalite=None,
                        zim_install=zim_install,
                        size=size,
                        logger=self.logger,
                        directory="build",
                        cancel_event=self.cancel_event,
                        done_callback=lambda : GLib.idle_add(self.installation_done))

            self.component.window.destroy()
            self.component.run_window.show()
            threading.Thread(target=target, daemon=True).start()

    def run_abort_done_button_clicked(self, widget):
        self.component.run_window.close()

    def done_window_ok_button_clicked(self, widget):
        self.component.done_window.close()

    def installation_done(self):
        self.component.done_window.show()
        self.component.run_abort_done_button.set_label("Close")
        #TODO change abort label to close

class ZimChooserWindow:
    def __init__(self, parent, zim_list_store):
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(DATA_DIR, "ui.glade"))

        self.component = Component(builder)

        self.component.zim_list_store = zim_list_store

        self.component.zim_tree_view.set_model(self.component.zim_list_store)

        renderer_radio = Gtk.CellRendererToggle()
        column_radio = Gtk.TreeViewColumn("Radio", renderer_radio, active=8)
        self.component.zim_tree_view.append_column(column_radio)
        renderer_radio.connect("toggled", self.renderer_radio_toggled)

        renderer_text = Gtk.CellRendererText()
        column_text = Gtk.TreeViewColumn("Id", renderer_text, text=0)
        self.component.zim_tree_view.append_column(column_text)
        column_text = Gtk.TreeViewColumn("Name", renderer_text, text=1)
        self.component.zim_tree_view.append_column(column_text)
        column_text = Gtk.TreeViewColumn("Language", renderer_text, text=5)
        self.component.zim_tree_view.append_column(column_text)
        column_text = Gtk.TreeViewColumn("Size", renderer_text, text=4)
        self.component.zim_tree_view.append_column(column_text)
        column_text = Gtk.TreeViewColumn("Type", renderer_text, text=6)
        self.component.zim_tree_view.append_column(column_text)
        column_text = Gtk.TreeViewColumn("Description", renderer_text, text=3)
        self.component.zim_tree_view.append_column(column_text)

        self.component.zim_language_list_store.append(["all"])
        renderer = Gtk.CellRendererText()
        self.component.zim_language_combobox.pack_start(renderer, True)
        self.component.zim_language_combobox.add_attribute(renderer, "text", 0)
        self.component.zim_language_combobox.set_active(0)

        self.component.zim_window.set_transient_for(parent)
        self.component.zim_window.set_modal(True)
        self.component.zim_window.set_default_size(1280, 800)
        self.component.zim_window.show()

        self.component.zim_window_done_button.connect("clicked", self.zim_done_button_clicked)

    def zim_done_button_clicked(self, widget):
        self.component.zim_window.close()

    def renderer_radio_toggled(self, widget, path):
        self.component.zim_list_store[path][8] = not self.component.zim_list_store[path][8]

catalog = catalog.get_catalogs()
Application(catalog)
Gtk.main()
