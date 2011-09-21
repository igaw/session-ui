#  IVI Connection Manager
#
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

# Build Instruction
# pyuic4 session.ui > session_ui.py

import signal
import sys
from session_ui import Ui_Session

from PyQt4.QtCore import SIGNAL, SLOT, QObject, QTimer, Qt
from PyQt4.QtGui import *


import traceback

import dbus
import dbus.service
import dbus.mainloop.qt
dbus.mainloop.qt.DBusQtMainLoop(set_as_default=True)

import weakref

_emitterCache = weakref.WeakKeyDictionary()

signal.signal(signal.SIGINT, signal.SIG_DFL)

def emitter(ob):
    if ob not in _emitterCache:
        _emitterCache[ob] = QObject()
    return _emitterCache[ob]

def extract_list(list):
        val = ""
        for i in list:
                val += " " + str(i)
        return val.strip()

def extract_values(values):
        val = ""
        for key in values.keys():
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
        def __init__(self, bus, notify_path):
                dbus.service.Object.__init__(self)

        @dbus.service.method("net.connman.Notification",
                                in_signature='', out_signature='')
        def Release(self):
                print("Release")
                QObject.emit(emitter(self), SIGNAL('Release'), '')

        @dbus.service.method("net.connman.Notification",
                                in_signature='a{sv}', out_signature='')
        def Update(self, settings):
                print "Update called"

                try:
                        for key in settings.keys():
                                if key in ["IPv4", "IPv6"]:
                                        val = extract_values(settings[key])
                                elif key in  ["AllowedBearers" ]:
                                        val = extract_list(settings[key])
                                else:
                                        val = settings[key]
                                print "    %s = %s" % (key, val)
                                QObject.emit(emitter(self), SIGNAL(key), str(val))
                except:
                        print "Exception:"
                        traceback.print_exc()

class Session(QWidget, Ui_Session):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)

        self.connect(self.pb_SessionEnable, SIGNAL('clicked()'), self.cb_SessionEnable)
        self.connect(self.pb_SessionDisable, SIGNAL('clicked()'), self.cb_SessionDisable)

        self.connect(self.pb_Create, SIGNAL('clicked()'), self.cb_Create)
        self.connect(self.pb_Destroy, SIGNAL('clicked()'), self.cb_Destroy)
        self.connect(self.pb_Connect, SIGNAL('clicked()'), self.cb_Connect)
        self.connect(self.pb_Disconnect, SIGNAL('clicked()'), self.cb_Disconnect)

        self.connect(self.pb_Quit, SIGNAL('clicked()'), self.cb_Quit)

        self.connect(self.le_SessionName, SIGNAL('editingFinished()'), self.cb_SessionName)

        self.connect(self.le_Priority, SIGNAL('editingFinished()'), self.cb_Priority)
        self.connect(self.le_AllowedBearers, SIGNAL('editingFinished()'), self.cb_AllowedBearers)
        self.connect(self.le_AvoidHandover, SIGNAL('editingFinished()'), self.cb_AvoidHandover)
        self.connect(self.le_StayConnected, SIGNAL('editingFinished()'), self.cb_StayConnected)
        self.connect(self.le_PeriodicConnect, SIGNAL('editingFinished()'), self.cb_PeriodicConnnect)
        self.connect(self.le_IdleTimeout, SIGNAL('editingFinished()'), self.cb_IdleTimeout)
        self.connect(self.le_EmergencyCall, SIGNAL('editingFinished()'), self.cb_EmergencyCall)
        self.connect(self.le_RoamingPolicy, SIGNAL('editingFinished()'), self.cb_Priority)

        self.notify = None
        self.notify_path = "/foo"
        self.le_SessionName.setText(self.notify_path)

        self.bus = dbus.SystemBus()
        self.manager = None

        try:
            self.bus.watch_name_owner('net.connman', self.connman_name_owner_changed)
        except dbus.DBusException:
            traceback.print_exc()
            exit(1)

    def connman_name_owner_changed(self, proxy):
        try:
            if proxy:
                print "ConnMan appeared on D-Bus ", str(proxy)
                self.manager = dbus.Interface(self.bus.get_object("net.connman", "/"),
                                              "net.connman.Manager")
            else:
                self.manager = None
                print "ConnMan disappeared on D-Bus"
            self.reset()
        except dbus.DBusException:
            traceback.print_exc()
            exit(1)

    def set_online(self, online):
        if online == "1":
            self.le_Online.setText("Online")
        else:
            self.le_Online.setText("Offline")

    def reset_fields(self):
        self.le_AvoidHandover.setText("")
        self.le_AllowedBearers.setText("")
        self.le_Bearer.setText("")
        self.le_EmergencyCall.setText("")
        self.le_PeriodicConnect.setText("")
        self.le_StayConnected.setText("")
        self.set_online("")
        self.le_IdleTimeout.setText("")
        self.le_SessionMarker.setText("")
        self.le_Priority.setText("")
        self.le_IPv4.setText("")
        self.le_IPv6.setText("")
        self.le_Interface.setText("")
        self.le_RoamingPolicy.setText("")
        self.le_Name.setText("")

    def reset(self):
        self.settings = {}
        if self.notify:
            self.notify.remove_from_connection(self.bus, self.notify_path)
            self.notify = None

        self.reset_fields()

    def cb_Priority(self):
        flag = str(self.le_Priority.displayText())
        val = flag not in ['0']
        self.session.Change('Priority', dbus.Boolean(val))

    def cb_AllowedBearers(self):
        val = str(self.le_AllowedBearers.displayText())
        self.session.Change('AllowedBearers', val)

    def cb_AvoidHandover(self):
        flag = str(self.le_AvoidHandover.displayText())
        val = flag not in ['0']
        self.session.Change('AvoidHandover', dbus.Boolean(val))

    def cb_StayConnected(self):
        flag = str(self.le_StayConnected.displayText())
        val = flag not in ['0']
        self.session.Change('StayConnected', dbus.Boolean(val))

    def cb_PeriodicConnnect(self):
        val = str(self.le_PeriodicConnect.displayText())
        self.session.Change('PeriodicConnect', dbus.UInt32(val))

    def cb_IdleTimeout(self):
        val = str(self.le_IdleTimeout.displayText())
        self.session.Change('IdleTimeout', dbus.UInt32(val))

    def cb_EmergencyCall(self):
        flag = str(self.le_EmergencyCall.displayText())
        val = flag not in ['0']
        self.session.Change('EmergencyCall', dbus.Boolean(val))

    def cb_RoamingPolicy(self):
        val = str(self.le_RoamingPolicy.displayText())
        self.session.Change('RoamingPolicy', val)

    def cb_Release(self):
        self.reset()

    def cb_SessionName(self):
        self.notify_path = str(self.le_SessionName.displayText())
        print self.notify_path

    def set_session_mode(self, enable):
        try:
            self.manager.SetProperty("SessionMode", enable)
        except dbus.DBusException, e:
            traceback.print_exc()

    def cb_SessionEnable(self):
        self.set_session_mode(True)

    def cb_SessionDisable(self):
        self.set_session_mode(False)

    def cb_Create(self):
        try:
            self.notify = Notification(self.bus, self.notify_path)
            self.notify.add_to_connection(self.bus, self.notify_path)

            QObject.connect(emitter(self.notify), SIGNAL('Release'), self.cb_Release)

            QObject.connect(emitter(self.notify), SIGNAL('AvoidHandover'), self.le_AvoidHandover.setText)
            QObject.connect(emitter(self.notify), SIGNAL('AllowedBearers'), self.le_AllowedBearers.setText)
            QObject.connect(emitter(self.notify), SIGNAL('Bearer'), self.le_Bearer.setText)
            QObject.connect(emitter(self.notify), SIGNAL('EmergencyCall'), self.le_EmergencyCall.setText)
            QObject.connect(emitter(self.notify), SIGNAL('PeriodicConnect'), self.le_PeriodicConnect.setText)
            QObject.connect(emitter(self.notify), SIGNAL('StayConnected'), self.le_StayConnected.setText)
            QObject.connect(emitter(self.notify), SIGNAL('Online'), self.set_online)
            QObject.connect(emitter(self.notify), SIGNAL('IdleTimeout'), self.le_IdleTimeout.setText)
            QObject.connect(emitter(self.notify), SIGNAL('SessionMarker'), self.le_SessionMarker.setText)
            QObject.connect(emitter(self.notify), SIGNAL('Priority'), self.le_Priority.setText)
            QObject.connect(emitter(self.notify), SIGNAL('IPv4'), self.le_IPv4.setText)
            QObject.connect(emitter(self.notify), SIGNAL('IPv6'), self.le_IPv6.setText)
            QObject.connect(emitter(self.notify), SIGNAL('Interface'), self.le_Interface.setText)
            QObject.connect(emitter(self.notify), SIGNAL('RoamingPolicy'), self.le_RoamingPolicy.setText)
            QObject.connect(emitter(self.notify), SIGNAL('Name'), self.le_Name.setText)

            self.session_path = self.manager.CreateSession(self.settings, self.notify_path)
            print "Session Path: ", self.session_path

            self.session = dbus.Interface(self.bus.get_object("net.connman", self.session_path),
                                                      "net.connman.Session")
        except dbus.DBusException, e:
            if e.get_dbus_name() in ['net.connman.Error.AlreadyExists']:
                print e.get_dbus_message()
                return
            traceback.print_exc()

    def cb_Destroy(self):
        try:
            self.notify.remove_from_connection(self.bus, self.notify_path)
            self.notify = None

            self.manager.DestroySession(self.session_path)
        except dbus.DBusException, e:
            if e.get_dbus_name() in ['net.connman.Error.InvalidArguments']:
                print e.get_dbus_message()
                return
            traceback.print_exc()

        self.reset_fields()

    def cb_Connect(self):
        try:
            self.session.Connect()
        except dbus.DBusException, e:
            if e.get_dbus_name() in ['net.connman.Error.Failed']:
                print e.get_dbus_message()
                return
            traceback.print_exc()

    def cb_Disconnect(self):
        try:
            self.session.Disconnect()
        except dbus.DBusException, e:
            if e.get_dbus_name() in ['net.connman.Error.Failed']:
                print e.get_dbus_message()
                return
            traceback.print_exc()

    def cb_Quit(self):
        sys.exit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    myapp = Session()
    myapp.show()
    sys.exit(app.exec_())
