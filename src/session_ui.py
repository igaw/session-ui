#!/usr/bin/env python
#  Copyright (C) 2011  BMW Car IT GmbH. All rights reserved.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 2 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import os
import signal
import sys
from functools import partial

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QWidget, QApplication

import distutils.sysconfig

import traceback

import dbus
import dbus.service
import dbus.mainloop.qt
from dbus.mainloop.pyqt5 import DBusQtMainLoop

signal.signal(signal.SIGINT, signal.SIG_DFL)


def get_resource_path(filename):
    if __name__ == '__main__':
        return filename

    return os.path.join(distutils.sysconfig.get_python_lib(),
                        'session_ui', filename)


def extract_list(list):
    val = ""
    for i in list:
        val += " " + str(i)
    return val.strip()


def extract_values(values):
    val = ""
    for key in list(values.keys()):
        val += " " + key + "="
        if key in ["PrefixLength"]:
            val += "%s" % (int(values[key]))
        else:
            if key in ["Servers", "Excludes"]:
                val += extract_list(values[key])
            else:
                val += str(values[key])
    return val.strip()


class Notification(dbus.service.Object):

    def __init__(self, bus, notify_path, cb_settings, cb_release):
        dbus.service.Object.__init__(self)
        self.cb_settings = cb_settings
        self.cb_release = cb_release

    @dbus.service.method("net.connman.Notification",
                         in_signature='', out_signature='')
    def Release(self):
        print("Release")
        self.cb_release()

    @dbus.service.method("net.connman.Notification",
                         in_signature='a{sv}', out_signature='')
    def Update(self, settings):
        print("Update called")
        self.cb_settings(settings)


class Session(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        ui_class, widget_class = uic.loadUiType(
            get_resource_path('ui/session.ui'))
        self.ui = ui_class()
        self.ui.setupUi(self)

        self.ui.pb_SessionEnable.clicked.connect(self.cb_SessionEnable)
        self.ui.pb_SessionDisable.clicked.connect(self.cb_SessionDisable)
        self.ui.pb_Create.clicked.connect(self.cb_Create)
        self.ui.pb_Destroy.clicked.connect(self.cb_Destroy)
        self.ui.pb_Disconnect.clicked.connect(self.cb_Disconnect)
        self.ui.pb_Quit.clicked.connect(self.cb_Quit)
        self.ui.le_SessionName.editingFinished.connect(self.cb_SessionName)
        self.ui.le_AllowedBearers.editingFinished.connect(
            self.cb_AllowedBearers)
        self.ui.le_ConnectionType.editingFinished.connect(
            self.cb_ConnectionType)
        self.ui.le_AllowedInterface.editingFinished.connect(
            self.cb_AllowedInterface)
        self.ui.cbox_SourceIPRRule.stateChanged.connect(
            self.cb_SourceIPRule)
        self.session_path = None
        self.notify = None
        self.notify_path = "/foo"
        self.ui.le_SessionName.setText(self.notify_path)

        self.bus = dbus.SystemBus()
        self.manager = None
        self.session = None

        try:
            self.bus.watch_name_owner(
                'net.connman', self.connman_name_owner_changed)
        except dbus.DBusException as e:
            print(e.get_dbus_message())
            exit(1)

    def connman_name_owner_changed(self, proxy):
        try:
            if proxy:
                print("ConnMan appeared on D-Bus ", str(proxy))
                self.manager = dbus.Interface(self.bus.get_object(
                    "net.connman", "/"), "net.connman.Manager")
            else:
                self.manager = None
                print("ConnMan disappeared on D-Bus")
            self.reset()
        except dbus.DBusException as e:
            print(e.get_dbus_message())
            exit(1)

    def set_controls(self, enable):
        self.ui.pb_Create.setEnabled(not enable)
        self.ui.pb_Connect.setEnabled(enable)
        self.ui.pb_Disconnect.setEnabled(enable)
        self.ui.pb_Destroy.setEnabled(enable)

    def reset_fields(self):
        self.ui.le_State.setText("")
        self.ui.le_Name.setText("")
        self.ui.le_Bearer.setText("")
        self.ui.le_Interface.setText("")
        self.ui.le_IPv4.setText("")
        self.ui.le_IPv6.setText("")
        self.ui.le_AllowedBearers.setText("*")
        self.ui.le_ConnectionType.setText("any")
        self.ui.le_AllowedInterface.setText("*")
        self.ui.cbox_SourceIPRRule.setCheckState(0)

    def reset(self):
        self.settings = {}

        if self.manager and self.session_path:
            self.manager.DestroySession(self.session_path)

        if self.notify:
            try:
                self.notify.remove_from_connection(self.bus, self.notify_path)
            except:
                pass
            self.notify = None
        if self.session:
            self.session = None
        self.reset_fields()
        self.cb_AllowedBearers()
        self.cb_ConnectionType()

        self.set_controls(False)

    def session_change(self, key, value):
        val = self.convert_type_to_dbus(key, value)

        if key not in self.settings:
            self.settings[key] = val
        elif self.settings[key] != val:
            self.settings[key] = val
            if (self.session is not None):
                self.session.Change(key, val)

    def cb_AllowedBearers(self):
        value = str(self.ui.le_AllowedBearers.displayText())
        self.session_change('AllowedBearers', value)

    def cb_ConnectionType(self):
        value = str(self.ui.le_ConnectionType.displayText())
        self.session_change('ConnectionType', value)

    def cb_AllowedInterface(self):
        pass

    def cb_SourceIPRule(self, state):
        pass

    def cb_Release(self):
        self.reset()

    def cb_SessionName(self):
        self.notify_path = str(self.ui.le_SessionName.displayText())

    def set_session_mode(self, enable):
        if not self.manager:
            return
        try:
            self.manager.SetProperty("SessionMode", enable)
        except dbus.DBusException as e:
            print(e.get_dbus_message())

    def cb_SessionEnable(self):
        self.set_session_mode(True)

    def cb_SessionDisable(self):
        self.set_session_mode(False)

    def convert_type_from_dbus(self, key, settings):
        val = None

        if key in ["IPv4", "IPv6"]:
            val = extract_values(settings[key])
        elif key in ["AllowedBearers"]:
            val = extract_list(settings[key])
        else:
            val = str(settings[key])

        return val

    def convert_type_to_dbus(self, key, value):
        val = None
        if key in ["AllowedBearers"]:
            if value is not None and len(value) > 0:
                val = dbus.Array(value.split(' '),
                                 signature='s')
            else:
                val = dbus.Array(signature='s')
        elif key in ["ConnectionType"]:
            if value is not None and len(value) > 0:
                val = dbus.String(str(value))
            else:
                val = dbus.String('')

        return val

    def cb_updateSettings(self, settings):
        try:
            for key in list(settings.keys()):
                val = self.convert_type_from_dbus(key, settings)
                print("	  %s = %s" % (key, val))

                self.settings[key] = val

                if key == 'SourceIPRule':
                    state = 0
                    if val:
                        state = 2
                    self.ui.cbox_SourceIPRRule.setCheckState(state)
                    return

                lineEdit = getattr(self.ui, 'le_' + key)
                lineEdit.setText(str(val))
        except:
            print("Exception:")
            traceback.print_exc()

    def handle_session_create(self, path):
        print("Session Path %s" % path)

        self.session_path = path
        self.session = dbus.Interface(
            self.bus.get_object(
                "net.connman",
                self.session_path),
            "net.connman.Session")
        self.set_controls(True)

    def handle_session_create_error(self, e):
        print("RaiseException raised an exception as expected:")
        print("\t", str(e))

    def cb_Create(self):
        if not self.manager:
            return
        try:
            self.notify = Notification(self.bus, self.notify_path,
                                       self.cb_updateSettings, self.cb_Release)
            self.notify.add_to_connection(self.bus, self.notify_path)

            infinite = 2147483647.0 / 1000.0
            self.manager.CreateSession(
                self.settings,
                self.notify_path,
                timeout=infinite,
                reply_handler=self.handle_session_create,
                error_handler=self.handle_session_create_error)
        except dbus.DBusException as e:
            print(e.get_dbus_message())

            if e.get_dbus_name() in ['net.connman.Error.AlreadyExists']:
                return

            if self.notify:
                self.notify.remove_from_connection(self.bus, self.notify_path)
                self.notify = None
                return

    def cb_Destroy(self):
        try:
            self.reset()
        except dbus.DBusException as e:
            print(e.get_dbus_message())

    def cb_Connect(self):
        if not self.session:
            return
        try:
            self.session.Connect()
        except dbus.DBusException as e:
            print(e.get_dbus_message())

    def cb_Disconnect(self):
        if not self.session:
            return
        try:
            self.session.Disconnect()
        except dbus.DBusException as e:
            print(e.get_dbus_message())

    def cb_Quit(self):
        sys.exit()


def main():
    try:
        import selinux
        print(selinux.getcon())
    except:
        print("no SELinux available")

    DBusQtMainLoop(set_as_default = True)
    app = QApplication(sys.argv)
    myapp = Session()
    myapp.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
