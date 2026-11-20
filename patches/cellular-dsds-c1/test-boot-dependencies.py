"""Regression tests for cold-boot readiness and preserving saved user intent."""
import ast,pathlib,threading
from unittest.mock import patch
import data_session

class Nas:
    def __init__(self):self.values=iter((b'\0\1\2',b'\1\1\2',b'\1\1\1'));self.queries=0;self.closed=False
    def bind(self,svc,sub):assert (svc,sub)==(3,2)
    def request(self,mid):assert mid==0x24;self.queries+=1;return {1:next(self.values)}
    def close(self):self.closed=True
nas=Nas()
with patch.object(data_session,'Client',return_value=nas),patch.object(data_session.time,'sleep'):
    data_session.DataSession().wait_packet_service(2)
assert nas.queries==3 and nas.closed

# Compile the real controller class without running its daemon entry point.
p=pathlib.Path(__file__).with_name('cellular_daemon.py');tree=ast.parse(p.read_text())
node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Controller')
commands=[];active=[]
def run(*args):
    commands.append(args)
    return '\n'.join(active) if args[-1]=='--active' else ''
namespace={'run':run};exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),namespace)
Controller=namespace['Controller']
class Secondary:
    handle=None
    def connect(self):raise RuntimeError('injected transient connection failure')
    def close(self):pass
    def dds(self,sub):pass

for previous, bootstrap in ((2, True), (1, False), (0, False)):
    c=Controller.__new__(Controller);c.lock=threading.RLock();c.secondary=Secondary();c.slot=previous;c.busy=False;c.native_sim2=False
    saves=[];c.save=lambda:saves.append(c.slot);commands.clear();active.clear()
    try:c.select(2,bootstrap=bootstrap)
    except RuntimeError:pass
    else:raise AssertionError('failed connect reported success')
    assert c.slot==previous and not c.busy and not saves
    restored=any(cmd[-2:]==('up','cerro-sim1-cmnet') for cmd in commands)
    assert restored==(previous==1 and not bootstrap)

active.append('cerro-sim1-cmnet')
commands.clear()
c.slot=1
c.select(1,bootstrap=True)
assert not any(cmd[-2:]==('up','cerro-sim1-cmnet') for cmd in commands)
assert not saves and not c.busy
print('PS attach gate, connection rollback, and active-profile preservation passed')

native_commands = []
def native_run(*args):
    native_commands.append(args)
    if args[-1] == 'status':
        return 'enabled\n'
    if args[-1] == '--active':
        return 'cerro-sim1-cmnet\n'
    if args[-1] == '-K':
        return 'modem.generic.state : disabled\n'
    return ''

class NativeSubscription:
    def __init__(self):
        self.slot = 1
    def dds(self, slot):
        native_commands.append(('DDS', slot))
        self.slot = slot
    def current_dds(self):
        return self.slot
    def wait_packet_service(self, slot):
        native_commands.append(('PS', slot))

namespace['run'] = native_run
c.native_sim2 = True
c.secondary = NativeSubscription()
c.select(2)
assert ('nmcli', '--wait', '30', 'connection', 'down', 'cerro-sim1-cmnet') in native_commands
assert native_commands.index(('DDS', 2)) < native_commands.index(('PS', 2))
assert native_commands.index(('PS', 2)) < native_commands.index(('nmcli', '--wait', '55', 'connection', 'up', 'cerro-sim2-gsm'))
assert native_commands[-1] == ('nmcli', 'connection', 'modify', '--temporary', 'cerro-sim2-gsm', 'connection.autoconnect', 'yes')
assert saves == [2]
print('Native SIM2 selects DDS before activating GSM and enables runtime-only autoconnect')
