#!/usr/bin/env python

import glob
import os
import re
import sys

CONFIG_FILE = "/etc/failover.conf"
DRBD_DIR    = "/etc/drbd.d"
PLUGIN_DIR  = "plugins/"

RE_CONFIG_LINE   = re.compile("^[\ \t]*([a-zA-Z0-9_\.]+)[\ \t]*=[\ \t]*([^#\n\r]+).*$")
RE_DRBD_RESOURCE = re.compile("^[\ \t]*resource[\ \t]+([a-z0-9]+).*$")

config_checks = {
	"port":            { "type": "int",   "default": 4997,       "check": "> 1024" },
	"role":            { "type": "str",   "default": False,      "check": "in ['master', 'slave']" },
	"initdead":        { "type": "float", "default": 5.0,        "check": "> 0.0" },
	"peer_host":       { "type": "str",   "default": False,      "check": False },
	"peer_port":       { "type": "int",   "default": False,      "check": "> 1024" },
	"timeout":         { "type": "float", "default": 2.0,        "check": ">= 0.1" },
	"interval":        { "type": "float", "default": 0.2,        "check": ">= 0.2" },
	"services":        { "type": "list",  "default": [],         "check": "checkServices(value)" },
	"drbd_resources":  { "type": "list",  "default": [],         "check": "checkDrbdResources(value)" },
	"plugin_dir":      { "type": "str",   "default": PLUGIN_DIR, "check": "checkDirectory(value)" },
	"quorum_plugin":   { "type": "str",   "default": False,      "check": "checkQuorumPlugin(value)" },
	"switcher_plugin": { "type": "str",   "default": False,      "check": "checkSwitcherPlugin(value)" },
}

config_optional = [
	"quorum_plugin",
	"switcher_plugin",
]

config_dict = dict()

def fail(text, code=1):
	sys.stderr.write("%s\n" % text)
	sys.stderr.flush()
	sys.exit(code)

def splitIntoList(value):
	if   len(value) == 0:       return []
	elif value.count(',') == 0: return [value]
	else:                       return value.split(',')

def convertType(name, value, vartype):
	ret   = False
	value = value.strip()

	try:
		if   vartype == "list":  ret = splitIntoList(value)
		elif len(value) == 0:    ret = False
		elif vartype == "int":   ret = int(value)
		elif vartype == "float": ret = float(value)
		else:                    ret = str(value)

	except ValueError:
		fail("Parameter '%s' should be a %s" % (name, vartype))

	return ret

def checkValue(name, value, check):
	if not check:            return True
	elif "(value)" in check: return eval(check)
	elif type(value) == str: return eval("\"%s\" %s" % (value, check))
	else:                    return eval("%.1f %s" % (value, check))

def checkDrbdResources(resources):
	global drbd_dir

	for res in glob.glob("%s/*.res" % (drbd_dir)):
		resource = False

		for line in open(res).readlines():
			match = RE_DRBD_RESOURCE.match(line)

			if match:
				resource = match.group(1)

				if resources.count(resource):
					resources.remove(resource)

	if len(resources):
		fail("The following DRBD resources do not exist: %s" % (resources))

	return True

def checkServices(services):
	for service in services:
		if not os.path.isfile(os.path.join("/etc/init.d", service)):
			fail("Service '%s' does not exist" % (service))

	return True

def checkQuorumPlugin(filepath):
	global config_dict

	if not filepath:
		return True

	return os.path.isfile(os.path.join(config_dict['plugin_dir'], "quorum", "%s.py" % filepath)) or fail("Quorum plugin '%s' does not exist." % (filepath))

def checkSwitcherPlugin(filepath):
	global config_dict

	if not filepath:
		return True

	return os.path.isfile(os.path.join(config_dict['plugin_dir'], "switcher", "%s.py" % filepath)) or fail("Switcher plugin '%s' does not exist." % (filepath))

def checkFile(filepath):
	return os.path.isfile(filepath) or fail("File '%s' does not exist." % (filepath))

def checkDirectory(dirpath):
	return os.path.isdir(dirpath) or fail("Directory '%s' does not exist." % (dirpath))

def show():
	global config_dict

	keys = config_dict.keys()
	keys.sort()

	print
	for name in keys:
		print "%-16s: %s" % (name, config_dict[name])
	print

if len(sys.argv) > 1: config_file = sys.argv[1]
else:                 config_file = CONFIG_FILE

if len(sys.argv) > 2: drbd_dir = sys.argv[2]
else:                 drbd_dir = DRBD_DIR

checkFile(config_file)
checkDirectory(drbd_dir)

for name in config_checks.keys():
	config_dict[name] = config_checks[name]['default']

for line in open(config_file).readlines():
	match = RE_CONFIG_LINE.match(line)

	if match:
		name   = match.group(1).strip()
		value  = match.group(2).replace('\t', '').replace(' ', '').strip()

		if name in config_checks.keys():
			vartype           = config_checks[name]['type']
			check             = config_checks[name]['check']
			config_dict[name] = convertType(name, value, vartype)
			res               = checkValue(name, config_dict[name], check)

			if not res:
				fail("Parameter '%s' validation failed (%s)" % (name, check))


for name in config_checks.keys():
	if name not in config_optional and config_dict[name] == False:
		fail("Parameter '%s' cannot be empty or unset" % (name))

	exec("%s = config_dict[name]" % (name))

