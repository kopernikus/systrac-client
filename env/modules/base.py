# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 Paul Kölle
# All rights reserved.

from core import implements, Component, ExtensionPoint, SysTracError
from interfaces import ISystemModule, IBaseModule
import cherrypy as cp

#setup the set_content_type Tool before loading any pagehandlers
def set_content_type(ct=None):
    if cp.response.status == 404:
        return # probably all but 2xx unless errors are convertet to json too
    if ct:
        cp.response.headers['Content-Type'] = ct
    else:
        cp.response.headers['Content-Type'] = 'application/json' #self.default_content_type
cp.tools.set_content_type = cp.Tool('before_finalize', set_content_type)


class SystemBaseModule(Component):
    implements(IBaseModule)

    children = ExtensionPoint(ISystemModule)
    
    @classmethod
    def supported_plattform(cls, p, f, r):
      """check plattform, flavour, release"""
      return True
    
    def __init__(self):
        self.log.debug("ISystemModule Providers: %s" % self.children)
        for provider in self.children:
            path = provider.get_path()
            provider.exposed = True
            #self.log.debug("Adding provider %s for path /%s" % (provider.__class__.__name__, path))
            setattr(self, path, provider)
                
    # the IBaseModuleProvider
    def get_path(self):
        return 'system'

    @cp.expose
    @cp.tools.set_content_type()
    def index(self, *args, **kwargs):
        subpaths = [c.get_path() for c in self.children]
        return self.json.dumps({"children": subpaths})

        
#fixme, use one of the cherrypy dispatchers
class Dispatcher(Component):
    children = ExtensionPoint(IBaseModule)

    def __init__(self, *args):
        # add IBaseModuleProviders as direct pagehandlers
        #self.log.debug(" Providers: %s" % self.children)
        self.subpaths = []
        for provider in self.children:
            path = provider.get_path()
            provider.exposed = True
            self.log.debug("Adding provider %s for path /%s" % (provider.__class__.__name__, path))
            print "Adding provider %s for path /%s" % (provider.__class__.__name__, path)
            setattr(self, path, provider)
            self.subpaths.append(path)


    def __call__(self, host, port):
        cp.server.socket_host = host
        cp.server.socket_port = port
        cp.quickstart(self)

    @cp.expose
    def index(self, *args, **kwargs):
        return self.json.dumps({"children": self.subpaths})