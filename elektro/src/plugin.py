#
# Power Save Plugin by gutemine
# Rewritten by Morty (morty@gmx.net)
# Profiles, HDD, IP, NAS Mod by joergm6
# No deep standby on network activity by betonme
# Check for sleep and show message on going to idle mode by Sven H
#
# Deep standby will be called sleep. Normal standby will be named standby!
# All calculations are in the local timezone, or in the relative Timezone.
# In the relative timezone the day starts at "nextday". If it is before nextday the last day will be used.
#

from __future__ import print_function

from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Components.ConfigList import ConfigListScreen
from Screens.MessageBox import MessageBox
from Screens.Console import Console
from Components.ActionMap import ActionMap
from Components.Button import Button
from Components.Harddisk import harddiskmanager
from Components.Sources.StaticText import StaticText
from Components.config import configfile, getConfigListEntry, \
	ConfigYesNo, ConfigText, ConfigClock, ConfigNumber, ConfigSelection, \
	config, ConfigSubsection, ConfigSubDict, ConfigIP, ConfigInteger
from Tools import Notifications
from enigma import eTimer
from RecordTimer import RecordTimerEntry
import NavigationInstance
import ping
import subprocess
from time import localtime, strftime, time, gmtime, sleep
from six.moves import range

# Globals
pluginPrintname = "[Elektro]"
debug = False # If set True, plugin will print some additional status info to track logic flow
session = None
ElektroWakeUpTime = -1
elektro_pluginversion = "3.4.7"
elektrostarttime = 60
elektroShutdownThreshold = 60 * 20
gDoElektro = None

def elektro_print(*args):
	print(pluginPrintname, " ".join(map(str, args)))

#Configuration
if debug:
	elektro_print("Setting config defaults")
config.plugins.elektro = ConfigSubsection()
config.plugins.elektro.nextday = ConfigClock(default = ((6 * 60 + 0) * 60) )
config.plugins.elektro.nextday2 = ConfigClock(default = ((6 * 60 + 0) * 60) )
config.plugins.elektro.profile = ConfigSelection(choices = [("1", "Profile 1"), ("2", "Profile 2")], default = "1")
config.plugins.elektro.profileShift = ConfigYesNo(default = False)

config.plugins.elektro.sleep = ConfigSubDict()
for i in range(7):
	config.plugins.elektro.sleep[i] = ConfigClock(default = ((1 * 60 + 0) * 60) )

config.plugins.elektro.wakeup = ConfigSubDict()
for i in range(7):
	config.plugins.elektro.wakeup[i] = ConfigClock(default = ((9 * 60 + 0) * 60) )

config.plugins.elektro.sleep2 = ConfigSubDict()
for i in range(7):
	config.plugins.elektro.sleep2[i] = ConfigClock(default = ((1 * 60 + 0) * 60) )

config.plugins.elektro.wakeup2 = ConfigSubDict()
for i in range(7):
	config.plugins.elektro.wakeup2[i] = ConfigClock(default = ((9 * 60 + 0) * 60) )

config.plugins.elektro.ip = ConfigSubDict()
for i in range(10):
	config.plugins.elektro.ip[i] = ConfigIP(default = [0, 0, 0, 0])

config.plugins.elektro.name = ConfigText(default = _("Elektro Power Save"), fixed_size = False, visible_width = 20)
config.plugins.elektro.description = ConfigText(default = _("Automatically shut down to deep standby"), fixed_size = False, visible_width = 80)
config.plugins.elektro.menu = ConfigSelection(default = "plugin", choices = [("plugin", _("Plugin menu")), ("extensions", _("Extensions menu"))])
config.plugins.elektro.enable = ConfigYesNo(default = False)
config.plugins.elektro.standbyOnBoot = ConfigYesNo(default = False)
config.plugins.elektro.standbyOnManualBoot = ConfigYesNo(default = True)
config.plugins.elektro.checkSleepAfterManualBoot = ConfigYesNo(default = False)
config.plugins.elektro.checkSleepOnIdle = ConfigYesNo(default = True)
config.plugins.elektro.nextwakeup = ConfigNumber(default = 0)
config.plugins.elektro.force = ConfigYesNo(default = False)
config.plugins.elektro.dontwakeup = ConfigYesNo(default = False)
config.plugins.elektro.holiday = ConfigYesNo(default = False)
config.plugins.elektro.hddsleep = ConfigYesNo(default = False)
config.plugins.elektro.netsleep = ConfigYesNo(default = False)
config.plugins.elektro.nfssleep = ConfigYesNo(default = False)
config.plugins.elektro.IPenable = ConfigYesNo(default = False)
config.plugins.elektro.deepstandby_wakeup_time = ConfigInteger(default = 0)

config.plugins.elektro.NASenable = ConfigSelection(choices = [("false", "no"), ("true", "yes"), ("1", _("yes, Profile 1")), ("2", _("yes, Profile 2"))], default="false")
config.plugins.elektro.NASname = ConfigText(default = "", fixed_size = False, visible_width = 50)
config.plugins.elektro.NASuser = ConfigText(default = "", fixed_size = False, visible_width = 50)
config.plugins.elektro.NASpass = ConfigText(default = "", fixed_size = False, visible_width = 50)
config.plugins.elektro.NAScommand = ConfigText(default = "poweroff", fixed_size = False, visible_width = 50)
config.plugins.elektro.NASport = ConfigNumber(default = 23)
config.plugins.elektro.NASwait = ConfigYesNo(default = False)

weekdays = [
	_("Monday"),
	_("Tuesday"),
	_("Wednesday"),
	_("Thursday"),
	_("Friday"),
	_("Saturday"),
	_("Sunday"),
	]


def NASpowerdown(Nname,Nuser,Npass,Ncommand,Nport):
	from telnetlib import Telnet
	if Nname == "":
		return _("no Name")
	l=_("Connection Error")
	try:
		tn = Telnet(Nname, Nport, 5)
		l=""
		if Nuser != "":
			l = l + tn.expect(['ogin:','sername'],10)[2]
			l = l + tn.read_very_lazy()
			tn.write('%s\r' % Nuser)
		if Npass != "":
			l = l + tn.read_until('assword:',10)
			l = l + tn.read_very_lazy()
			tn.write('%s\r' % Npass)
		l = l + tn.expect(['#',">"],10)[2]
		l = l + tn.read_very_lazy()
		tn.write('%s\r' % Ncommand)
		l = l + tn.expect(['#',">"],20)[2]
		l = l + tn.read_very_lazy()
		if config.plugins.elektro.NASwait.value == True:
			tt = time() + 90
			l = l + "\n waiting...\n"
			while tt>time() and ping.doOne(Nname,1) != None:
				sleep(2)
		tn.write('exit\r')
		l = l + tn.expect(['#',">"],5)[2]
		l = l + tn.read_very_lazy()
		tn.close()
	finally:
		return l

#internal ping without external module
def ping_doOne(server='example.com', timeout=1.0, wait_sec=1, count=1):
	cmd = "timeout {} ping -c {} -W {} {}".format(timeout, count, wait_sec, server).split(' ')
	try:
		output = subprocess.check_output(cmd).decode().strip()
		lines = output.split("\n")
		loss = lines[-2].split(',')[2].split()[0]
		timing = lines[-1].split()[3].split('/')
		return {
			'type': 'rtt',
			'min': timing[0],
			'avg': timing[1],
			'max': timing[2],
			'loss': loss,
		}
	except Exception as e:
		return None


def autostart(reason, **kwargs):
	global session
	if reason == 0 and "session" in kwargs:
		session = kwargs["session"]
		session.open(DoElektro)

def getNextWakeup():
	global ElektroWakeUpTime

	wakeuptime = 0
	now = time()
	elektro_print("Now realtime:", strftime("%a, %H:%M:%S", localtime(now)))

	if ElektroWakeUpTime > now:
		elektro_print("Will wake up at realtime:", strftime("%a, %H:%M:%S", localtime(ElektroWakeUpTime)))
		wakeuptime = ElektroWakeUpTime

	config.plugins.elektro.deepstandby_wakeup_time.value = wakeuptime
	config.plugins.elektro.deepstandby_wakeup_time.save()

	return wakeuptime or -1

def main(session,**kwargs):
	try:
	 	session.open(Elektro)
	except:
		elektro_print("Pluginexecution failed")

def Plugins(**kwargs):
	if debug:
		elektro_print("Setting entry points")
	list = [
		PluginDescriptor(
			name = config.plugins.elektro.name.value,
			description = config.plugins.elektro.description.value + " " + _("Ver.") + " " + elektro_pluginversion,
			where = [PluginDescriptor.WHERE_SESSIONSTART, PluginDescriptor.WHERE_AUTOSTART],
			fnc = autostart,
			wakeupfnc = getNextWakeup)
		]
	if config.plugins.elektro.menu.value == "plugin":
		list.append (PluginDescriptor(
			name = config.plugins.elektro.name.value,
			description = config.plugins.elektro.description.value + " " + _("Ver.") + " " + elektro_pluginversion,
			where = PluginDescriptor.WHERE_PLUGINMENU,
			icon = "elektro.png",
			fnc=main)
		)
	else:
		list.append (PluginDescriptor(
			name = config.plugins.elektro.name.value,
			description = config.plugins.elektro.description.value + " " + _("Ver.") + " " + elektro_pluginversion,
			where = PluginDescriptor.WHERE_EXTENSIONSMENU,
			fnc=main)
		)

	return list


class ElektroProfile(ConfigListScreen,Screen):
	skin = """
			<screen position="center,120" size="820,520" title="Elektro Power Save Profile Times">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40" alphatest="on" />
			<widget name="key_red" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget name="key_green" position="210,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<eLabel position="10,50" size="800,1" backgroundColor="grey" />
			<widget name="config" position="10,60" size="800,450" enableWrapAround="1" scrollbarMode="showOnDemand" />
		</screen>"""

	def __init__(self, session, args = 0):
		self.session = session
		Screen.__init__(self, session)

		self.list = []

		for i in range(7):
			self.list.append(getConfigListEntry(" 1. " + weekdays[i] + ": " + _("Wakeup"), config.plugins.elektro.wakeup[i]))
			self.list.append(getConfigListEntry(" 1. " + weekdays[i] + ": " + _("Sleep"), config.plugins.elektro.sleep[i]))
		self.list.append(getConfigListEntry(" 1. " + _("Next day starts at"), config.plugins.elektro.nextday,
			_("If the box is supposed to enter deep standby e.g. monday night at 1 AM, it actually is already tuesday. To enable this anyway, differing next day start time can be specified here.")))
		for i in range(7):
			self.list.append(getConfigListEntry(" 2. " + weekdays[i] + ": " + _("Wakeup"), config.plugins.elektro.wakeup2[i]))
			self.list.append(getConfigListEntry(" 2. " + weekdays[i] + ": " + _("Sleep"), config.plugins.elektro.sleep2[i]))
		self.list.append(getConfigListEntry(" 2. " + _("Next day starts at"), config.plugins.elektro.nextday2,
			_("If the box is supposed to enter deep standby e.g. monday night at 1 AM, it actually is already tuesday. To enable this anyway, differing next day start time can be specified here.")))

		ConfigListScreen.__init__(self, self.list)

		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("Ok"))
		self["setupActions"] = ActionMap(["SetupActions", "ColorActions"],
		{
			"red": self.cancel,
			"green": self.save,
			"save": self.save,
			"cancel": self.cancel,
			"ok": self.save,
		}, -2)

	def save(self):
		for x in self["config"].list:
			x[1].save()
		self.close(False,self.session)

	def cancel(self):
		for x in self["config"].list:
			x[1].cancel()
		self.close(False,self.session)


class ElektroIP(ConfigListScreen,Screen):
	skin = """
			<screen position="center,120" size="820,520" title="Elektro Power Save IP Addresses to wait">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40" alphatest="on" />
			<widget name="key_red" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget name="key_green" position="210,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<eLabel position="10,50" size="800,1" backgroundColor="grey" />
			<widget name="config" position="10,60" size="800,450" enableWrapAround="1" scrollbarMode="showOnDemand" />
		</screen>"""

	def __init__(self, session, args = 0):
		self.session = session
		Screen.__init__(self, session)

		self.list = []

		for i in range(10):
			self.list.append(getConfigListEntry(_("IP Address") , config.plugins.elektro.ip[i]))

		ConfigListScreen.__init__(self, self.list)

		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("Ok"))
		self["setupActions"] = ActionMap(["SetupActions", "ColorActions"],
		{
			"red": self.cancel,
			"green": self.save,
			"save": self.save,
			"cancel": self.cancel,
			"ok": self.save,
		}, -2)

	def save(self):
		for x in self["config"].list:
			x[1].save()
		self.close(False,self.session)

	def cancel(self):
		for x in self["config"].list:
			x[1].cancel()
		self.close(False,self.session)


class ElektroNASrun(Screen):
	skin = """
		<screen name="ElektroNASrun" position="center,120" size="820,520" title="Powerdown...">
		<widget source="TextTest" render="Label" position="10,10" size="800,500" font="Regular;20" />
		</screen>"""

	def __init__(self, session, args = 0):
		self.session = session
		Screen.__init__(self, session)
		self["TextTest"] = StaticText()
		self["TextTest"].setText(_("please wait..."))
		self.timer = eTimer()
		self.timer_conn = self.timer.timeout.connect(self.DoNASrun)
		self.timer.start(1000, True)

		self["actions"] = ActionMap(["OkCancelActions"],
		{
			"ok": self.cancel,
			"cancel": self.cancel
		}, -1)

	def cancel(self):
		self.close(False,self.session)

	def DoNASrun(self):
		ret = NASpowerdown(config.plugins.elektro.NASname.value, config.plugins.elektro.NASuser.value, config.plugins.elektro.NASpass.value, config.plugins.elektro.NAScommand.value, config.plugins.elektro.NASport.value)
		self["TextTest"].setText(ret)


class ElektroNAS(ConfigListScreen,Screen):
	skin = """
			<screen name="ElektroNAS" position="center,120" size="820,520" title="Elektro Power Save IP Telnet - Poweroff">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="410,5" size="200,40" alphatest="on" />
			<widget name="key_red" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget name="key_green" position="210,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget name="key_yellow" position="410,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<eLabel position="10,50" size="800,1" backgroundColor="grey" />
			<widget name="config" position="10,60" size="800,450" enableWrapAround="1" scrollbarMode="showOnDemand" />
		</screen>"""

	def __init__(self, session, args = 0):
		self.session = session
		Screen.__init__(self, session)

		self.list = []
		self.list.append(getConfigListEntry(_("NAS/Server Name or IP"), config.plugins.elektro.NASname))
		self.list.append(getConfigListEntry(_("Username"), config.plugins.elektro.NASuser))
		self.list.append(getConfigListEntry(_("Password"), config.plugins.elektro.NASpass))
		self.list.append(getConfigListEntry(_("Command [poweroff, shutdown -h,...]"), config.plugins.elektro.NAScommand))
		self.list.append(getConfigListEntry(_("Telnet Port"), config.plugins.elektro.NASport))
		self.list.append(getConfigListEntry(_("Waiting until poweroff"), config.plugins.elektro.NASwait))

		ConfigListScreen.__init__(self, self.list)

		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("Ok"))
		self["key_yellow"] = Button(_("Run"))
		self["setupActions"] = ActionMap(["SetupActions", "ColorActions"],
		{
			"red": self.cancel,
			"green": self.save,
			"yellow": self.run,
			"save": self.save,
			"cancel": self.cancel,
			"ok": self.save,
		}, -2)

	def run(self):
		self.session.open(ElektroNASrun)

	def save(self):
		for x in self["config"].list:
			x[1].save()
		self.close(False,self.session)

	def cancel(self):
		for x in self["config"].list:
			x[1].cancel()
		self.close(False,self.session)


class Elektro(ConfigListScreen,Screen):
	skin = """
		<screen name ="Elektro" position="center,120" size="820,520" title="Elektro Power Save">
			<ePixmap pixmap="skin_default/buttons/red.png" position="10,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="210,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/yellow.png" position="410,5" size="200,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/blue.png" position="610,5" size="200,40" alphatest="on" />
			<widget name="key_red" position="10,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget name="key_green" position="210,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget name="key_yellow" position="410,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#a08500" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<widget name="key_blue" position="610,5" size="200,40" zPosition="1" font="Regular;20" halign="center" valign="center" backgroundColor="#18188b" transparent="1" shadowColor="black" shadowOffset="-2,-2" />
			<eLabel position="10,50" size="800,1" backgroundColor="grey" />
			<widget name="config" position="10,55" size="800,330" enableWrapAround="1" scrollbarMode="showOnDemand" />
			<eLabel position="10,390" size="800,1" backgroundColor="grey" />
			<widget source="help" render="Label" position="10,395" size="800,115" font="Regular;21" halign="center" valign="center"/>
		</screen>"""

	def __init__(self, session, args = 0):
		self.session = session
		Screen.__init__(self, session)
		if debug:
			elektro_print("Displays config screen")

		self.onChangedEntry = []

		self.list = [
			getConfigListEntry(_("Active Time Profile"), config.plugins.elektro.profile,
				_("The active Time Profile is (1 or 2).")),
			getConfigListEntry(_("Enable Elektro Power Save"),config.plugins.elektro.enable,
				_("Unless this is enabled, this plugin won't run automatically.")),
			getConfigListEntry(_("Use both profiles alternately"), config.plugins.elektro.profileShift,
				_("Both profiles are used alternately. When shutting down the other profile is enabled. This allows two time cycles per day. Do not overlap the times.")),
			getConfigListEntry(_("Standby on boot"), config.plugins.elektro.standbyOnBoot,
				_("Puts the box in standby mode after boot.")),
			getConfigListEntry(_("Standby on manual boot"), config.plugins.elektro.standbyOnManualBoot,
				_("Whether to put the box in standby when booted manually. On manual boot the box will not go to standby before the next deep standby interval starts, even if this option is set. This option is only active if 'Standby on boot' option is set, too.")),
			getConfigListEntry(_("check for sleep directly after manual boot"), config.plugins.elektro.checkSleepAfterManualBoot,	_("If set to 'yes' the box will check to deepstandby directly after manual boot if sleep time is already reached. If set to 'no' (default) the box will check to deepstandby only if the next deepstandby interval starts (after next wakeuptime)")),
			getConfigListEntry(_("check for sleep directly on going to idle mode"), config.plugins.elektro.checkSleepOnIdle,
				_("Check for sleep directly on going to idle mode and show a message if want to go to sleep.")),
			getConfigListEntry(_("Force sleep (even when not in standby)"), config.plugins.elektro.force,
				_("Forces deep standby, even when not in standby mode. Scheduled recordings remain unaffected.")),
			getConfigListEntry(_("Avoid deep standby when HDD is active, e.g. for FTP"), config.plugins.elektro.hddsleep,
				_("Wait for the HDD to enter sleep mode. Depending on the configuration this can prevent the box entirely from entering deep standby mode.")),
			getConfigListEntry(_("Avoid deep standby on network activity, e.g. for Streaming"), config.plugins.elektro.netsleep,
				_("Wait for the network to enter sleep mode.") + " " + _("(tcp/udp)")),
			getConfigListEntry(_("Avoid deep standby on nfs-read activity, e.g. for Streaming"), config.plugins.elektro.nfssleep,
				_("Wait for no nfs-read-activity to enter sleep mode.")),
			getConfigListEntry(_("Check IPs (press OK to edit)"), config.plugins.elektro.IPenable,
				_("This list of IP addresses is checked. Elektro waits until addresses no longer responds to ping.")),
			getConfigListEntry(_("NAS Poweroff (press OK to edit)"), config.plugins.elektro.NASenable,
				_("A NAS/Server can be shut down. Is required activated Telnet.")),
			getConfigListEntry(_("Don't wake up"), config.plugins.elektro.dontwakeup,
				_("Do not wake up at the end of next deep standby interval.")),
			getConfigListEntry(_("Holiday mode (experimental)"), config.plugins.elektro.holiday,
				_("The box always enters deep standby mode, except for recording.")),
			getConfigListEntry(_("Show in"), config.plugins.elektro.menu,
				_("Specify whether plugin shall show up in plugin menu or extensions menu (needs GUI restart)")),
			getConfigListEntry(_("Name"), config.plugins.elektro.name,
				_("Specify plugin name to be used in menu (needs GUI restart).")),
			getConfigListEntry(_("Description"), config.plugins.elektro.description,
				_("Specify plugin description to be used in menu (needs GUI restart).")),
			]

		ConfigListScreen.__init__(self, self.list, session = session, on_change = self.changed)

		def selectionChanged():
			if self["config"].current:
				self["config"].current[1].onDeselect(self.session)
			self["config"].current = self["config"].getCurrent()
			if self["config"].current:
				self["config"].current[1].onSelect(self.session)
			for x in self["config"].onSelectionChanged:
				x()

		self["config"].selectionChanged = selectionChanged
		self["config"].onSelectionChanged.append(self.configHelp)

		self["key_red"] = Button(_("Cancel"))
		self["key_green"] = Button(_("Ok"))
		self["key_yellow"] = Button(_("Help"))
		self["key_blue"] = Button(_("Times"))
		self["help"] = StaticText()

		self["setupActions"] = ActionMap(["SetupActions", "ColorActions"],
		{
			"red": self.keyCancel,
			"green": self.keySave,
			"yellow": self.help,
			"blue": self.profile,
			"save": self.keySave,
			"cancel": self.keyCancel,
			"ok": self.keyOK,
		}, -2)

		# Trigger change
		self.changed()

		self.onLayoutFinish.append(self.setCustomTitle)

	def setCustomTitle(self):
		self.setTitle(config.plugins.elektro.name.value + " " + _("Ver.") + " " + elektro_pluginversion)

	def configHelp(self):
		cur = self["config"].getCurrent()
		self["help"].text = cur[2]

	def keyOK(self):
		ConfigListScreen.keyOK(self)
		sel = self["config"].getCurrent()[1]
		if sel == config.plugins.elektro.IPenable:
			self.session.open(ElektroIP)
		if sel == config.plugins.elektro.NASenable:
			self.session.open(ElektroNAS)

	def changed(self):
		for x in self.onChangedEntry:
			try:
				x()
			except Exception:
				pass

	def getCurrentEntry(self):
		return self["config"].getCurrent()[0]

	def getCurrentValue(self):
		return str(self["config"].getCurrent()[1].getText())

	def help(self):
		self.session.open(Console,_("Showing Elektro readme.txt"),["cat /usr/lib/enigma2/python/Plugins/Extensions/Elektro/%s" % _("readme.txt")])

	def profile(self):
		self.session.open(ElektroProfile)


class DoElektro(Screen):
	skin = """ <screen position="center,center" size="300,300" title="Elektro Plugin Menu" > </screen>"""

	def __init__(self,session):
		Screen.__init__(self,session)

		elektro_print("Starting up Version", elektro_pluginversion)

		self.session = session
		
		global gDoElektro
		gDoElektro = self

		# Make sure wakeup time is set.
		self.setNextWakeuptime()

		# If we didn't wake up by a timer we don't want to go to sleep any more.
		# Unforturnately it is not possible to use getFPWasTimerWakeup()
		# Therfore we're checking wheter there is a recording starting within
		# the next five min

		automatic_wakeup = self.session.nav.wasTimerWakeup() # woken by any timer
		elektro_wakeup = automatic_wakeup and config.plugins.elektro.deepstandby_wakeup_time.value == config.misc.prev_wakeup_time.value
		record_wakeup = automatic_wakeup and config.misc.prev_wakeup_time.value and config.misc.prev_wakeup_time_type.value == 0

		self.dontsleep = False

		#Let's assume we got woken up manually
		timerWakeup = elektro_wakeup or record_wakeup

		# If the start was a manual wakeup: Don't go to sleep
		if timerWakeup == False:
			#check sleep after manual boot - Sven H
			if config.plugins.elektro.checkSleepAfterManualBoot.value == False:
				self.dontsleep = True
				elektro_print("check for sleep after manual boot on next sleeptime (after next wakeuptime)")
			else:
				elektro_print("check for sleep directly after manual boot")

		#Check whether we should try to sleep:
		trysleep = config.plugins.elektro.standbyOnBoot.value

		#Don't go to sleep when this was a manual wakeup and the box shouldn't go to standby
		if timerWakeup == False and config.plugins.elektro.standbyOnManualBoot.value == False:
			trysleep = False

		#if waken up by timer and configured ask whether to go to sleep.
		if trysleep:
			elektro_print("add standby notification", Standby)
			Notifications.AddNotificationWithID("Standby", Standby)

		self.TimerSleep = eTimer()
		self.TimerSleep_conn = self.TimerSleep.timeout.connect(self.CheckElektro)
		self.TimerSleep.startLongTimer(elektrostarttime)
		elektro_print("Start timer for sleep-check")
		if debug:
			elektro_print("Translation test:", _("Standby on boot"))

		#set the last_nfsread-value
		self.last_nfsread = "0"
		
		config.misc.standbyCounter.addNotifier(self.onStandbyCounter, initial_call = False)
		
	def onStandbyCounter(self,configElement):
		elektro_print("onStandby")
		Screens.Standby.inStandby.onClose.append(self.leaveStandby)

	def leaveStandby(self):
		elektro_print("leaveStandby")
		self.dontsleep = False

	def clkToTime(self, clock):
		return ( (clock.value[0]) * 60 + (int)(clock.value[1]) ) * 60

	def getTime(self):
		ltime = localtime();
		return ( (int)(ltime.tm_hour) * 60 + (int)(ltime.tm_min) ) * 60

	def getPrintTime(self, secs):
		return strftime("%H:%M:%S", gmtime(secs))

	# This function converts the time into the relative Timezone where the day starts at "nextday"
	# This is done by substracting nextday from the current time. Negative times are corrected using the mod-operator
	def getReltime(self, time):
		if config.plugins.elektro.profile.value == "1":
			nextday = self.clkToTime(config.plugins.elektro.nextday)
		else:
			nextday = self.clkToTime(config.plugins.elektro.nextday2)
		return (time - nextday) % (24 * 60 * 60)

	def setNextWakeuptime(self):
		# Do not set a wakeup time if
		# - Elektro isn't enabled
		# - Elektro shouldn't wake up
		# - Holiday mode is turned on
		if ((config.plugins.elektro.enable.value == False)
			or (config.plugins.elektro.dontwakeup.value == True)
			or config.plugins.elektro.holiday.value == True):
			global ElektroWakeUpTime
			ElektroWakeUpTime = -1
			return

		time_s = self.getTime()
		ltime = localtime()
		if config.plugins.elektro.profile.value == "1":
			config_wakeup = config.plugins.elektro.wakeup
			config_sleep = config.plugins.elektro.sleep
			config_nextday = config.plugins.elektro.nextday
		else:
			config_wakeup = config.plugins.elektro.wakeup2
			config_sleep = config.plugins.elektro.sleep2
			config_nextday = config.plugins.elektro.nextday2

		#elektro_print("Nextday:", time.ctime(self.clkToTime(config.plugins.elektro.nextday)))
		# If it isn't past next-day time we need yesterdays settings
		#
		if time_s < self.clkToTime(config_nextday):
			day = (ltime.tm_wday - 1) % 7
		else:
			day = ltime.tm_wday

		# Check whether we wake up today or tomorrow
		# Relative Time is needed for this
		time_s = self.getReltime(time_s)
		wakeuptime = self.getReltime(self.clkToTime(config_wakeup[day]))

		# Lets see if we already woke up today
		if wakeuptime < time_s:
			#yes we did -> Next wakeup is tomorrow
			if debug:
				elektro_print("Wakeup tomorrow")
			day = (day + 1) % 7
			wakeuptime = self.getReltime(self.clkToTime(config_wakeup[day]))

		# Tomorrow we'll wake up erly-> Add a full day.
		if wakeuptime < time_s:
			wakeuptime = wakeuptime + 24 * 60 * 60

		# The next wakeup will be in wakupin seconds
		wakeupin = wakeuptime - time_s

		# Now add this to the current time to get the wakeuptime
		wakeuptime = (int)(time()) + wakeupin

		#Write everything to the global variable
		ElektroWakeUpTime = wakeuptime

	def CheckElektro(self, checkOnly=False):
		# first set the next wakeuptime - it would be much better to call that function on sleep. This will be a todo!
		self.setNextWakeuptime()

		#convert to seconds
		time_s = self.getTime()
		ltime = localtime()
		if config.plugins.elektro.profile.value == "1":
			config_wakeup = config.plugins.elektro.wakeup
			config_sleep = config.plugins.elektro.sleep
			config_nextday = config.plugins.elektro.nextday
		else:
			config_wakeup = config.plugins.elektro.wakeup2
			config_sleep = config.plugins.elektro.sleep2
			config_nextday = config.plugins.elektro.nextday2

		#Which day is it? The next day starts at nextday
		if debug:
			elektro_print("wday 1:", str(ltime.tm_wday))
		if time_s < self.clkToTime(config_nextday):
			day = (ltime.tm_wday - 1) % 7
		else:
			day = ltime.tm_wday
		if debug:
			elektro_print("wday 2:", str(day))

		#Let's get the day
		wakeuptime = lwakeuptime = self.clkToTime(config_wakeup[day])
		sleeptime = lsleeptime = self.clkToTime(config_sleep[day])
		ltime_s = time_s

		elektro_print("Profile:", config.plugins.elektro.profile.value)
		elektro_print("Nextday:", self.getPrintTime(self.clkToTime(config.plugins.elektro.nextday)))
		elektro_print("Current time:", self.getPrintTime(time_s))
		elektro_print("Wakeup time:", self.getPrintTime(wakeuptime))
		elektro_print("Sleep time:", self.getPrintTime(sleeptime))

		#convert into relative Times
		time_s = self.getReltime(time_s)
		wakeuptime = self.getReltime(wakeuptime)
		sleeptime = self.getReltime(sleeptime)

		if debug:
			elektro_print("Current Rel-time:", self.getPrintTime(time_s))
			elektro_print("Wakeup Rel-time:", self.getPrintTime(wakeuptime))
			elektro_print("Sleep Rel-time:", self.getPrintTime(sleeptime))

		#let's see if we should be sleeping
		trysleep = False
		if time_s < (wakeuptime - elektroShutdownThreshold): # Wakeup is in the future -> sleep!
			trysleep = True
			elektro_print("try sleep:", self.getPrintTime(ltime_s), " <", self.getPrintTime(lwakeuptime))
		if sleeptime < time_s : #Sleep is in the past -> sleep!
			trysleep = True
			elektro_print("try Sleep:", self.getPrintTime(lsleeptime), " <", self.getPrintTime(ltime_s))

		#We are not tying to go to sleep anymore -> maybe go to sleep again the next time
		if trysleep == False:
			elektro_print("don't try sleep -> maybe go to sleep again the next time")
			self.dontsleep = False

		#The User aborted to got to sleep -> Don't go to sleep.
		if self.dontsleep:
			elektro_print("don't sleep - user aborted to got to sleep")
			trysleep = False

		# If we are in holydaymode we should try to got to sleep anyway
		# This should be set after self.dontsleep has been handled
		if config.plugins.elektro.holiday.value:
			elektro_print("sleep - we are in holiday mode")
			trysleep = True

		# We are not enabled -> Dont go to sleep (This could have been catched earlier!)
		if config.plugins.elektro.enable.value == False:
			elektro_print("don't sleep - Elektro not activated")
			trysleep = False

		# Only go to sleep if we are in standby or sleep is forced by settings
		if trysleep == True and not ((Screens.Standby.inStandby) or (config.plugins.elektro.force.value == True)) and checkOnly==False:
			elektro_print("don't sleep - not in standby or sleep not forced by settings")
			trysleep = False

		# wakeuptime coming up in a short while - Sven H
		# avoid deepstandby on recordtimer-end with auto-afterevent, if wakeuptime after recordstart
		if wakeuptime > 0 and (wakeuptime - time_s) < elektroShutdownThreshold and NavigationInstance.instance.wasTimerWakeup() and Screens.Standby.inStandby and config.misc.standbyCounter.value == 1 and config.misc.isNextRecordTimerAfterEventActionAuto.value:
			elektro_print("wakeuptime coming up in a short while: set isNextRecordTimerAfterEventActionAuto to False")
			config.misc.isNextRecordTimerAfterEventActionAuto.value = False

		# No Sleep while recording
		if trysleep == True and self.session.nav.RecordTimer.isRecording():
			elektro_print("don't sleep - current recording")
			trysleep = False

		# No Sleep on Online IPs - joergm6
		if trysleep == True and config.plugins.elektro.IPenable.value == True:
			for i in range(10):
				ip = "%d.%d.%d.%d" % tuple(config.plugins.elektro.ip[i].value)
				if ip != "0.0.0.0":
					#if ping.doOne(ip,0.1) != None:
					#new ping-check - select.select crash with fd-count > 1024
					if ping_doOne(ip,0.2) != None:
						elektro_print("don't sleep - ip online:", ip)
						trysleep = False
						break

		# No Sleep on HDD running
		if trysleep == True and (config.plugins.elektro.hddsleep.value == True) and (harddiskmanager.HDDCount() > 0):
			hddlist = harddiskmanager.HDDList()
			#new code by Sven H
			for hdd in hddlist:
				#print("[Elektro] ", hdd[0], hdd[1].bus_description(), hdd[1].isSleeping())
				if hdd[1].bus_description() == "SATA" and not hdd[1].isSleeping():
					elektro_print("don't sleep - HDD is active:", hdd[0])
					trysleep = False

		# No Sleep on network activity - betonme
		if trysleep == True and (config.plugins.elektro.netsleep.value == True) and (harddiskmanager.HDDCount() > 0):
			with open("/proc/net/tcp", 'r') as f:
				lines = f.readlines()
				lines.pop(0)
				for line in lines:
					content = line.split()
					if content[3] == "01":
						# Connection established
						elektro_print("don't sleep - tcp-Connection established")
						trysleep = False
						break
			with open("/proc/net/udp", 'r') as f:
				lines = f.readlines()
				lines.pop(0)
				for line in lines:
					content = line.split()
					if content[3] == "01":
						# Connection established
						elektro_print("don't sleep - udp-Connection established")
						trysleep = False
						break

		# No Sleep on nfs-read activity - Sven H
		if trysleep == True and (config.plugins.elektro.nfssleep.value == True):
			with open("/proc/net/rpc/nfsd", 'r') as f:
				lines = f.readlines()
				for line in lines:
					content = line.split()
					if content[0] == "io":
						current_nfsread = content[1]
						#elektro_print("nfs-read activity - last, current", self.last_nfsread, current_nfsread)
						if (current_nfsread != self.last_nfsread):
							elektro_print("don't sleep because current nfs-read activity")
							trysleep = False
						self.last_nfsread = current_nfsread
						break

		# Will there be a recording in a short while?
		nextRecTime = self.session.nav.RecordTimer.getNextRecordingTime()
		if trysleep == True and (nextRecTime > 0) and (nextRecTime - (int)(time()) < elektroShutdownThreshold):
			elektro_print("don't sleep - there be a recording in a short while")
			trysleep = False

		if checkOnly:
			return trysleep
		
		# Looks like there really is a reason to go to sleep -> Lets try it!
		if trysleep:
			try:
				if Screens.Standby.inStandby:
					#in DreamOS messageboxes/choiceboxes are no longer displayed on idle mode
					elektro_print("on idle mode go directly to sleep")
					self.DoElektroSleep(True)
				else:
					elektro_print("show message - 'go to sleep now?'")
					self.session.openWithCallback(self.DoElektroSleep, MessageBoxElektro, _("Elektro-Plugin has checked and want to go to sleep.") + "\n\n" + _("Go to sleep now?") + "\n" + _("(Press Exit to cancel)"), type = MessageBox.TYPE_YESNO,timeout = 60, title = config.plugins.elektro.name.value)
			except:
				#call the timer and try again
				elektro_print("error on go to sleep - start timer and try again")
				self.TimerSleep.startLongTimer(elektrostarttime)
		
		else:
			#set Timer, which calls this function again.
			self.TimerSleep.startLongTimer(elektrostarttime)

	def DoElektroSleep(self,retval):
		elektro_print("DoElektroSleep retval:", retval)
		if retval is None:
			#do nothing on cancel, don't restart the checktimer
			return
		config_NASenable = True if config.plugins.elektro.NASenable.value == config.plugins.elektro.profile.value else False
		if config.plugins.elektro.profileShift.value == True:
			config.plugins.elektro.profile.value = "1" if config.plugins.elektro.profile.value == "2" else "2"
			config.plugins.elektro.profile.save()
			self.setNextWakeuptime()
		if (retval):
			if not Screens.Standby.inTryQuitMainloop:
				if config.plugins.elektro.NASenable.value == "true" or config_NASenable:
					ret = NASpowerdown(config.plugins.elektro.NASname.value, config.plugins.elektro.NASuser.value, config.plugins.elektro.NASpass.value, config.plugins.elektro.NAScommand.value, config.plugins.elektro.NASport.value)
				configfile.save()
				if Screens.Standby.inStandby:
					RecordTimerEntry.TryQuitMainloop()
				else:
					Notifications.AddNotificationWithID("Shutdown", Screens.Standby.TryQuitMainloop, 1)
		else:
			# Dont try to sleep until next wakeup
			self.dontsleep = True
			#Start the timer again
			self.TimerSleep.startLongTimer(elektrostarttime)
			


# === overwrite Standby-Class to show shutdown-Message before going to idle mode ======
import Screens.Standby #Standby-Module
from Screens.Standby import Standby #Standby-Class

class StandbyElektro(Standby):
	def __init__(self, session):
		trysleep=False
		elektro_print("StandbyElektro_init checkSleepOnIdle", config.plugins.elektro.checkSleepOnIdle.value, Standby)
		if config.plugins.elektro.checkSleepOnIdle.value:
			gDoElektro.TimerSleep.stop()
			elektro_print("StandbyElektro Start CheckElektro")
			trysleep = gDoElektro.CheckElektro(checkOnly=True)
			if not trysleep:
				#restart the checktimer and try again next time on idle mode
				gDoElektro.TimerSleep.startLongTimer(elektrostarttime)
		if trysleep:
			elektro_print("StandbyElektro_init - trysleep:", trysleep)
			self.skin = """<screen position="0,0" size="0,0"/>"""
			Screen.__init__(self, session)
			self.onShown.append(self.show_elektro_message)
		else:
			elektro_print("Standby_init org - trysleep:", trysleep)
			Standby.__init__(self,session)
			self.skinName = "Standby"

	def show_elektro_message(self):
		self.onShown.remove(self.show_elektro_message)
		elektro_print("show message - 'go to sleep now?'")
		self.session.openWithCallback(self.elektro_message_callback, MessageBoxElektro, _("Elektro-Plugin has checked and want to go to sleep.") + "\n\n" + _("Go to sleep now?") + "\n" + _("(Press Exit to cancel)"), type = MessageBox.TYPE_YESNO, timeout = 30, title = config.plugins.elektro.name.value)

	def elektro_message_callback(self,retval):
		elektro_print("elektro_message_callback", retval)
		self.close()
		if retval is None:
			#do nothing on cancel, only restart the timer
			gDoElektro.TimerSleep.startLongTimer(elektrostarttime)
			return
		gDoElektro.DoElektroSleep(retval)
		if not retval:
			Notifications.AddNotificationWithID("Standby", Standby)

Screens.Standby.Standby = StandbyElektro
# === end overwrite Standby-Class =====================================


# === to use a MessageBox with return None on Exit-Key to cancel ======
class MessageBoxElektro(MessageBox):
	def __init__(self, session, text, type = MessageBox.TYPE_YESNO, timeout = -1, close_on_any_key = False, default = True, enable_input = True, msgBoxID = None, windowTitle = None, additionalActionMap=None, title = _("Message")):
		MessageBox.__init__(self, session, text, type = type, timeout = timeout, close_on_any_key = close_on_any_key, default = default, enable_input = enable_input, msgBoxID = msgBoxID, windowTitle = windowTitle, additionalActionMap = additionalActionMap, title = title)
		self.skinName = "MessageBox"
	
	def cancel(self):
		self.close(None)

