# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 Paul Kölle
# All rights reserved.

import os
from os.path import join as joinpath
from subprocess import Popen, PIPE

from config import Option
from core import implements, Component, ExtensionPoint,\
        IBaseModuleProvider, SysTracError, Interface
import cherrypy as cp

class IConfigModule(Interface):
    """access to /etc"""
    
    def description():
        """return a string describing the module"""

    def get_path():
        """the url path"""
        
class ConfigBaseModule(Component):
    implements(IBaseModuleProvider)

    children = ExtensionPoint(IConfigModule)
    
    @classmethod
    def supported_plattform(cls):
        yield ('linux', 'ubuntu', '9.04')
        yield ('linux', 'debian', '5.0')
        
    def __init__(self):
        self.log.debug("IMonitoringModule Providers: %s" % self.children)
        for provider in self.children:
            path = provider.get_path()
            provider.exposed = True
            self.log.debug("Adding provider %s for path /%s" % (provider.__class__.__name__, path))
            setattr(self, path, provider)
            
    def get_path(self):
        return 'etc'

    @cp.expose
    @cp.tools.set_content_type()
    def index(self, *args, **kwargs):
        subpaths = [c.get_path() for c in self.children]
        return self.json.dumps({"children": subpaths})


class MuninConfig(Component):
    implements(IConfigModule)
    
    enabled_plugindir = Option('munin', 'enabled_plugindir', '/etc/munin/plugins')
    all_plugindir = Option('munin', 'all_plugindir', '/usr/share/munin/plugins')
    plugin_conf = Option('munin', 'plugin_conf', '/etc/munin/plugin-conf.d/munin-node')
    munin_conf = Option('munin', 'munin_conf', '/etc/munin/munin.conf')
    
    @classmethod
    def supported_plattform(cls):
        yield ('linux', 'ubuntu', '9.04')
        yield ('linux', 'debian', '5.0')
        
    def get_path(self):
        return 'munin'
    
    @cp.expose
    @cp.tools.set_content_type()
    def index(self):
        return self.json.dumps(
            {'methods':['plugins', 'plugin', 'disable']})
    

    @cp.expose
    @cp.tools.set_content_type()
    def plugins(self):
        enabled = os.listdir(self.enabled_plugindir)
        all = os.listdir(self.all_plugindir)
        return self.json.dumps({'all': all, 'enabled': enabled})
        
    @cp.expose
    @cp.tools.set_content_type()
    def plugin(self, name, suffix=None):
        print "SUFFIX: ", suffix
        method = cp.request.method
        if method == 'POST':
            return self._enable_plugin(name, suffix)
        elif method == 'DELETE':
            return self._disable_plugin(name)
        elif method == 'GET':
            return self._plugin_value(name)
            
    @cp.expose
    @cp.tools.set_content_type()
    def pluginconfig(self):
        method = cp.request.method
        if method == 'GET':
            return self._get_pluginconfig()
        elif method == 'POST':
            return self._change_pluginconfig()
    
    
    @cp.expose
    @cp.tools.set_content_type()
    def muninconfig(self):
        method = cp.request.method
        if method == 'GET':
            return self._get_muninconfig(name, suffix)
        elif method == 'POST':
            return self._change_muninconfig(name, suffix)
            
    def _enable_plugin(self, name, suffix):
        src = joinpath(self.all_plugindir, name)
        if suffix: name = name+suffix
        
        if os.path.isfile(src):
            try:
                os.symlink(src, joinpath(self.enabled_plugindir, name))
            except OSError, e:
                return self.json.dumps({
                    'status':'error', 'errors':[str(e)]}) 

            return self.json.dumps({
                'status': 'success', 'message': 'enabled plugin %s' % name})
            
        else:
            return self.json.dumps({
                'status':'error', 'errors':['plugin %s not found' % name]}) 

    def _disable_plugin(self, name):
        src = joinpath(self.enabled_plugindir, name)
        if os.path.islink(src):
            try:
                os.unlink(src)
            except OSError, e:
                return self.json.dumps({
                    'status':'error', 'errors':[str(e)]})
            return self.json.dumps({
                'status':'success', 'message': 'disabled plugin %s' % name})
        else:
            return self.json.dumps({
                'status':'error', 'errors':['plugin %s not found' % name]})
                
        
    def _plugin_value(self, name):
        src = joinpath(self.enabled_plugindir, name)
        
        if os.path.isfile(src):
            p =Popen(src, shell=True, stdout=PIPE)
            p.wait()
            return self.json.dumps(dict([l.split() 
                    for l in p.stdout.readlines()]))
        else:
            return self.json.dumps({'errors': ['plugin %s not found' % name]})
            
    def _change_pluginconfig(self, data):
        oldconfig = self.json.loads(self._get_pluginconfig())
        updated = self.json.load(cp.request.rfile)
        oldconfig.update(updated)
        
    def _get_pluginconfig(self):
        res = {}; section = []; sh = None; 
        hdr = re.compile(r'\[(.*?)\]')
        for line in open(self.plugin_conf).readlines():
            m = hdr.match(line)
            if m and sh and section:
                res[sh] = section
                section = []; sh = m.group(1)
            elif m: sh = m.group(1)
            else:
                data = line.strip() 
                if data: section.append(data)
        return self.json.dumps(res)
        
        
