#!python3

import subprocess
import threading
import gpiozero
import time
import json
import sys
import os
import re



# Do not change the value of these default constants.
DEFAULT_CONFIG_FILE_PATH = "config.json" # Default "config.json" file path.
DEFAULT_COOLER_TEMP = "60.0/70.0" # Cooler fan will start running at (2nd value) temperature or above, and will stop when below (1st value) temperature.
DEFAULT_COOLER_TIMESPAN = "5m/24h" # Cooler fan will forcibly run for a total of (1st value) time each (2nd value) time (eg.: 5m each 24h).
DEFAULT_TEMPERATURE_MEASURE_CMD = "vcgencmd measure_temp" # Default temperature measurement command.
DEFAULT_TEMPERATURE_MEASURE_REGEX = r"^\s*temp\s*=\s*([+-]?[0-9]+(?:\.[0-9]+)?)\s*'\s*C\s*$" # Default temperature measurement output regex (Regexp to capture the temperature as a float).
DEFAULT_BUTTON_CMDS = [ "shutdown -r now", "shutdown now" ] # Default button commands (must be a non-empty list of strings).
TEMPERATURE_MEASURE_INTERVAL = 30 # Interval time (seconds) between each temperature check.
BUTTON_TEST_TIMEOUT = 10 # Time (seconds) to wait until push down the button on setup.
BUTTON_PRESS_TIMEOUT = 3 # Time (seconds) to wait button turns to the next command.

# Do not change the value of these constants.
LED_BLINK_MIN_TIME = BUTTON_PRESS_TIMEOUT/12 # Minimum time (seconds) of the LED blink animation.
LED_BLINK_MAX_TIME = BUTTON_PRESS_TIMEOUT/4 # Maximum time (seconds) of the LED blink animation.
TIME_SPAN_REGEX = re.compile(r"^\s*([0-9]+)\s*(s|m|h|d)?\s*\/\s*([0-9]+)\s*(s|m|h|d)?\s*$") # Regexp for time span (two integers).
TEMPERATURE_REGEX = re.compile(r"^\s*([+-]?[0-9]+(?:\.[0-9]+)?)\s*\/\s*([+-]?[0-9]+(?:\.[0-9]+)?)\s*$") # Regexp for temperatures (two floats).



class SetupInputException(Exception):
	pass

class HwController:

	allPins = { }

	def __init__(self, pin: str, reversed: bool = False):
		pin = pin.strip()
		if pin == "":
			raise SetupInputException("Pin must not be empty.")
		self.initialized = False
		self.pin = pin
		self.ioPin = None
		self.reversed = reversed
	
	def initialize(self):
		if self.initialized:
			return
		if self.pin.lower() in HwController.allPins:
			raise SetupInputException("Pin '%s' already in use." % (self.pin))
		HwController.allPins[self.pin.lower()] = True
		self.initialized = True
		#self.ioPin = gpiozero.DigitalOutputDevice(self.pin, active_high=not self.reversed)
	
	def setReversed(self, reversed: bool = False):
		if self.initialized:
			return
		self.reversed = reversed

	def close(self):
		if not self.initialized:
			return
		if self.ioPin is not None:
			self.ioPin.close()
			self.ioPin = None
		del HwController.allPins[self.pin.lower()]
		self.initialized = False

	def __del__(self):
		self.close()

class StatusLED(HwController):
	def initialize(self):
		HwController.initialize(self)
		self.ioPin = gpiozero.LED(self.pin, active_high=not self.reversed)
		self.ioPin.on()

class PowerLED(HwController):
	def initialize(self):
		if self.initialized:
			return
		HwController.initialize(self)
		self.ioPin = gpiozero.LED(self.pin, active_high=not self.reversed)
		self.ioPin.off()
	
	def blink(self, start: int, end: int = 5):
		if not self.initialized:
			return
		if start < 0:
			self.ioPin.off()
		elif start <= end:
			time = LED_BLINK_MIN_TIME + start/end * (LED_BLINK_MAX_TIME - LED_BLINK_MIN_TIME)
			n = int(BUTTON_PRESS_TIMEOUT/time) + 2
			self.ioPin.blink(on_time=time/2, off_time=time/2, n=n)
		else:
			self.ioPin.on()
		
	def on(self):
		if not self.initialized:
			return
		self.ioPin.on()

	def off(self):
		if not self.initialized:
			return
		self.ioPin.off()

class PowerButton(HwController):
	def __init__(self, pin: str, cmds: list = [ ], powerLED = None):
		super().__init__(pin, reversed = False)
		if len(cmds) < 1:
			self.cmds = DEFAULT_BUTTON_CMDS
		else:
			for item in cmds:
				if type(item) != str:
					raise TypeError("Argument 'cmds' must be a list of strings.")
				self.cmds = cmds
		self.powerLED = powerLED

	def setCmds(self, cmds: list):
		if self.initialized:
			return
		if len(cmds) < 1:
			raise TypeError("Argument 'cmds' must be a non-empty list of strings.")
		for item in cmds:
			if type(item) != str:
				raise TypeError("Argument 'cmds' must be a list of strings.")
		self.cmds = cmds

	def setPowerLED(self, powerLED = None):
		if self.initialized:
			return
		self.powerLED = powerLED

	def initialize(self):
		if self.initialized:
			return
		HwController.initialize(self)
		self.ioPin = gpiozero.Button(self.pin) # No reversed on button.
		if self.powerLED is not None: self.powerLED.off()

	@staticmethod
	def _exec(cmd):
		os.system(cmd)

	def wait(self, timeout = None) -> bool:
		if not self.initialized:
			return False
		if timeout is not None and type(timeout) != float and type(timeout) != int:
			raise TypeError("Argument 'timeout' must be None, a float or an integer.")
		if not self.ioPin.wait_for_press(timeout):
			return False
		if self.powerLED is not None: self.powerLED.on()
		if self.ioPin.wait_for_release(BUTTON_PRESS_TIMEOUT):
			if self.powerLED is not None: self.powerLED.off()
			return True
		cmdLen = len(self.cmds)
		for i in range(cmdLen):
			if powerLED is not None: powerLED.blink(i, cmdLen - 1)
			if self.ioPin.wait_for_release(BUTTON_PRESS_TIMEOUT):
				PowerButton._exec(self.cmds[i])
				if self.powerLED is not None: self.powerLED.off()
				return True
		if self.powerLED is not None: self.powerLED.off()
		if not self.ioPin.wait_for_release(timeout):
			return False
		return True

	def run(self, timeout = None):
		if timeout is not None and type(timeout) != float and type(timeout) != int:
			raise TypeError("Argument 'timeout' must be None, a float or an integer.")
		while True:
			self.wait(timeout)

class CoolerFan(HwController):
	def __init__(self, pin: str, reversed: bool = False):
		super().__init__(pin, reversed)
		self.stopTemperature, self.startTemperature = CoolerFan._parseTemp(DEFAULT_COOLER_TEMP)
		self.runTime, self.runCycle = CoolerFan._parseTimeSpan(DEFAULT_COOLER_TIMESPAN)
		self.measureCmd = DEFAULT_TEMPERATURE_MEASURE_CMD
		self.measureRegexp = re.compile(DEFAULT_TEMPERATURE_MEASURE_REGEX)

	@staticmethod
	def _parseTemp(temp: str):
		found = TEMPERATURE_REGEX.findall(temp.strip().lower())
		if len(found) < 1:
			raise ValueError("The 'temp' is not correct. Must be in format 'float/float'.")
		found = found[0]
		return (float(found[0]), float(found[1]))
	
	@staticmethod
	def _tempValid(temp: str) -> bool:
		try:
			stop, start = CoolerFan._parseTemp(temp)
			if stop > start:
				return False
		except:
			return False
		return True

	@staticmethod
	def _parseTimeSpan(timeSpan: str):
		found = TIME_SPAN_REGEX.findall(timeSpan.strip().lower())
		if len(found) < 1:
			raise ValueError("The 'timeSpan' is not correct. Must be in format 'int[s|m|h|d]/int[s|m|h|d]'.")
		found = found[0]
		run = int(found[0])
		cycle = int(found[2])
		if found[1] == "m":
			run *= 60
		elif found[1] == "h":
			run *= 60*60
		elif found[1] == "d":
			run *= 60*60*24
		if found[3] == "m":
			cycle *= 60
		elif found[3] == "h":
			cycle *= 60*60
		elif found[3] == "d":
			cycle *= 60*60*24
		return (run, cycle)

	@staticmethod
	def _timeSpanValid(timeSpan: str) -> bool:
		try:
			run, cycle = CoolerFan._parseTimeSpan(timeSpan)
			if run > cycle:
				return False
		except:
			return False
		return True

	@staticmethod
	def _measureTemp(cmd, regexp):
		try:
			process = subprocess.Popen(cmd, stdout = subprocess.PIPE, shell = True)
			output, _ = process.communicate()
			output = output.decode("ascii").strip()
			output = regexp.findall(output)
			if len(output) < 1:
				return None
			return float(output[0])
		except:
			pass
		return None

	def initialize(self):
		if self.initialized:
			return
		HwController.initialize(self)
		self.ioPin = gpiozero.DigitalOutputDevice(self.pin, active_high=not self.reversed)

	def setTemperatures(self, temp: str):
		if self.initialized:
			return
		self.stopTemperature, self.startTemperature = CoolerFan._parseTemp(temp)
	
	def setTimeSpan(self, timeSpan: str):
		if self.initialized:
			return
		self.runTime, self.runCycle = CoolerFan._parseTimeSpan(timeSpan)

	def setCmd(self, cmd: str):
		if self.initialized:
			return
		self.measureCmd = cmd
	
	def setRegex(self, regex: str = r"^\s*(\-?[0-9]+(?:\.[0-9]+)?)\s*$"):
		if self.initialized:
			return
		self.measureRegexp = re.compile(regex)

	def check(self):
		timestampMod = time.time() % self.runCycle
		temp = CoolerFan._measureTemp(self.measureCmd, self.measureRegexp)
		if self.runTime > 0 and timestampMod <= self.runTime:
			self.ioPin.on()
		elif temp is None:
			self.ioPin.off()
		elif temp < self.stopTemperature:
			self.ioPin.off()
		elif temp >= self.startTemperature:
			self.ioPin.on()
	
	def run(self):
		while True:
			self.check()
			time.sleep(TEMPERATURE_MEASURE_INTERVAL)

def setup():
	""" This setup is run when the config file doesn't exist to create it. """
	print("Looks like you are running Pi-Cooler for the first time. Let's setup everything for you.")
	print()
	try:
		coolerFan = input("What GPIO pin are you using for the Raspberry Pi Cooler Fan? (leave blank if you are not using it) > ").strip()
		coolerFanReversed = False
		if coolerFan != "":
			coolerFanReversed = input("Are you using a NPN or PNP transistor for the Cooler Fan? (leave blank if you are using no transistors) > ").strip().lower()
			if coolerFanReversed != "pnp" and coolerFanReversed != "npn" and coolerFanReversed != "":
				raise SetupInputException("This question only accepts values NPN or PNP as answer!")
			if coolerFanReversed == "pnp":
				coolerFanReversed = True
			else:
				coolerFanReversed = False
		powerButton = input("What GPIO pin are you using for the Power Button? (leave blank if you are not using it) > ").strip()
		powerLed = ""
		if powerButton != "":
			powerLed = input("What GPIO pin are you using for the Power Button LED indicator? This LED indicates when you press the button. (leave blank if you are not using it) > ").strip()
		statusLed = input("What GPIO pin are you using for the Status LED indicator? This LED is always ON, except when Raspberry is restarting or powering off. (leave blank if you are not using it) > ").strip()
		if coolerFan == "" and powerButton == "" and statusLed == "":
			raise SetupInputException("You don't need this program, since you have no compatible electronic hardware attached to the Raspberry Pi GPIO!")
		print()
		print("Now let's check if everything is working properly.")
		if coolerFan != "":
			pin = gpiozero.DigitalOutputDevice(coolerFan, active_high=not coolerFanReversed)
			pin.on()
			working = input("Is the Cooler Fan working? (YES or NO, default = YES) > ").strip().lower()
			if working != "yes" and working != "y" and working != "":
				raise SetupInputException("Please, check the electronic circuit and try again.")
			pin.off()
			pin.close()
		if powerButton != "":
			pin = gpiozero.Button(powerButton)
			input("We are going to test the power button. You need to press it within the next " + str(BUTTON_TEST_TIMEOUT) + " seconds. Get ready and press [ENTER] whenever you are ready to press it. > ")
			print("PRESS THE BUTTON NOW!")
			working = pin.wait_for_press(timeout = BUTTON_TEST_TIMEOUT)
			if working == False:
				raise SetupInputException("Please, check the electronic circuit and try again.")
			pin.close()
		if powerLed != "":
			pin = gpiozero.LED(powerLed)
			pin.on()
			working = input("Is the Power LED indicator working? (YES or NO, default = YES) > ").strip().lower()
			if working != "yes" and working != "y" and working != "":
				raise SetupInputException("Please, check the electronic circuit and try again.")
			pin.off()
			pin.close()
		if statusLed != "":
			pin = gpiozero.LED(statusLed)
			pin.on()
			working = input("Is the Status LED indicator working? (YES or NO, default = YES) > ").strip().lower()
			if working != "yes" and working != "y" and working != "":
				raise SetupInputException("Please, check the electronic circuit and try again.")
			pin.off()
			pin.close()
		print("Saving changes...")
		jsonObj = {
			"pins": { "coolerFan": coolerFan, "powerButton": powerButton, "powerLED": powerLed, "statusLED": statusLed },
			"powerButtonCmds": DEFAULT_BUTTON_CMDS,
			"coolerFanReversed": coolerFanReversed,
			"runTemperature": DEFAULT_COOLER_TEMP,
			"runTimeSpan": DEFAULT_COOLER_TIMESPAN,
			"cmdTemperature": DEFAULT_TEMPERATURE_MEASURE_CMD,
			"regexTemperature": DEFAULT_TEMPERATURE_MEASURE_REGEX
		}
		with open(config_file, "w") as fStream:
			json.dump(jsonObj, fStream, indent=4)
		print()
		print("PERFECT! Now the configuration file has been created. The following command line starts the program:")
		print("\t> python3 \"%s\" \"%s\" &" % (os.path.realpath(__file__), os.path.realpath(config_file)))
		print()
		print("We recommend adding this command line to the boot sequence of the Raspberry Pi (so that you don't need to start the program manually everytime).")
		print("For instance, add this command line to the \"rc.local\" file.")
		print()
	except SetupInputException as exc:
		print()
		print(str(exc))
		print()
	except Exception as exc:
		print()
		print(exc)
		print()
		print("Error! Please run program again to restart setup.")
		print()

def loadConfig(config_file):
	global statusLED, powerLED, powerButton, coolerFan
	try:
		with open(config_file, "r") as fStream:
			config = json.load(fStream)
		if "pins" not in config or type(config["pins"]) != dict:
			raise SetupInputException("No pins configured. Delete the 'config.json' file and run setup again.")
		empty = True
		for key in config["pins"]:
			if key != "coolerFan" and key != "powerButton" and key != "powerLED" and key != "statusLED":
				continue
			if config["pins"][key] is None:
				config["pins"][key] = ""
			if type(config["pins"][key]) != str:
				raise SetupInputException("Pins must be of type 'string' or 'null'.")
			config["pins"][key] = config["pins"][key].strip()
			if config["pins"][key] == "":
				continue
			if key == "coolerFan":
				coolerFan = CoolerFan(config["pins"][key])
			elif key == "powerButton":
				powerButton = PowerButton(config["pins"][key])
			elif key == "powerLED":
				powerLED = PowerLED(config["pins"][key])
				continue
			elif key == "statusLED":
				statusLED = StatusLED(config["pins"][key])
			empty = False
		if empty:
			raise SetupInputException("No pins configured. Delete '%s' file and run setup again." % (config_file))
		if powerButton is not None and powerLED is not None:
			powerButton.setPowerLED(powerLED)
		if powerButton is not None and "powerButtonCmds" in config and type(config["powerButtonCmds"]) == list:
			powerButton.setCmds(config["powerButtonCmds"])
		if coolerFan is not None and "coolerFanReversed" in config and type(config["coolerFanReversed"]) == bool:
			coolerFan.setReversed(config["coolerFanReversed"])
		if coolerFan is not None and "runTemperature" in config and type(config["runTemperature"]) == str and CoolerFan._tempValid(config["runTemperature"]):
			coolerFan.setTemperatures(config["runTemperature"])
		if coolerFan is not None and "runTimeSpan" in config and type(config["runTimeSpan"]) == str and CoolerFan._timeSpanValid(config["runTimeSpan"]):
			coolerFan.setTimeSpan(config["runTimeSpan"])
		if coolerFan is not None and "cmdTemperature" in config and type(config["cmdTemperature"]) == str:
			coolerFan.setCmd(config["cmdTemperature"])
		if coolerFan is not None and "regexTemperature" in config and type(config["regexTemperature"]) == str:
			coolerFan.setRegex(config["regexTemperature"])
	except SetupInputException as exc:
		print()
		print(str(exc))
		print()
		sys.exit()
	except Exception as exc:
		print()
		print(exc)
		print()
		print("Error! The configuration file could not be read or parsed. If this error persists, delete the file and run the program again to setup.")
		print()
		sys.exit()

# Initialize all hardware objects.
coolerFan = None
powerButton = None
powerLED = None
statusLED = None

if __name__ != "__main__": # Check if running as main program.
	print("Can not be used as a module.")
	sys.exit()

if len(sys.argv) > 2: # Usage help.
	print("Usage:")
	print("\t> python3 %s %s" % (sys.argv[0], "[CONFIG_FILE]"))
	print()
	print("Where:")
	print("\t%s -> %s" % ("[CONFIG_FILE]", "Path to the configuration JSON file (default = " + DEFAULT_CONFIG_FILE_PATH + ")."))
	print()
	sys.exit()

if len(sys.argv) > 1: # Config file path specified.
	config_file = sys.argv[1]
else:
	config_file = DEFAULT_CONFIG_FILE_PATH

if not os.path.isfile(config_file): # Config file doesn't exist, therefore setup.
	setup()
	sys.exit()

loadConfig(config_file) # Load JSON file.

if statusLED is not None: # If Status LED is activated, then turn it on.
	statusLED.initialize()

if powerButton is not None and powerLED is not None: # If Power Button and Power LED are activated, initialize them.
	powerLED.initialize()
	powerButton.initialize()
elif powerButton is not None: # If Power Button only is activated, initialize it.
	powerButton.initialize()

if coolerFan is not None: # If Cooler Fan is activated, initialize it.
	coolerFan.initialize()

if coolerFan is not None and powerButton is not None: # If both Cooler Fan and Power Button are initialized, create thread for Power Button and run Cooler Fan on main thread.
	t = threading.Thread(target=powerButton.run)
	t.start()
	coolerFan.run()
	t.join()
elif powerButton is not None: # If only Power Button is initialized, run it in main thread.
	powerButton.run()
elif coolerFan is not None: # If only Cooler Fan is initialized, run it in main thread.
	coolerFan.run()
else: # If none is initialized, you need to pause the script forever because of the Status LED (which is already on).
	while True:
		time.sleep(TEMPERATURE_MEASURE_INTERVAL)


