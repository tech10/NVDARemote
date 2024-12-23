import ctypes
from ctypes import POINTER, Structure, Union, c_long, c_ulong, wintypes

import api
import baseObject
import braille
import brailleInput
import globalPluginHandler
import scriptHandler
import vision

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2
MAPVK_VK_TO_VSC = 0
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENT_SCANCODE = 0x0008
KEYEVENTF_UNICODE = 0x0004

class MOUSEINPUT(Structure):
	_fields_ = (
		('dx', c_long),
		('dy', c_long),
		('mouseData', wintypes.DWORD),
		('dwFlags', wintypes.DWORD),
		('time', wintypes.DWORD),
		('dwExtraInfo', POINTER(c_ulong)),
	)

class KEYBDINPUT(Structure):
	_fields_ = (
		('wVk', wintypes.WORD),
		('wScan', wintypes.WORD),
		('dwFlags', wintypes.DWORD),
		('time', wintypes.DWORD),
		('dwExtraInfo', POINTER(c_ulong)),
	)

class HARDWAREINPUT(Structure):
	_fields_ = (
		('uMsg', wintypes.DWORD),
		('wParamL', wintypes.WORD),
		('wParamH', wintypes.WORD),
	)

class INPUTUnion(Union):
	_fields_ = (
		('mi', MOUSEINPUT),
		('ki', KEYBDINPUT),
		('hi', HARDWAREINPUT),
	)

class INPUT(Structure):
	_fields_ = (
		('type', wintypes.DWORD),
		('union', INPUTUnion))

class BrailleInputGesture(braille.BrailleDisplayGesture, brailleInput.BrailleInputGesture):

	def __init__(self, **kwargs):
		super().__init__()
		for key, value in kwargs.items():
			setattr(self, key, value)
		self.source="remote{}{}".format(self.source[0].upper(),self.source[1:])
		self.scriptPath=getattr(self,"scriptPath",None)
		self.script=self.findScript() if self.scriptPath else None

	def findScript(self):
		if not (isinstance(self.scriptPath,list) and len(self.scriptPath)==3):
			return None
		module,cls,scriptName=self.scriptPath
		focus = api.getFocusObject()
		if not focus:
			return None
		if scriptName.startswith("kb:"):
			# Emulate a key press.
			return scriptHandler._makeKbEmulateScript(scriptName)

		import globalCommands

		# Global plugin level.
		if cls=='GlobalPlugin':
			for plugin in globalPluginHandler.runningPlugins:
				if module==plugin.__module__:
					func = getattr(plugin, "script_%s" % scriptName, None)
					if func:
						return func

		# App module level.
		app = focus.appModule
		if app and cls=='AppModule' and module==app.__module__:
			func = getattr(app, "script_%s" % scriptName, None)
			if func:
				return func

		# Vision enhancement provider level
		for provider in vision.handler.getActiveProviderInstances():
			if isinstance(provider, baseObject.ScriptableObject):
				if cls=='VisionEnhancementProvider' and module==provider.__module__:
					func = getattr(app, "script_%s" % scriptName, None)
					if func:
						return func

		# Tree interceptor level.
		treeInterceptor = focus.treeInterceptor
		if treeInterceptor and treeInterceptor.isReady:
			func = getattr(treeInterceptor , "script_%s" % scriptName, None)
			if func:
				return func

		# NVDAObject level.
		func = getattr(focus, "script_%s" % scriptName, None)
		if func:
			return func
		for obj in reversed(api.getFocusAncestors()):
			func = getattr(obj, "script_%s" % scriptName, None)
			if func and getattr(func, 'canPropagate', False):
				return func

		# Global commands.
		func = getattr(globalCommands.commands, "script_%s" % scriptName, None)
		if func:
			return func

		return None

def send_key(vk=None, scan=None, extended=False, pressed=True):
	i = INPUT()
	i.union.ki.wVk = vk
	if scan:
		i.union.ki.wScan = scan
	else: #No scancode provided, try to get one
		i.union.ki.wScan = ctypes.windll.user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
	if not pressed:
		i.union.ki.dwFlags |= KEYEVENTF_KEYUP 
	if extended:
		i.union.ki.dwFlags |= KEYEVENTF_EXTENDEDKEY
	i.type = INPUT_KEYBOARD
	ctypes.windll.user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))
