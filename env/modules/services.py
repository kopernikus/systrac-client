import os
from os.path import join as joinpath
from subprocess import Popen, PIPE
from config import Option, ExtensionOption
from core import implements, Component, ExtensionPoint, SysTracError

import cherrypy as cp

from interfaces import ISystemModule, IServiceManager






            
class SysVServiceModule(Component):
    implements(IServiceManager)
    
    def __init__(self):
        self.basedir = '/etc/init.d'
        self.blacklist = [
            'skeleton', 'rc', 'rcS','pppd-dns'
            'open-vm-tools.dpkg-old', 'README',
            'anacron', 'acpi-support', 'alsa-utils',
            'apmd', 'apport', 'binfmt-support',
            'brltty', 'console-setup', 'dkms_autoinstaller',
            'dns-clean', 'gdm', 'halt', 'hotkey-setup', 
            'keyboard-setup', 'killprocs', 'laptop-mode',
            'linux-restricted-modules-common',
            'module-init-tools', 'mountoverflowtmp',
            'networking', 'ondemand', 'open-vm-tools',
            'pulseaudio', 'procps', 'rc', 'rc.local',
            'readahead', 'readahead-desktop', 'reboot',
            'rmnologin', 'screen-cleanup', 'sendsigs',
            'single', 'stop-bootlogd', 'stop-bootlogd-single',
            'stop-readahead', 'system-tools-backends', 'udev',
            'udev-finish', 'wpa-ifupdown']
    
        self.answer = {
                'status':None,
                'content': [],
                'errors':[]}
                
    @classmethod
    def supported_plattform(cls, p, f, r):
      """check plattform, flavour, release"""
      if p == 'linux' and f in ['debian', 'ubuntu']:
          return True
      return False
      
    def index(self):
        return self.json.dumps(
            {'methods':['list', 'start', 'stop', 'restart', 'status']})
 

    def list(self):
        raw =  [e for e in os.listdir('/etc/init.d')
                if not e.endswith('.sh')]
        srv = [e for e in raw if e not in self.blacklist]
        return self.json.dumps({'status': 200, 'content': [srv]})

 
    def start(self, name):
        cmd = joinpath(self.basedir, name)
        if self._filter_cmd(cmd):
            out, err = self._run_cmd(cmd, 'start')
            return self.json.dumps({'status':201, 'response':[out], 'errors':[err]})
        return self.json.dumps({'status':404, 'errors':['service not found']})
        
    def status(self, name):
        cmd = joinpath(self.basedir, name)
        if self._filter_cmd(cmd):
            out, err = self._run_cmd(cmd, 'status')
            return self.json.dumps({'status':201, 'response':[out], 'errors':[err]})
        return self.json.dumps({'status':404, 'errors':['service not found']})
        
    def stop(self, name):
        cmd = joinpath(self.basedir, name)
        if self._filter_cmd(cmd):
            out, err = self._run_cmd(cmd, 'stop')
            return self.json.dumps({'status':201, 'response':[out], 'errors':[err]})
        return self.json.dumps({'status':404, 'errors':['NOTFOUND']})
    
    def restart(self, name):
        cmd = joinpath(self.basedir, name)
        if self._filter_cmd(cmd):
            out, err = self._run_cmd(cmd, 'restart')
            return self.json.dumps({'status':201, 'response':[out], 'errors':[err]})
        return self.json.dumps({'status':404, 'errors':['service not found']})


    def _filter_cmd(self, cmd):
        if os.path.isfile(cmd) and name not in self.blacklist:
           return True
        return False

    def _run_cmd(self, cmd, args):
        p = Popen(cmd+' '.join(args), stderr=PIPE, stdout=PIPE, shell=True)
        p.wait()
        return p.stdout.read(), p.stderr.read()

class UpstartServiceModule(Component):
    implements(IServiceManager)
    
    def __init__(self):
        self.answer = { 'status':None, 'response': [], 'errors':[]}
                
    @classmethod
    def supported_plattform(cls, p, f, r):
      """check plattform, flavour, release"""
      if p == 'linux' and f in ['debian', 'ubuntu'] and r >= 10.4:
          return True
      return False
        
    def description(self):
        return "Service management with Upstart"
        
    def start(self, service):
        pass
      
    def stop(self, service):
        pass
      
    def restart(self, service):
        pass
      
    def list(self):
        pass
      
    def status(self, service):
        pass

class ServiceModule(Component):
    implements(ISystemModule)
    
    children = ExtensionPoint(IServiceManager)
    #default service manager
    default_manager = ExtensionOption('systrac', 'service_manager', 
                              IServiceManager, default=SysVServiceModule)
  
    def __init__(self):
        self.log.debug("Got IServiceManager providers %s" % self.children)
        
    #FIXME: collect all platforms from self.children
    @classmethod
    def supported_plattform(cls, p, f, r):
      """check plattform, flavour, release"""
      return cls.default_manager.default.supported_plattform(p, f, r)
        
    def description(self):
        return "Service management"
        
    def get_path(self):
        return 'services'
        
    @cp.expose
    @cp.tools.set_content_type()
    def start(self, name):
        return self.default_manager.start(name)
  
    @cp.expose
    @cp.tools.set_content_type()
    def stop(self, name):
        return self.default_manager.start(name)
    
    @cp.expose
    @cp.tools.set_content_type()
    def restart(self, name):
        return self.default_manager.start(name)
        
    @cp.expose
    @cp.tools.set_content_type()
    def status(self, name):
        return self.default_manager.status(name)
    
    @cp.expose
    @cp.tools.set_content_type()
    def list(self):
        return self.default_manager.list()
    
    @cp.expose
    @cp.tools.set_content_type()
    def index(self):
        return self.json.dumps(
            {'methods':['list', 'start', 'stop', 'restart', 'status']})
