# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 Paul Kölle
# All rights reserved.

import os
from os.path import join as joinpath
from subprocess import Popen, PIPE
from config import Option, ExtensionOption
from core import implements, Component, ExtensionPoint,\
        IBaseModuleProvider, SysTracError, Interface

import cherrypy as cp

class ISystemModule(Interface):
    """A module for handling system tasks or providing
    system related information"""
    
    def description():
        """return a string describing the module"""

    def get_path():
        """the url path"""


class SystemBaseModule(Component):
    implements(IBaseModuleProvider)

    children = ExtensionPoint(ISystemModule)
    
    @classmethod
    def supported_plattform(cls):
        yield ('linux', 'ubuntu', '9.04')
        yield ('linux', 'debian', '5.0')
    
    def __init__(self):
        self.log.debug("ISystemModule Providers: %s" % self.children)
        for provider in self.children:
            path = provider.get_path()
            provider.exposed = True
            self.log.debug("Adding provider %s for path /%s" % (provider.__class__.__name__, path))
            setattr(self, path, provider)
                
    # the IBaseModuleProvider
    def get_path(self):
        return 'system'

    @cp.expose
    @cp.tools.set_content_type()
    def index(self, *args, **kwargs):
        subpaths = [c.get_path() for c in self.children]
        return self.json.dumps({"children": subpaths})

        
        
