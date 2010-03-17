# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 Paul Kölle
# All rights reserved.

import sys, os, time
import telnetlib
from os.path import join as joinpath
import cherrypy as cp

from subprocess import Popen, PIPE
from core import implements, Component, ExtensionPoint, SysTracError
from config import Option, IntOption, ListOption

from interfaces import IMonitoringModule, IBaseModule

class MonitoringBaseModule(Component):
    implements(IBaseModule)

    children = ExtensionPoint(IMonitoringModule)
    
    @classmethod
    def supported_plattform(cls, p, f, r):
      """check plattform, flavour, release"""
      return True
        
    def __init__(self):
        self.log.debug("IMonitoringModule Providers: %s" % self.children)
        self._cached_children = {}

    def get_path(self):
        return 'monitoring'

    @cp.expose
    @cp.tools.set_content_type()
    def index(self):
        return self.json.dumps(
            {'methods':['metrics', 'values(*metrics)'],
             'desc': "monitoring info"})


    def default(self, *args, **kwargs):
        return "Default called: %s, %s -- %s" % (args, kwargs, request)
        
    #IMonitoringModule methods
    @cp.expose
    @cp.tools.set_content_type()
    def metrics(self):
        res = []
        for child in self.children:
            r = child.metrics()
            if r:
                self._cached_children[child] = r
                res.extend(r)
        return self.json.dumps(res)
        
    @cp.expose
    @cp.tools.set_content_type()
    def values(self, *metrics):
        print "MonitoringModule.values() called with metrics %s(%s)" % (metrics, type(metrics))
        res =[]
        if self._cached_children:
            for child,metrics in self._cached_children.items():
                res.extend(child.metrics(*metrics))
            return self.json.dumps(res)

        for child in self.children:
            res.extend(child.values( *metrics))
        return self.json.dumps(res)
        
class MuninNodeProxy(Component):
    implements(IMonitoringModule)

    port = 4949

    @classmethod
    def supported_plattform(cls, p, f, r):
      """check plattform, flavour, release"""
      #FIXME: check for running munin-node (open socket on localhost:4949)
      return True
        
    def metrics(self):
        """get a list of metrics"""
        t = telnetlib.Telnet('localhost', self.port)
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
        
    def values(self, *metric):
        """get current values for each metric in *metrics"""
        t = telnetlib.Telnet('localhost', self.port)
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
        


