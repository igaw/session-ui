#!/usr/bin/env python
#  Copyright (C) 2012  BMW Car IT GmbH. All rights reserved.
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

from PyQt4.QtCore import SIGNAL, SLOT, QObject, QTimer, Qt, QUrl
from PyQt4.QtGui import QApplication
from PyQt4.QtNetwork import QHttp

import distutils.sysconfig

import traceback

import dbus
import dbus.service
import dbus.mainloop.qt
dbus.mainloop.qt.DBusQtMainLoop(set_as_default=True)

signal.signal(signal.SIGINT, signal.SIG_DFL)

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

class Session(QObject):
	def __init__(self, url, parent = None):
		QObject.__init__(self, parent)

		self.notify = None
		self.notify_path = "/foo"

		self.bus = dbus.SystemBus()
		self.manager = None
		self.session = None

		self.http = None
		self.url = QUrl(url)

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

		if self.manager:
			self.create_session()

	def create_session(self):
		self.init_http()

		self.cb_Create()
		self.cb_Connect()

	def init_http(self):
		self.http = QHttp(self)
		self.http.requestFinished.connect(self.httpRequestFinished)
		self.http.dataReadProgress.connect(self.updateDataReadProgress)
		self.http.responseHeaderReceived.connect(self.readResponseHeader)
		self.http.authenticationRequired.connect(self.slotAuthenticationRequired)
		self.http.sslErrors.connect(self.sslErrors)

	def httpRequestFinished(self, requestId, error):
		print "httpRequestFinished: ", requestId

	def updateDataReadProgress(self, bytesRead, totalBytes):
		print "updateDataReadProgress: bytesRead %d, totalBytes %d" % (bytesRead, totalBytes)

	def readResponseHeader(self, responseHeader):
		print "readResponseHeader:", responseHeader

	def slotAuthenticationRequired(self, hostName, _, authenticator):
		print "slotAuthenticationRequired: hostName %s, authenticator %s" % (hostName, authenticator)

	def sslErrors(self, errors):
		print "sslErrors: ", errors

	def http_stateChanged(self, state):
		print "stateChanged: ", state

	def http_requestStarted(self, id):
		print "requestStarted: ", id


	def start_http(self):
		self.http.setHost(self.url.host())
		self.http.get(self.url.path())

	def stop_http(self):
		self.http.abort()

	def reset(self):
		self.settings = {}
		if self.notify:
			self.notify.remove_from_connection(self.bus, self.notify_path)
			self.notify = None
		if self.session:
			self.session = None
		if self.http:
			self.http = None

	def session_change(self, key, value):
		if key not in self.settings:
			self.settings[key] = self.convert_type_to_dbus(key, value)
		elif self.settings[key] != value:
			val = self.convert_type_to_dbus(key, value)

			if (self.session != None):
				self.session.Change(key, val)

	def cb_Release(self):
		self.reset()

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

				if key == "State":
					if val == "online":
						self.start_http()
					else:
						self.stop_http()
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
	if len(sys.argv) < 2:
		print "usage: %s <URL>" % (sys.argv[0])
		return

	app = QApplication(sys.argv)
	myapp = Session(sys.argv[1])
	sys.exit(app.exec_())

if __name__ == "__main__":
	main()
