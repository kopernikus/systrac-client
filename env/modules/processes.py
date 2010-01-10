import os
from os.path import join as joinpath
from subprocess import Popen, PIPE
from config import Option, ExtensionOption
from core import implements, Component, ExtensionPoint,\
        SysTracError, Interface
from base import ISystemModule

import cherrypy as cp
import psutil

class IProcessInfo(Interface):
    def info(pid):
        "return a json dict with process information"
    
    def list():
        "return a list of running processes"
    
    def kill(pid):
        """kill process by pid"""
        
class ProcessModule(Component):
    implements(ISystemModule, IProcessInfo)


    #this starts to get painful, not needed here it's just the dumb loader
    @classmethod
    def supported_plattform(cls):
        yield ('linux', 'ubuntu', '9.04')
        yield ('linux', 'debian', '5.0')
        
    def description(self):
        return "Process information"
        
    def get_path(self):
        return 'processes'
        
    @cp.expose
    @cp.tools.set_content_type()
    def info(self, pid):
        try:
            pid = int(pid)
            p = psutil.Process(pid) 
            p.uid 
            info = p._procinfo.__dict__.copy()
            info['memory'] = p.get_memory_info()
            info['cpu'] = p.get_cpu_times()
            return self.json.dumps(info)
        except psutil.error.NoSuchProcess:
            return self.json.dumps({'status':404, 'errors':['PROCESS_NOT_FOUND']})
        except ValueError:
            return self.json.dumps({'status':510, 'errors':['INVALID_ARGUMENT']})
            
    @cp.expose
    @cp.tools.set_content_type()
    def list(self):
        r = cp.request
        method, uri, proto = r.request_line.split()
        uri = '/'.join(uri.split('/')[1:-2])
        res = []
        for p in psutil.get_process_list():
          if not p.path: continue # exclude kernel threads....
          res.append(
            {'pid': p.pid, 
             'info': "http://%s:%s/%s/info/%s" % (
                r.local.name, r.local.port, uri, p.pid),
              'name': p.name,
              'cmdline': " ".join(p.cmdline)})
              
        return self.json.dumps(res) 

    @cp.expose
    @cp.tools.set_content_type()
    def index(self):
        return self.json.dumps(
            {'methods':['list', 'info(pid)'],
             'desc': "process information"})

