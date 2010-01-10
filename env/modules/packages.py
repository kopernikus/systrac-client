import os
from os.path import join as joinpath
from subprocess import Popen, PIPE
from config import Option, ExtensionOption
from core import implements, Component, ExtensionPoint,\
        SysTracError, Interface
from base import ISystemModule

import cherrypy as cp

class IPackageManager(Interface):
    def search(pkgname):
      "search for package"
      
    def install(pkgname):
        """install/update a package"""
      
    def remove(pkgname):
      """uninstall package"""
      
    def update():
        """update the package database"""
    
    def upgrade():
        """perform system upgrade"""
        
    def updates():
        """list packages with new versions"""
    
    def info(pkgname):
        """detailed info for package 'name'"""

class PackageManagerModule(Component):
    implements(ISystemModule)
    
    children = ExtensionPoint(IPackageManager)
    #default package manager
    default_manager = ExtensionOption('systrac', 'default_package_manager', 
                              IPackageManager)
  
    def __init__(self):
        self.log.debug("Got IServiceManager providers %s" % self.children)
        
    @classmethod
    def supported_plattform(cls, p, f, r):
      """check plattform, flavour, release"""
      return True
        
    def description(self):
        return "Package management"
        
    def get_path(self):
        return 'packages'
        
    @cp.expose
    @cp.tools.set_content_type()
    def search(self, pkgname):
        return self.default_manager.search(pkgname)
    
    @cp.expose
    @cp.tools.set_content_type()
    def info(self, pkgname):
        return self.default_manager.info(pkgname)
    
    @cp.expose
    @cp.tools.set_content_type()
    def index(self):
        return self.default_manager.index()
        
class AptPackageManager(Component):
    implements(IPackageManager)

    def __init__(self):
        self.answer = {
                'status':200,
                'result': 'success',
                'errors':[]}
                
    @classmethod
    def supported_plattform(cls, p, f, r):
      """check plattform, flavour, release"""
      if p == 'linux' and f in ['debian', 'ubuntu']:
          return True
      return False
        
    def description(self):
        return "apt package management"
    

    def search(self, pkgname):
        res = []
        p = Popen('apt-cache search %s | grep %s' % (pkgname, pkgname), shell=True, stdout=PIPE, stderr=PIPE)
        for line in p.stdout.readlines():
            parts = line.split(' - ', 1)
            if len(parts) == 2:
                res.append({'name':parts[0], 'desc':parts[1].rstrip()})
            else: print "invalid package "+line
        out = self.answer.copy()
        out.update({'data':res})
        return self.json.dumps(out)
    

    def info(self, pkgname):
        out = self.answer.copy()
        res = {}; missing = False
        p = Popen('dpkg -s %s' % pkgname, shell=True, stdout=PIPE, stderr=PIPE)
        err = p.stderr.read()
        if err: 
            out.update({'status':404, 'errors':[err]})
            return self.json.dumps(out)
            
        for line in p.stdout.readlines():
          parts = line.split(':')
          if len(parts) == 2:
            res[parts[0].strip()] = parts[1].strip()
  
        out.update({'data':res})
        return self.json.dumps(out)
            
    def index(self):
        return self.json.dumps(
            {'methods':['search(pkgname)', 'info(pkgname)'],
             'desc': "simple interface to the systems package manager"})
