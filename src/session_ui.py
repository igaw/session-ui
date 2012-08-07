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

from PyQt4 import uic
from PyQt4.QtCore import SIGNAL, SLOT, QObject, QTimer, Qt
from PyQt4.QtGui import *

import distutils.sysconfig

import traceback

import dbus
import dbus.service
import dbus.mainloop.qt
dbus.mainloop.qt.DBusQtMainLoop(set_as_default=True)

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
	for key in values.keys():
		val += " " + key + "="
		if key in [ "PrefixLength" ]:
			val += "%s" % (int(values[key]))
		else:
			if key in [ "Servers", "Excludes" ]:
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
		print "Release"
		self.cb_release()

	@dbus.service.method("net.connman.Notification",
				in_signature='a{sv}', out_signature='')
	def Update(self, settings):
		print "Update called"
		self.cb_settings(settings)

class Session(QWidget):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)

		ui_class, widget_class = uic.loadUiType(get_resource_path('ui/session.ui'))
		self.ui = ui_class()
		self.ui.setupUi(self)

		self.connect(self.ui.pb_SessionEnable, SIGNAL('clicked()'), self.cb_SessionEnable)
		self.connect(self.ui.pb_SessionDisable, SIGNAL('clicked()'), self.cb_SessionDisable)

		self.connect(self.ui.pb_Create, SIGNAL('clicked()'), self.cb_Create)
		self.connect(self.ui.pb_Destroy, SIGNAL('clicked()'), self.cb_Destroy)
		self.connect(self.ui.pb_Connect, SIGNAL('clicked()'), self.cb_Connect)
		self.connect(self.ui.pb_Disconnect, SIGNAL('clicked()'), self.cb_Disconnect)

		self.connect(self.ui.pb_Quit, SIGNAL('clicked()'), self.cb_Quit)

		self.connect(self.ui.le_SessionName, SIGNAL('editingFinished()'), self.cb_SessionName)

		self.connect(self.ui.le_ConnectionType, SIGNAL('editingFinished()'), self.cb_ConnectionType)
		self.connect(self.ui.le_Priority, SIGNAL('editingFinished()'), self.cb_Priority)
		self.connect(self.ui.le_AllowedBearers, SIGNAL('editingFinished()'), self.cb_AllowedBearers)
		self.connect(self.ui.le_AvoidHandover, SIGNAL('editingFinished()'), self.cb_AvoidHandover)
		self.connect(self.ui.le_StayConnected, SIGNAL('editingFinished()'), self.cb_StayConnected)
		self.connect(self.ui.le_PeriodicConnect, SIGNAL('editingFinished()'), self.cb_PeriodicConnnect)
		self.connect(self.ui.le_IdleTimeout, SIGNAL('editingFinished()'), self.cb_IdleTimeout)
		self.connect(self.ui.le_EmergencyCall, SIGNAL('editingFinished()'), self.cb_EmergencyCall)
		self.connect(self.ui.le_RoamingPolicy, SIGNAL('editingFinished()'), self.cb_Priority)

		self.notify = None
		self.notify_path = "/foo"
		self.ui.le_SessionName.setText(self.notify_path)

		self.bus = dbus.SystemBus()
		self.manager = None
		self.session = None

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

	def set_controls(self, enable):
		self.ui.pb_Create.setEnabled(not enable)
		self.ui.pb_Connect.setEnabled(enable)
		self.ui.pb_Disconnect.setEnabled(enable)
		self.ui.pb_Destroy.setEnabled(enable)

	def reset_fields(self):
		self.ui.le_State.setText("")
		self.ui.le_AvoidHandover.setText("")
		self.ui.le_AllowedBearers.setText("")
		self.ui.le_Bearer.setText("")
		self.ui.le_EmergencyCall.setText("")
		self.ui.le_ConnectionType.setText("")
		self.ui.le_PeriodicConnect.setText("")
		self.ui.le_StayConnected.setText("")
		self.ui.le_IdleTimeout.setText("")
		self.ui.le_SessionMarker.setText("")
		self.ui.le_Priority.setText("")
		self.ui.le_IPv4.setText("")
		self.ui.le_IPv6.setText("")
		self.ui.le_Interface.setText("")
		self.ui.le_RoamingPolicy.setText("")
		self.ui.le_Name.setText("")

	def reset(self):
		self.settings = {}
		if self.notify:
			self.notify.remove_from_connection(self.bus, self.notify_path)
			self.notify = None
		if self.session:
			self.session = None
		self.reset_fields()

		self.set_controls(False)

	def session_change(self, key, value):
		if key not in self.settings:
			self.settings[key] = self.convert_type_to_dbus(key, value)
		elif self.settings[key] != value:
			val = self.convert_type_to_dbus(key, value)

			if (self.session != None):
				self.session.Change(key, val)

	def cb_ConnectionType(self):
		self.session_change('ConnectionType', str(self.ui.le_ConnectionType.displayText()))

	def cb_Priority(self):
		self.session_change('Priority', str(self.ui.le_Priority.displayText()))

	def cb_AllowedBearers(self):
		self.session_change('AllowedBearers', str(self.ui.le_AllowedBearers.displayText()))

	def cb_AvoidHandover(self):
		self.session_change('AvoidHandover', str(self.ui.le_AvoidHandover.displayText()))

	def cb_StayConnected(self):
		self.session_change('StayConnected', str(self.ui.le_StayConnected.displayText()))

	def cb_PeriodicConnnect(self):
		self.session_change('PeriodicConnect', str(self.ui.le_PeriodicConnect.displayText()))

	def cb_IdleTimeout(self):
		self.session_change('IdleTimeout', str(self.ui.le_IdleTimeout.displayText()))

	def cb_EmergencyCall(self):
		self.session_change('EmergencyCall', str(self.ui.le_EmergencyCall.displayText()))

	def cb_RoamingPolicy(self):
		self.session_change('RoamingPolicy', str(self.ui.le_RoamingPolicy.displayText()))

	def cb_Release(self):
		self.reset()

	def cb_SessionName(self):
		self.notify_path = str(self.le_SessionName.displayText())

	def set_session_mode(self, enable):
		try:
			self.manager.SetProperty("SessionMode", enable)
		except dbus.DBusException, e:
			traceback.print_exc()

	def cb_SessionEnable(self):
		self.set_session_mode(True)

	def cb_SessionDisable(self):
		self.set_session_mode(False)

	def convert_type_from_dbus(self, key, settings):
		val = None

		if key in [ "IPv4", "IPv6" ]:
			val = extract_values(settings[key])
		elif key in  [ "AllowedBearers" ]:
			val = extract_list(settings[key])
		elif key in [ "Priority", "AvoidHandover",
			      "StayConnected", "EmergencyCall" ]:
			val = bool(settings[key])
			if val:
				val = '1'
			else:
				val = '0'
		elif key in [ "PeriodicConnect", "IdleTimeout",
			      "SessionMarker" ]:
			val = int(settings[key])
		else:
			val = str(settings[key])

		return val

	def convert_type_to_dbus(self, key, value):
		val = None

		if key in  [ "AllowedBearers" ]:
			if value != None and len(value) > 0:
				val = dbus.Array(value.split(' '))
			else:
				val = str("")
		elif key in [ "Priority", "AvoidHandover",
			      "StayConnected", "EmergencyCall" ]:
			flag = str(value)
			val = flag not in ['0']
			val = dbus.Boolean(val)
		elif key in [ "PeriodicConnect", "IdleTimeout" ]:
			if value != None and len(value) > 0:
				val = dbus.UInt32(value)
		elif key in [ "ConnectionType" ]:
			if value != None and len(value) > 0:
				val = str(value)
			else:
				val = str("")

		return val

	def cb_updateSettings(self, settings):
		try:
			for key in settings.keys():
				val = self.convert_type_from_dbus(key, settings)
				print "	  %s = %s" % (key, val)

				self.settings[key] = val

				lineEdit = getattr(self.ui, 'le_' + key)
				lineEdit.setText(str(val))
		except:
			print "Exception:"
			traceback.print_exc()

	def cb_Create(self):
		try:
			self.notify = Notification(self.bus, self.notify_path,
						   self.cb_updateSettings, self.cb_Release)
			self.notify.add_to_connection(self.bus, self.notify_path)

			self.session_path = self.manager.CreateSession(self.settings, self.notify_path)
			print "Session Path: ", self.session_path

			self.session = dbus.Interface(self.bus.get_object("net.connman", self.session_path),
							"net.connman.Session")

			self.set_controls(True)
		except dbus.DBusException, e:
			if e.get_dbus_name() in ['net.connman.Error.AlreadyExists']:
				print e.get_dbus_message()
				return
			traceback.print_exc()

	def cb_Destroy(self):
		try:
			self.manager.DestroySession(self.session_path)

			self.reset()
		except dbus.DBusException, e:
			if e.get_dbus_name() in ['net.connman.Error.InvalidArguments']:
				print e.get_dbus_message()
				return
			traceback.print_exc()

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

def main():
	app = QApplication(sys.argv)
	myapp = Session()
	myapp.show()
	sys.exit(app.exec_())

if __name__ == "__main__":
	main()