#!/usr/bin/python2

import sys
sys.path.insert(1, "../")
import time
import argparse
import zaber
import id3003
import myutils
import signal

log = myutils.printer()

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument("-xd",	"--xray-device",	dest="xray_device",	help="Xray generator device, e.g. /dev/ttyS0",	default="/dev/ttyS0")
parser.add_argument("-xt",	"--xray-type",		dest="xray_type",	help="Xray generator device type, e.g. id3003",	default="id3003")
parser.add_argument("-sd",	"--stage-device",	dest="stage_device",	help="Fluorescence device, e.g. /dev/ttyS0",	default="/dev/ttyS1")
parser.add_argument("-st",	"--stage-type",		dest="stage_type",	help="Fluorescence device type, e.g. zaber",	default="zaber")
parser.add_argument("-dir",	"--directory",		dest="directory",	help="Directory for log files",			default=".")
parser.add_argument("-ts",	"--timestamp",		dest="timestamp",	help="Timestamp for creation of file",		default=0)
parser.add_argument("-tg",	"--targets",		dest="targets",		help="Fluorescence target description",		default="")
args = parser.parse_args()

# Setup logging handle
log.timestamp = float(args.timestamp)
log.set_logfile(args.directory + "/xrayClient.log")
log.set_prefix = ""

# Print welcome
log.printw()

# Setup Subsystem
abo = "/xray"
client = myutils.sClient("127.0.0.1", 12334, "xrayClient")
client.subscribe(abo)
client.send(abo, 'Connecting xrayClient with Subsystem\n')

targets = {}
# Decode target argument
for target in args.targets.split(","):
	positions = target.split(":")
	name = positions[0]
	positions = positions[1:]
	if len(positions) == 0:
		error = "Invalid target description."
		log.warning(error)
		raise Exception(error)
	str = name + " target at position "
	if len(positions) > 1:
		str += "["
	for p in positions[:-1]:
		str += p + ":"
	str += positions[-1]
	if len(positions) > 1:
		str += "]"
	log << str
	for i in range(len(positions)):
		positions[i] = int(positions[i])
	targets[name] = positions

log.printv()

# Open the xray generator device ###################################################
log << "Opening " + args.xray_type +  " xray device at " + args.xray_device + " ..."
if args.xray_type == "id3003":
	xray_generator = id3003.id3003_xray_generator(args.xray_device)
else:
	error = "Unknown device " + args.xray_type + "."
	log.warning(error)
	raise Exception(error)

if not xray_generator.is_open():
	error = "Unable to open " + args.xray_type + " device."
	log.warning(error)
	raise Exception(error)
else:
	log << "Xray device is open."

if not xray_generator.test_communication():
	error = "Unable to communicate with " + args.xray_type + " device."
	log.warning(error)
	raise Exception(error)
else:
	log << "Communication with xray device is OK."

# Reset the device
#log << "Resetting device ..."
#success = motor_stage.reset()
#if not success:
#	error = "Unable to reset the device."
#	log.warning(error)
#	raise Exception(error)
#else:
#	log << "Device reset."

# Sleep a little to allow the device to reset properly
#sleep_seconds = 0.5
#log << "Sleeping " + `sleep_seconds` + " seconds ..."
#time.sleep(sleep_seconds)

log.printv()

# Open the motor stage device ################################################################
log << "Opening " + args.stage_type +  " fluorescence device at " + args.stage_device + " ..."
if args.stage_type == "zaber":
	motor_stage = zaber.zaber_motor_stage(args.stage_device)
else:
	error = "Unknown device " + args.stage_type + "."
	log.warning(error)
	raise Exception(error)

if not motor_stage.is_open():
	error = "Unable to open " + args.stage_type + " device."
	log.warning(error)
	raise Exception(error)
else:
	log << "Fluorescence device is open."

if not motor_stage.test_communication():
	error = "Unable to communicate with " + args.stage_type + " device."
	log.warning(error)
	raise Exception(error)
else:
	log << "Communication with fluorescence device is OK."

# Reset the device
#log << "Resetting device ..."
#success = motor_stage.reset()
#if not success:
#	error = "Unable to reset the device."
#	log.warning(error)
#	raise Exception(error)
#else:
#	log << "Device reset."

# Sleep a little to allow the device to reset properly
sleep_seconds = 0.5
log << "Sleeping " + `sleep_seconds` + " seconds ..."
time.sleep(sleep_seconds)

# Move the device to its home position
log << "Moving device to home position ..."
success = motor_stage.home()
if not success:
	error = "Unable to move to home position."
	log.warning(error)
	raise Exception(error)
else:
	log << "Home position reached."

log << "Initialization finished."
log.printv()

# Setup KILL handler
def handler(signal, frame):
	log.printv()
	log << "Received signal " + `signal` + "."
	log << "Closing connection ..."
	client.closeConnection()
	if client.isClosed == True:
		log << "Client connection closed."

signal.signal(signal.SIGINT, handler)

# Wait for new commands from elComandante

shutter = 3 # FIXME: Read from config

log << "Waiting for commands ..."
while client.anzahl_threads > 0 and client.isClosed == False:
	time.sleep(0.5)
	packet = client.getFirstPacket(abo)
	if not packet.isEmpty():
		log << "Received packet from " + abo + ": " + packet.data
		timeStamp, commands, type, message, command = myutils.decode(packet.data)
		if len(commands) == 2 and commands[0].upper() == "SET":
			if commands[1].upper() == "TARGET":
				target = message
				if target in targets:
					log << "Moving to target " + target + " ..."
					motor_stage.move_absolute(targets[target])
					log << "Current target is now " + target + "."
					shutter = 1 # FIXME: Use config value
				elif target.lower() == "none" or target == "":
					shutter = 3 # FIXME: Use config value
				else:
					error = "Invalid target selected."
					log.warning(error)
			elif commands[1].upper() == "VOLTAGE":
				kV = int(message)
				log << "Setting voltage to " + `kV` + " kV ..."
				success = xray_generator.set_voltage(kV)
				if not success:
					error = "Unable to set the voltage."
					log.warning(error)
					raise Exception(error)
				else:
					log << "Voltage set."
			elif commands[1].upper() == "CURRENT":
				mA = int(message)
				log << "Setting current to " + `mA` + " mA ..."
				success = xray_generator.set_current(mA)
				if not success:
					error = "Unable to set the current."
					log.warning(error)
					raise Exception(error)
				else:
					log << "Current set."
			elif commands[1].upper() == "HV":
				on = 0
				if message.upper() == "ON":
					on = 1
				elif message.upper() == "OFF":
					on = 0
				else:
					error = "Invalid command: " + packet.data
					log.warning(error)
					raise Exception(error)

				if on:
					log << "Turning high voltage on ..."
				else:
					log << "Turning high voltage off ..."
				success = xray_generator.set_hv(on)
				if not success:
					if on:
						error = "Unable to turn on the high voltage."
					else:
						error = "Unable to turn off the high voltage."
					log.warning(error)
					raise Exception(error)
				else:
					if on:
						log << "High voltage on and stable."
					else:
						log << "High voltage off."
			elif commands[1].upper() == "BEAM":
				on = 0
				if message.upper() == "ON":
					on = 1
				elif message.upper() == "OFF":
					on = 0
				else:
					error = "Invalid command: " + packet.data
					log.warning(error)
					raise Exception(error)

				if on:
					log << "Turning beam on ..."
				else:
					log << "Turning beam off ..."
				success = xray_generator.set_beam_shutter(shutter, on)
				if not success:
					if on:
						error = "Unable to turn on the beam."
					else:
						error = "Unable to turn off the beam."
					log.warning(error)
					raise Exception(error)
				else:
					if on:
						log << "Beam on."
					else:
						log << "Beam off."
		elif len(commands) == 1 and commands[0].upper() == "FINISHED":
			client.send(abo, ":FINISHED\n")
		elif len(commands) == 1 and commands[0].upper() == "EXIT":
			break

log.printv()
log << "Closing connection ..."
client.closeConnection()
if client.isClosed == True:
	log << "Client connection closed."
log << "Exit."