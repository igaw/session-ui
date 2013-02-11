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
import selinux
from functools import partial

from PyQt4 import uic
from PyQt4.QtCore import SIGNAL, SLOT, QObject, QTimer, QThread
from PyQt4.QtGui import *

import PyQt4.Qwt5 as Qwt
from PyQt4.Qwt5.anynumpy import *
import socket
import time

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

class WorkerThread(QThread):
	def __init__(self, sleep = 0.05):
		QThread.__init__(self)
		self.sleep = sleep

	def run(self):
		HOST, PORT = "hotel311.server4you.de", 9999
		data = 1000*"x"
		upload = 0
		download = 0

		while True:
			print self.sleep
			time.sleep(self.sleep)

			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			try:
				upload = len(data)
				sock.connect((HOST, PORT))
				sock.sendall(data + "\n")

				received = sock.recv(1024)
				download = len(received)
			finally:
				sock.close()

			self.emit(SIGNAL('update(int, int)'), upload, download)

class TrafficGenerator(QWidget):
	def __init__(self, parent=None):
		QWidget.__init__(self, parent)

		ui_class, widget_class = uic.loadUiType(get_resource_path('ui/trafficgenerator.ui'))
		self.ui = ui_class()
		self.ui.setupUi(self)

		self.worker = None

		self.x = arange(0, 30, 1)
		self.y = zeros(len(self.x))
		self.curve = Qwt.QwtPlotCurve("Some Data")
		self.curve.attach(self.ui.qwtPlot)

		self.ui.qwtPlot.setAxisTitle(Qwt.QwtPlot.xBottom, "Time (seconds)")
		self.ui.qwtPlot.setAxisTitle(Qwt.QwtPlot.yLeft, "Bytes")

		self.ui.slider.setRange(0, 1000, 10)
		self.ui.slider.setValue(50)

		self.connect(self.ui.pb_Start, SIGNAL('clicked()'), self.cb_Start)
		self.connect(self.ui.pb_Stop, SIGNAL('clicked()'), self.cb_Stop)
		self.connect(self.ui.pb_Close, SIGNAL('clicked()'), self.cb_Close)
		self.connect(self.ui.slider, SIGNAL('sliderMoved(double)'), self.cb_sleep)

	def cb_Start(self):
		if self.worker:
			return

		sleep = 0
		if self.ui.slider.value():
			sleep = self.ui.slider.value()/1000.0
		self.worker = WorkerThread(sleep)
		self.connect(self.worker, SIGNAL('update(int, int)'), self.cb_update)
		self.worker.start()

		self.timer = QTimer()
		self.connect(self.timer, SIGNAL('timeout()'), self.cb_timeout)
		self.timer.start(1000)

	def cb_Stop(self):
		if not self.worker:
			return

		self.timer.stop()
		self.timer = None
		self.worker.terminate()
		self.worker = None

	def cb_Close(self):
		self.cb_Stop()
		self.hide()

	def cb_sleep(self, value):
		if not self.worker:
			return
		if value == 0:
			self.worker.sleep = 0
		else:
			self.worker.sleep = value/1000.0


	def cb_update(self, upload, download):
		self.y[-1] += download

	def cb_timeout(self):
		self.curve.setData(self.x, self.y)
		self.ui.qwtPlot.replot()

		self.y = concatenate((self.y[1:], self.y[:1]), 1)
		self.y[-1] = 0

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

		self.connect(self.ui.pb_TrafficGenerator, SIGNAL('clicked()'), self.cb_TrafficGenerator)

		self.connect(self.ui.pb_SessionEnable, SIGNAL('clicked()'), self.cb_SessionEnable)
		self.connect(self.ui.pb_SessionDisable, SIGNAL('clicked()'), self.cb_SessionDisable)

		self.connect(self.ui.pb_Create, SIGNAL('clicked()'), self.cb_Create)
		self.connect(self.ui.pb_Destroy, SIGNAL('clicked()'), self.cb_Destroy)
		self.connect(self.ui.pb_Connect, SIGNAL('clicked()'), self.cb_Connect)
		self.connect(self.ui.pb_Disconnect, SIGNAL('clicked()'), self.cb_Disconnect)

		self.connect(self.ui.pb_Quit, SIGNAL('clicked()'), self.cb_Quit)

		self.connect(self.ui.le_SessionName, SIGNAL('editingFinished()'), self.cb_SessionName)

		self.connect(self.ui.le_AllowedBearers, SIGNAL('editingFinished()'), self.cb_AllowedBearers)
		self.connect(self.ui.le_ConnectionType, SIGNAL('editingFinished()'), self.cb_ConnectionType)


		self.notify = None
		self.notify_path = "/foo"
		self.ui.le_SessionName.setText(self.notify_path)

		self.bus = dbus.SystemBus()
		self.manager = None
		self.session = None
		self.traffic_generator = TrafficGenerator()

		try:
			self.bus.watch_name_owner('net.connman', self.connman_name_owner_changed)
		except dbus.DBusException, e:
			print e.get_dbus_message()
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
		except dbus.DBusException, e:
			print e.get_dbus_message()
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

	def reset(self):
		self.settings = {}
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
			if (self.session != None):
				self.session.Change(key, val)

	def cb_AllowedBearers(self):
		value = str(self.ui.le_AllowedBearers.displayText())
		self.session_change('AllowedBearers', value)

	def cb_ConnectionType(self):
		value = str(self.ui.le_ConnectionType.displayText())
		self.session_change('ConnectionType', value)

	def cb_Release(self):
		self.reset()

	def cb_SessionName(self):
		self.notify_path = str(self.ui.le_SessionName.displayText())

	def set_session_mode(self, enable):
		try:
			self.manager.SetProperty("SessionMode", enable)
		except dbus.DBusException, e:
			print e.get_dbus_message()

	def cb_TrafficGenerator(self):
		if self.traffic_generator.isVisible():
			self.traffic_generator.hide()
		else:
			self.traffic_generator.show()

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
		else:
			val = str(settings[key])

		return val

	def convert_type_to_dbus(self, key, value):
		val = None
		if key in  [ "AllowedBearers" ]:
			if value != None and len(value) > 0:
				val = dbus.Array(value.split(' '),
						 signature='s')
			else:
				val = dbus.Array(signature='s')
		elif key in [ "ConnectionType" ]:
			if value != None and len(value) > 0:
				val = dbus.String(str(value))
			else:
				val = dbus.String('')

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
			print e.get_dbus_message()

			if e.get_dbus_name() in ['net.connman.Error.AlreadyExists']:
				return

			if self.notify:
				self.notify.remove_from_connection(self.bus, self.notify_path)
				self.notify = None
				return

	def cb_Destroy(self):
		try:
			self.manager.DestroySession(self.session_path)

			self.reset()
		except dbus.DBusException, e:
			print e.get_dbus_message()

	def cb_Connect(self):
		try:
			self.session.Connect()
		except dbus.DBusException, e:
			print e.get_dbus_message()

	def cb_Disconnect(self):
		try:
			self.session.Disconnect()
		except dbus.DBusException, e:
			print e.get_dbus_message()

	def cb_Quit(self):
		sys.exit()

def main():
	print selinux.getcon()

	app = QApplication(sys.argv)
	myapp = Session()
	myapp.show()
	sys.exit(app.exec_())

if __name__ == "__main__":
	main()
