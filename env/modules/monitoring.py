# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 Paul Kölle
# All rights reserved.

import sys, os, time
import telnetlib
from os.path import join as joinpath
import cherrypy as cp

from subprocess import Popen, PIPE
from core import implements, Component, ExtensionPoint,\
        IBaseModuleProvider, SysTracError, Interface
from config import Option, IntOption, ListOption
from env import json

class IMonitoringModule(Interface):
    """A module for handling system tasks or providing
    system related information"""
    
    def description():
        """return a string describing the module"""

    def nodes():
      """return a list of nodes (hostnames)"""
      
    def metrics(hostname):
      """return a list of metrics"""
      
    def values(hostname, *metrics):
      """return values for all metrics in the *metrics list"""
      
class MonitoringBaseModule(Component):
    implements(IBaseModuleProvider)

    children = ExtensionPoint(IMonitoringModule)
    
    @classmethod
    def supported_plattform(cls):
        yield ('linux', 'ubuntu', '9.04')
        yield ('linux', 'debian', '5.0')
        
    def __init__(self):
        self.log.debug("IMonitoringModule Providers: %s" % self.children)
            
    def get_path(self):
        return 'monitoring'

    @cp.expose
    @cp.tools.set_content_type()
    def index(self):
        return self.json.dumps(
            {'methods':['nodes', 'metrics(host)', 'values(host, *metrics)'],
             'desc': "monitoring info"})


    def default(self, *args, **kwargs):
        return "Default called: %s, %s -- %s" % (args, kwargs, request)
        
    #IMonitoringModule methods
    @cp.expose
    @cp.tools.set_content_type()
    def nodes(self):
        res = []
        for c in self.children:
            res.extend(c.nodes())
        return self.json.dumps(res)
    
    @cp.expose
    @cp.tools.set_content_type()
    def metrics(self, host):
        res = []
        for c in self.children:
            res.append(c.metrics(host))
        return self.json.dumps(res)
        
    @cp.expose
    @cp.tools.set_content_type()
    def values(self, host, *metrics):
        res = []
        for c in self.children:
            res.append(c.values(host, *metrics))
        return self.json.dumps(res)
        
class MuninNodeProxy(Component):
    implements(IMonitoringModule)
    
    proxy_hosts = ListOption('munin', 'proxy_hosts', 'localhost')
    
    @classmethod
    def supported_plattform(cls):
        yield ('linux', 'ubuntu', '9.04')
        yield ('linux', 'debian', '5.0')
        
    def nodes(self):
        return self.proxy_hosts
        
    def metrics(self, host):
        if ':' in host: host, port = host.split(':')
        else: port = 4949
        
        t = telnetlib.Telnet(host, port)
        time.sleep(.2)
        res = t.read_eager() #read the banner
        t.write('list\n')
        time.sleep(.2)
        data = ''
        try:
            res = t.read_eager()
            while res: 
                data += res
                res = t.read_eager()
        except EOFError:
            pass
        return data.strip().split() #return list of metric names
        
    def values(self, host, metric):
        if ':' in host: host, port = host.split(':')
        else: port = 4949
        
        t = telnetlib.Telnet(host, port)
        time.sleep(.2)
        res = t.read_eager() #read the banner
        t.write('fetch %s\n' % metric)
        time.sleep(.2)
        data = ''
        try:
            res = t.read_eager()
            while res: 
                data += res
                res = t.read_eager()
        except EOFError:
            pass
        return data.strip().split('\n')
        
class MuninModule(Component):
    implements(IMonitoringModule)
    
    rrdpath = Option('munin', 'rrdpath', '/var/lib/munin')
    
    blacklines = ["dbdir", "version", "logdir", "tmpldir", "rundir", "htmldir"]
    blackparams = ['use_node_name', 'address']
    cache = {}
    result = {'status':200, 'data': {}, 'errors':[]}
    
    @classmethod
    def supported_plattform(cls):
        yield ('linux', 'ubuntu', '9.04')
        yield ('linux', 'debian', '5.0')
        

    def nodes(self):
        "return domains and hosts"
        data = self._filter_datafile()
        return data['hosts']
      
    def metrics(self, host):
        data = self._filter_datafile()
        metrics = data['metrics'].get(host) #FIXME...
        if metrics is None:
            return []
        return metrics
        
    def values(self, host, *metrics):
        try:
            rrd = metrics[0]
            shortname, domain = host.split('.', 1)
        except IndexError:
            self.log.info("Invalid hostname %s passed to MuninNode.values()")
            return []
          
        fname = joinpath(self.rrdpath, domain, host+'-'+rrd+'-g.rrd')
        self.log.debug("trying to read %s" % fname)
        if os.path.isfile(fname):
            p = Popen('rrdtool info '+fname, shell=True, stdout=PIPE, stdin=PIPE, stderr=PIPE)
            return p.stdout.readlines()
        return []
        
    def _filter_datafile(self):
        try:
            last = self._lastrun
            now = time.time()
            if now - last < 15: # ten seconds
              return self.cache
        except AttributeError:
            pass
            
        f = open(joinpath(self.rrdpath, 'datafile'))
        data = {'domains':set(), 'hosts':set(), 'metrics':{} }
        
        for line in f.readlines():
            if  line.split()[0] in self.blacklines:
                continue
            domain, rest = line.split(';', 1)
            host, rest = rest.split(':', 1)
            if rest.split()[0] in self.blackparams:
                continue
            mname, mvalue = rest.split('.', 1) #[:2]
            
            data['domains'].add(domain)
            data['hosts'].add(host)
            if data['metrics'].get(host) is not None:
                mkey, mvalue = mvalue.split(' ', 1)
                if data['metrics'][host].get(mname):
                    data['metrics'][host][mname][mkey] = mvalue
                else:
                    data['metrics'][host][mname] = {mkey:mvalue}
            else:
                data['metrics'][host] =  {}
        f.close()
        
        #add URL to value?....
        
        #json doesn't understand set()
        data['domains'] = self.cache['domains'] = list(data['domains'])
        data['hosts'] = self.cache['domains'] = list(data['hosts'])
        self.cache['metrics'] = data['metrics']
        self._lastrun = time.time()
        return data

