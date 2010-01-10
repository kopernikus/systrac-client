#!/usr/bin/env python

"""
The MIT License

Copyright (c) 2008 Gilad Raphaelli <gilad@raphaelli.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

from ctypes import byref, cast, cdll, pointer, addressof
from ctypes import c_char, c_char_p, c_double, c_int, c_long, c_short, c_ulong, c_uint
from ctypes import POINTER, Structure, Union
from ctypes.util import find_library
from itertools import izip
import re, sys

time_t = c_long
off_t = c_long

# rrd.h
rrd_value_t  = c_double
rrd_info_type_t = c_int

class rrd_file_t(Structure):
	_fields_ = [
		('fd',           c_int),
		('file_start',   c_char_p),
		('header_len',   off_t),
		('file_len',     off_t),
		('pos',          off_t),
	]

class rrd_blob_t(Structure):
	_fields_ = [
		('size',         c_ulong),                 # /* size of the blob */
		('ptr',          c_char_p),                # /* size of the blob */
	]

(RD_I_VAL, RD_I_CNT, RD_I_STR, RD_I_INT, RD_I_BLO) = [c_int(x) for x in xrange(5)]

class rrd_infoval_t(Union):
	_fields_ = [
		('u_cnt',        c_ulong),
		('u_val',        rrd_value_t),
		('u_str',        c_char_p),
		('u_int',        c_int),
		('u_blo',        rrd_blob_t),
	]

class rrd_info_t(Structure):
	pass

rrd_info_t._fields_ = [
	('key',          c_char_p),
	('type',         rrd_info_type_t),
	('value',        rrd_infoval_t),
	('next',         POINTER(rrd_info_t)),
]

rrd_library = find_library('rrd')

if rrd_library:
	librrd = cdll.LoadLibrary(rrd_library)
else:
	raise ImportError("Can't find the rrd library")

class RRDLibError(Exception): pass
class RRDLibVersionError(Exception): pass

def needs_argv(fn):
	""" convenience decorator to create the argv that rrd_* expect """
	def new(*args):
		argv = (c_char_p * (len(args) + 1))()
		for i in xrange(len(args)):
			argv[i+1] = c_char_p(str(args[i]))
			#argv[i+1] = c_char_p(args[i]) # need to think about this
		return fn(argv)
	return new

def make_argv(*args):
	""" convenience function to create the argv that rrd_* expect """
	return needs_argv(lambda x: x)(*args)

def librrd_wrapper(rrdlib_func):
	""" DRY wrapper for standard rrd_*(argc, argv) calls """
	def deco(fn):
		def new(argv):
			return_type = rrdlib_func.restype
			#ret = return_type()
			ret = rrdlib_func(len(argv), argv)
			if (return_type in (c_int, time_t) and ret == -1) or (ret is None): # or librrd.rrd_test_error():
				e = rrd_get_error()
				rrd_clear_error()
				raise RRDLibError(e)
			return fn(ret)
		return new
	return deco

def needs_rrdtool_version(v_wanted):
	""" only available in version X or higher """
	def deco(fn):
		def new(*args):
			v = version()
			if v < v_wanted:
				raise RRDLibVersionError("requires rrdtool version %s, %s found" % (v_wanted, v))
			return fn(*args)
		return new
	return deco

def _rrd_info_to_array(info_p):
	""" given a pointer to an rrd_info_t, return an array of tuples of the
	contents of that rrd_info_t """
	r = []
	while info_p:
		d = info_p.contents
		if d.type == RD_I_VAL.value:
			val = d.value.u_val
			if isnan(val):
				val = None
		elif d.type == RD_I_CNT.value:
			val = d.value.u_cnt
		elif d.type == RD_I_INT.value:
			val = d.value.u_int
		elif d.type == RD_I_STR.value:
			val = d.value.u_str
		elif d.type == RD_I_BLO.value:
			val = d.value.u_blo.contents

		r.append((d.key, val))

		info_p = d.next

	return r

def _array_to_rrd_info12(arr):
	""" given an array like that returned by _rrd_info_to_array, return
	something like what py-rrdtool bundled with rrdtool 1.2.* did """

	info_re = re.compile('(?P<info_type>\w+)\[(?P<index>\w+)\]\.(?P<property>\w+)')

	def update_d(key, value, d, dt):
		""" info array specific function for turning something like 
		[('rra[0].cf', 'AVERAGE')] into {'rra' : ['cf' : 'AVERAGE'] } """

		m = info_re.search(key)
		if m:
			(info_type, index, property) = m.groups()

			if not d.has_key(info_type):
				d[info_type] = dt()

			if dt is list:
				index = int(index)
				if len(d[info_type]) <= index:
					d[info_type].append({})
			elif not d[info_type].has_key(index):
				d[info_type][index] = {}

			if m.end() == len(key):
				d[info_type][index][property] = value
			else:
				if not dt is list and not d[info_type].has_key(index):
					d[info_type][index] = {}
				prop_start_pos = m.end() - len(property)
				update_d(key[prop_start_pos:], value, d[info_type][index], list)
		return d
			
	di = {'rra':[], 'ds':{}}
	for (k,v) in arr:
		if k.startswith('ds'):
			 update_d(k, v, di, dict)
		elif k.startswith('rra'):
			 update_d(k, v, di, list)
		else:
			di[k] = v

	for ds_name in di['ds'].keys():
		di['ds'][ds_name]['ds_name'] = ds_name

	return di

def rrd_info12_wrapper(fn):
	""" wrapper to return rrdtool 1.2 style dict """
	def new(info):
		return _array_to_rrd_info12(fn(info))
	return new

def returns_info(fn):
	""" librrd returns an rrd_into_t - make it into an array on the way back """
	def new(info_p):
		info_array =  _rrd_info_to_array(info_p)
		try:
			info_free(info_p)
			del(info_p)
		except:
			pass # ?
		return fn(info_array)
	return new

# Version  #################################################
# /* double rrd_version( void ) */
rrd_version = librrd.rrd_version
rrd_version.restype = c_double

# /* char *rrd_strversion( void) */
rrd_strversion = librrd.rrd_strversion
rrd_strversion.restype = c_char_p

def version():
	return rrd_version()

def strversion():
	return rrd_strversion()

RRDTOOL_VERSION = version()

# Helpers #################################################
# /* HELPER FUNCTIONS */
# void rrd_set_error(char *,...);
# void rrd_clear_error(void);
# int  rrd_test_error(void);
# char *rrd_get_error(void);

# void rrd_set_error_r(rrd_context_t *, char *, ...)
# void rrd_clear_error_r(rrd_context_t *)
# int  rrd_test_error_r(rrd_context_t *)
# char *rrd_get_error_r(rrd_context_t *)

rrd_clear_error = librrd.rrd_clear_error

rrd_test_error = librrd.rrd_test_error
rrd_test_error.restype = c_int

rrd_get_error = librrd.rrd_get_error
rrd_get_error.restype = c_char_p

# void rrd_freemem(void *mem);
rrd_freemem = librrd.rrd_freemem

# Create  ###############################################
# /* int rrd_create(int, char **) */
rrd_create = librrd.rrd_create
rrd_create.argtypes = [c_int, POINTER(c_char_p)]
rrd_create.restype = c_int

# /* int rrd_create_r(const char *filename, unsigned long pdp_step, time_t last_up, int argc, const char **argv) */
rrd_create_r = librrd.rrd_create_r
rrd_create_r.argtypes = [c_char_p, c_ulong, time_t, c_int, POINTER(c_char_p)]
rrd_create_r.restype = c_int

@needs_argv
@librrd_wrapper(rrd_create)
def create(ret):
	""" create filename [--start|-b start time] [--step|-s step] [DS:ds-name:DST:heartbeat:min:max] [RRA:CF:xff:steps:rows] """
	return ret

def create_r(filename, pdp_step=300, last_up=None, *args):
	raise NotImplementedError
	if last_up is None:
		last_up = int(time.time()-10)
	
	# the list of DSes and RRAs
	argv = [ None ]
	for arg in args:
		if hasattr(arg, 'get_spec'):
			argv.append(arg.get_spec())
		else:
			argv.append(arg)

#	ret = rrd_create_r(c_char_p(filename), c_ulong(pdp_step), time_t(last_up), c_int(len(argv)), (c_char_p * len(argv))(
	if ret:
		e = rrd_get_error()
		raise RRDLibError(e)
	else:
		return RRDFile(filename)

# Dump  ###############################################
# /* int rrd_dump(int, char **) */
rrd_dump = librrd.rrd_dump
rrd_dump.argtypes = [c_int, POINTER(c_char_p)]
rrd_dump.restype = c_int

# /* int rrd_dump_r(const char *filename, char *outname) */
rrd_dump_r = librrd.rrd_dump_r
rrd_dump_r.argtypes = [c_char_p, c_char_p]
rrd_dump_r.restype = c_int

@needs_argv
@librrd_wrapper(rrd_dump)
def dump(ret):
	""" dump filename """
	return ret

def dump_r(filename):
	raise NotImplementedError
	
# Fetch  ###############################################
# /* int rrd_fetch(int, char **, time_t *start, time_t *end, unsigned long *step, unsigned long *ds_cnt, char ***ds_namv, rrd_value_t **data); */
rrd_fetch = librrd.rrd_fetch
rrd_fetch.argtypes = [c_int, POINTER(c_char_p), POINTER(time_t), POINTER(time_t), POINTER(c_ulong), POINTER(c_ulong), POINTER(POINTER(c_char_p)), POINTER(POINTER(rrd_value_t))]
rrd_fetch.restype = c_int

# /* int rrd_fetch_r(const char *filename, const char* cf, time_t *start, time_t *end, unsigned long *step, unsigned long *ds_cnt, char ***ds_namv, rrd_value_t **data) */
rrd_fetch_r = librrd.rrd_fetch_r
rrd_fetch_r.argtypes = [c_char_p, c_char_p, POINTER(time_t), POINTER(time_t), POINTER(c_ulong), POINTER(c_ulong), POINTER(POINTER(c_char_p)), POINTER(POINTER(rrd_value_t))]
rrd_fetch_r.restype = c_int

@needs_argv
def fetch(argv):
	""" fetch filename CF [--resolution|-r resolution] [--start|-s start] [--end|-e end] """
	start = time_t()
	end = time_t()
	step = c_ulong()
	ds_cnt = c_ulong()
	ds_namv = pointer(c_char_p())
	data = pointer(rrd_value_t())

	if rrd_fetch(len(argv), argv, byref(start), byref(end), byref(step), byref(ds_cnt), byref(ds_namv), byref(data)) == -1:
		e = rrd_get_error()
		rrd_clear_error()
		raise RRDLibError(e)
	else:
		ds_names = tuple([ds_namv[i] for i in xrange(ds_cnt.value)])
		rows = (end.value - start.value) / step.value
		data_points = []
		pos = 0
		for row in xrange(rows):
			dp = []
			for ds in xrange(ds_cnt.value):
				dv = data[pos]
				if isnan(dv):
					dv = None
				dp.append(dv)
				pos += 1
			data_points.append(tuple(dp))

		rrd_freemem(ds_namv)
		rrd_freemem(data)
		return ((start.value, end.value, step.value) , ds_names, data_points)

def fetch_r(filename, cf, *args):
	raise NotImplementedError

# First  ###############################################
# /* time_t rrd_first(int, char **) */
rrd_first = librrd.rrd_first
rrd_first.argtypes = [c_int, POINTER(c_char_p)]
rrd_first.restype = time_t

# /* time_t rrd_first_r(const char * filename, c_int) */
rrd_first_r = librrd.rrd_first_r
rrd_first_r.argtypes = [c_char_p, c_int]
rrd_first_r.restype = time_t

@needs_argv
@librrd_wrapper(rrd_first)
def first(ts):
	""" first filename """
	return ts

def first_r(filename, rraindex):
	raise NotImplementedError

# Graph  ###############################################
# /* int rrd_graph(int argc, char **argv, char ***prdata, int *xsize, int *ysize, FILE * stream, double *ymin, double *ymax) */
rrd_graph = librrd.rrd_graph
rrd_graph.argtypes = [c_int, POINTER(c_char_p), POINTER(POINTER(c_char_p)), POINTER(c_int), POINTER(c_int), POINTER(c_long), POINTER(c_double), POINTER(c_double)]
rrd_graph.restype = c_int

if RRDTOOL_VERSION >= 1.3:
	# /* rrd_info_t *rrd_graph_v(int, char **) */
	rrd_graph_v = librrd.rrd_graph_v
	rrd_graph_v.argtypes = [c_int, POINTER(c_char_p)]
	rrd_graph_v.restype = POINTER(rrd_info_t)

@needs_argv
def graph(argv):
	""" graph filename [so-many-options]
	[-s|--start seconds] [-e|--end seconds] [-x|--x-grid x-axis grid and label] [-y|--y-grid y-axis grid and label] [--alt
	-y-grid] [--alt-y-mrtg] [--alt-autoscale] [--alt-autoscale-max] [--units-exponent] value [-v|--vertical-label text] [-w|--width pixels] [
	-h|--height pixels] [-i|--interlaced] [-f|--imginfo formatstring] [-a|--imgformat GIF|PNG|GD] [-B|--background value] [-O|--overlay value
	] [-U|--unit value] [-z|--lazy] [-o|--logarithmic] [-u|--upper-limit value] [-l|--lower-limit value] [-g|--no-legend] [-r|--rigid] [--ste
	p value] [-b|--base value] [-c|--color COLORTAG#rrggbb] [-t|--title title] [DEF:vname=rrd:ds-name:CF] [CDEF:vname=rpn-expression] [PRINT:
	vname:CF:format] [GPRINT:vname:CF:format] [COMMENT:text] [HRULE:value#rrggbb[:legend]] [VRULE:time#rrggbb[:legend]] [LINE{1|2|3}:vname[#r
	rggbb[:legend]]] [AREA:vname[#rrggbb[:legend]]] [STACK:vname[#rrggbb[:legend]]] """
	prdata = pointer(c_char_p())
	xsize = c_int()
	ysize = c_int()
	ymin = c_double()
	ymax = c_double()

	if rrd_graph(len(argv), argv, byref(prdata), byref(xsize), byref(ysize), None, byref(ymin), byref(ymax)) == -1:
		e = rrd_get_error()
		rrd_clear_error()
		raise RRDLibError(e)
	else:
		a = None
		if prdata:
			# this doesn't actually work yet
			a = []
			for i in prdata:
				a.append(i)
		return (xsize.value, ysize.value, a)

if RRDTOOL_VERSION >= 1.3:
	@needs_argv
	@librrd_wrapper(rrd_graph_v)
	@returns_info
	def graph_v(info):
		return info
	
# Info  ###############################################
# Not public in 1.2, an info_t is the same as an rrd_info_t
# /* rrd_info_t rrd_info(int, char **) */
rrd_info = librrd.rrd_info
rrd_info.argtypes = [c_int, POINTER(c_char_p)]
rrd_info.restype = POINTER(rrd_info_t)

if RRDTOOL_VERSION >= 1.3:
	# /* void rrd_info_free(rrd_info_t *) */
	rrd_info_free = librrd.rrd_info_free
	rrd_info_free.argtypes = [POINTER(rrd_info_t)]

	# /* void rrd_info_print(rrd_info_t * data) */
	rrd_info_print = librrd.rrd_info_print
	rrd_info_print.argtypes = [POINTER(rrd_info_t)]

@needs_argv
@librrd_wrapper(rrd_info)
@returns_info
def info(info):
	""" info filename """
	return info

if RRDTOOL_VERSION < 1.3:
	info = rrd_info12_wrapper(info)
	infodict = info
else:
	infodict = rrd_info12_wrapper(info)

@needs_rrdtool_version(1.3)
def info_free(info_p):
	librrd.rrd_info_free(info_p)

@needs_rrdtool_version(1.3)
def info_print(info_p):
	librrd.rrd_info_print(info_p)

# Last  ###############################################
# /* time_t rrd_last(int, char **) */
rrd_last = librrd.rrd_last
rrd_last.argtypes = [c_int, POINTER(c_char_p)]
rrd_last.restype = time_t

# /* time_t rrd_last_r(const char * filename, c_int) */
rrd_last_r = librrd.rrd_last_r
rrd_last_r.argtypes = [c_char_p, c_int]
rrd_last_r.restype = time_t

@needs_argv
@librrd_wrapper(rrd_last)
def last(ts):
	""" last filename """
	return ts

# Resize  ###############################################
# /* int rrd_resize(int, char **) */
rrd_resize = librrd.rrd_resize
rrd_resize.argtypes = [c_int, POINTER(c_char_p)]
rrd_resize.restype = c_int

@needs_argv
@librrd_wrapper(rrd_resize)
def resize(ret):
	""" resize filename rra-num GROW|SHRINK rows """
	return ret

# Restore  ###############################################
# /* int rrd_restore(int, char **) */
rrd_restore = librrd.rrd_restore
rrd_restore.argtypes = [c_int, POINTER(c_char_p)]
rrd_restore.restype = c_int

@needs_argv
@librrd_wrapper(rrd_restore)
def restore(ret):
	""" resize filename rra-num GROW|SHRINK rows """
	return ret

# Tune  ###############################################
# /* int rrd_tune(int, char **) */
rrd_tune = librrd.rrd_tune
rrd_tune.argtypes = [c_int, POINTER(c_char_p)]
rrd_tune.restype = c_int

@needs_argv
@librrd_wrapper(rrd_tune)
def tune(ret):
	""" tune filename [--heartbeat|-h ds-name:heartbeat] [--minimum|-i ds-name:min] [--maximum|-a ds-name:max] [--data-source-type|-d ds-name:DST] [--data-source-rename|-r old-name:new-name] """
	return ret

# Update  ###############################################
# /* int rrd_update(int, char **) */
rrd_update = librrd.rrd_update
rrd_update.argtypes = [c_int, POINTER(c_char_p)]
rrd_update.restype = c_int

# /* int rrd_update_r(const char *filename, const char *_template, int argc, const char **argv) */
rrd_update_r = librrd.rrd_update_r
rrd_update_r.argtypes = [c_char_p, c_char_p, c_int, POINTER(c_char_p)]
rrd_update_r.restype = c_int

# /* rrd_info_t rrd_update_v(int, char **) */
rrd_update_v = librrd.rrd_update_v
rrd_update_v.argtypes = [c_int, POINTER(c_char_p)]
rrd_update_v.restype = POINTER(rrd_info_t)

@needs_argv
@librrd_wrapper(rrd_update)
def update(ret):
	""" update filename [--template|-t ds-name[:ds-name]...] N|timestamp:value[:value...] [timestamp:value[:value...] ...] """
	return ret

def update_r(filename, template, *args):
	raise NotImplementedError

@needs_argv
@librrd_wrapper(rrd_update_v)
@returns_info
def update_v(info):
	return info

# Xport ####################################################
# /* int rrd_xport(int argc, char **argv, int *xsize, time_t *start, time_t *end, unsigned long *step, unsigned long *col_cnt, char ***legend_v, rrd_value_t **data) */
rrd_xport = librrd.rrd_xport
rrd_xport.argtypes = [c_int, POINTER(c_char_p), POINTER(c_int), POINTER(time_t), POINTER(time_t), POINTER(c_ulong), POINTER(c_ulong), POINTER(POINTER(c_char_p)), POINTER(POINTER(rrd_value_t))]
rrd_xport.restype = c_int

@needs_argv
def xport(argv):
	""" xport filename details """
	start = time_t()
	end = time_t()
	step = c_ulong()
	col_cnt = c_ulong()
	legend_v = pointer(c_char_p())
	data = pointer(rrd_value_t())
	if rrd_xport(len(argv), argv, None, byref(start), byref(end), byref(step), byref(col_cnt), byref(legend_v), byref(data)) == -1:
		e = rrd_get_error()
		rrd_clear_error()
		raise RRDLibError(e)
	else:
		legend = legend_v.contents

		data_points = []
		pos = 0
		rows = (end.value - start.value) / step.value
		for row in xrange(rows):
			dp = []
			for ds in xrange(col_cnt.value):
				dv = data[pos]
				if isnan(dv):
					dv = None
				dp.append(dv)
				pos += 1
			data_points.append(tuple(dp))

		return (start.value, end.value, step.value, rows, legend, data_points)
	
# isnan #################################################
# /* int isnan(double) */ may not be in librrd always (windows?)
# More support for rrd_info
isnan = librrd.isnan
isnan.restype = c_int
isnan.argtypes = [c_double]

import rrdfile

class RRDFileError(Exception): pass

class RRDFile(object):
	class DS(object):
		def __init__(self, ds_info):
			""" create ds objects from a ds dict from rrd_info() """
			self.ds_name = ds_info['ds_name']
			self.type = ds_info['type']

			for (k,v) in ds_info.items():
				setattr(self, k, v)

			if hasattr(self, 'max') and self.max is None:
				self.max = 'U'
			if hasattr(self, 'min') and self.min is None:
				self.min = 'U'

			if self.type in ('ABSOLUTE', 'COUNTER', 'DERIVE', 'GAUGE'):
				self.spec = "DS:%s:%s:%s:%s:%s" % (self.ds_name, self.type,
					self.minimal_heartbeat, self.min, self.max)
			elif self.type in ('COMPUTE',):
				self.spec = "DS:%s:%s:%s" % (self.ds_name, self.type, self.cdef)
			else:
				raise RRDFileError("Unknown Data Source type '%s'" % self.type)

		def __repr__(self):
			return self.get_spec()

		def __str__(self):
			return self.get_spec()

		def get_spec(self):
			# DS:ds-name:GAUGE | COUNTER | DERIVE | ABSOLUTE:heartbeat:min:max
			# DS:ds-name:COMPUTE:rpn-expression
			return self.spec

	class RRA(object):
		def __init__(self, rra_info):
			""" create rra objects from an rra dict from rrd_info() """
			self.cf = rra_info['cf']
			for (k,v) in rra_info.items():
				if not hasattr(v, '__iter__'):
					setattr(self, k , v)

			if not hasattr(self, 'rra_num'):
				self.rra_num = "?"

			if self.cf in ('HWPREDICT', 'MHWPREDICT'):
				self.spec = "RRA:%s:%s:%s:%s:%s" % (self.cf,
					self.rows, self.alpha, self.beta, self.pdp_per_row)
				if hasattr(self, 'rra_num'):
					self.spec += ":" + self.rra_num
			elif self.cf in ('SEASONAL', 'DEVSEASONAL'):
				self.spec = "RRA:%s:%s:%s:%s" % (self.cf,
					self.pdp_per_row , self.gamma, self.rra_num)
			elif self.cf in ('FAILURES',):
				self.spec = "RRA:%s:%s:%s:%s" % (self.cf,
					self.failure_threshold, self.window_length, self.rra_num)
			elif self.cf in ('DEVPREDICT',):
				self.spec = "RRA:%s:%s:%s" % (self.cf,
					self.rows, self.rra_num)
			elif self.cf in ('AVERAGE', 'LAST', 'MAX', 'MIN'):
				self.spec = "RRA:%s:%s:%s:%s" % (self.cf,
					self.xff, self.pdp_per_row, self.rows)
			else:
				raise RRDFileError("Unkown RRA type '%s'" % self.cf)

		def __repr__(self):
			return self.get_spec()

		def __str__(self):
			return self.get_spec()

		def get_spec(self):
			# RRA:AVERAGE | MIN | MAX | LAST:xff:steps:rows
			# RRA:HWPREDICT:rows:alpha:beta:seasonal period[:rra-num]
			# RRA:SEASONAL:seasonal period:gamma:rra-num
			# RRA:DEVSEASONAL:seasonal period:gamma:rra-num
			# RRA:DEVPREDICT:rows:rra-num
			# RRA:FAILURES:rows:threshold:window length:rra-num
			return self.spec

	def __init__(self, filename):
		info = rrdfile.infodict(filename)

		for (k,v) in info.items():
			if not hasattr(v, '__iter__'):
				setattr(self, k , v)

		self.ds = {}
		for ds_name in info['ds']:
			self.ds[ds_name] = RRDFile.DS(info['ds'][ds_name])

		self.rra = []
		for rra_info in info['rra']:
			self.rra.append(RRDFile.RRA(rra_info))

	def __str__(self):
		spec = ""
		for c in dir(self):
			if not callable(getattr(self, c)) and not c.startswith('_'):
				spec += "%s:%s\n" % (c, getattr(self, c))
		return spec.strip()

	def get_create_cmd(self):
		return "rrdtool create %s -s %i %s %s" % (self.filename, self.step,
			" ".join([d.get_spec() for d in self.ds.values()]),
			" ".join([r.get_spec() for r in self.rra]))

	def dump(self):
		rrdfile.dump(self.filename)

def Create(filename, *args):
	rrdfile.create(filename, *args)
	return RRDFile(filename)

def Open(filename):
	""" Open a Round Robin Database file """
	return RRDFile(filename)

if (__name__ == '__main__'):
	try:
		rrdf = Open(sys.argv[1])
	except IndexError:
		print "usage: %s <rrdfile>" % sys.argv[0]
	print rrdf.get_create_cmd()

