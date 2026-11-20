#!/usr/bin/env python3
"""Owner-only local API for this phone's two SIMs, SMS and selected data call."""
import json,os,pathlib,pwd,signal,socket,struct,subprocess,threading,time
from data_session import DataSession,run
from qmi_socket import Client,routes
from sms_store import SmsStore

STATE=pathlib.Path('/var/lib/cerro-cellular-c1');SOCK='/run/cerro-cellular/control.sock'
# Stable desktop UID survives an owner-requested login/group rename.
OWNER=pwd.getpwuid(int(os.environ.get('CERRO_DESKTOP_UID', '1000')))

def notify(value):
    endpoint=os.environ.get('NOTIFY_SOCKET')
    if endpoint:
        with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as s:
            s.connect('\0'+endpoint[1:] if endpoint.startswith('@') else endpoint);s.send(value.encode())

class Controller:
    def __init__(self):
        STATE.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.lock=threading.RLock();self.secondary=DataSession();self.sms=SmsStore(STATE)
        self.native_sim2 = os.environ.get('CERRO_NATIVE_SIM2') == '1'
        self.file=STATE/'data-slot.json';self.slot=int(json.loads(self.file.read_text())) if self.file.exists() else 1
        if self.slot not in (0,1,2):self.slot=1
        self.ready=False;self.busy=True
    def save(self):
        p=self.file.with_suffix('.tmp');p.write_text(json.dumps(self.slot));p.chmod(0o600);p.replace(self.file)
    def apply_data_slot(self, slot):
        if self.native_sim2:
            self.apply_native_data_slot(slot)
            return
        if self.secondary.handle:
            self.secondary.close()
        profile = 'cerro-sim1-cmnet'
        active = profile in run('nmcli', '-t', '-f', 'NAME', 'connection', 'show', '--active').splitlines()
        if slot == 1:
            self.secondary.dds(1)
            run('nmcli', 'connection', 'modify', profile, 'connection.autoconnect', 'yes')
            if not active:
                run('nmcli', '--wait', '45', 'connection', 'up', profile)
            return
        run('nmcli', 'connection', 'modify', profile, 'connection.autoconnect', 'no')
        if active:
            run('nmcli', '--wait', '30', 'connection', 'down', profile)
        if slot == 2:
            self.secondary.connect()
        else:
            self.secondary.dds(1)

    def apply_native_data_slot(self, slot):
        profiles = {1: 'cerro-sim1-cmnet', 2: 'cerro-sim2-gsm'}
        active = run('nmcli', '-t', '-f', 'NAME', 'connection', 'show', '--active').splitlines()
        selected = profiles.get(slot)
        if selected and run('env', 'LC_ALL=C', 'nmcli', '-t', '-f', 'WWAN', 'general', 'status').strip() != 'enabled':
            raise RuntimeError('请先开启系统的移动宽带')
        for index, profile in profiles.items():
            if index == slot:
                continue
            temporary = ('--temporary',) if index == 2 else ()
            run('nmcli', 'connection', 'modify', *temporary, profile, 'connection.autoconnect', 'no')
            if profile in active:
                run('nmcli', '--wait', '30', 'connection', 'down', profile)

        subscription = slot or 1
        if selected in active and self.secondary.current_dds() != subscription:
            run('nmcli', '--wait', '30', 'connection', 'down', selected)
            active.remove(selected)
        self.secondary.dds(subscription)
        if selected is None:
            return
        if selected not in active:
            if slot == 2:
                state = run('mmcli', '-m', 'any', '-K')
                if any(line.partition(':')[2].strip() == 'disabled' for line in state.splitlines()
                       if line.partition(':')[0].strip() == 'modem.generic.state'):
                    run('mmcli', '-m', 'any', '--enable')
                self.secondary.wait_packet_service(2)
            run('nmcli', '--wait', '55', 'connection', 'up', selected)
        if self.secondary.current_dds() != subscription:
            raise RuntimeError('数据连接的订阅已变化')
        # Keep SIM2 off on disk until DDS is selected on the next full boot.
        temporary = ('--temporary',) if slot == 2 else ()
        run('nmcli', 'connection', 'modify', *temporary, selected, 'connection.autoconnect', 'yes')

    def select(self,slot,bootstrap=False):
        if type(slot) is not int or slot not in (0,1,2):raise ValueError('请选择 SIM1、SIM2 或关闭数据')
        with self.lock:
            previous = self.slot
            self.busy=True
            try:
                self.apply_data_slot(slot)
                if slot != previous:
                    self.slot = slot
                    self.save()
            except Exception:
                self.slot = previous
                if not bootstrap and slot != previous:
                    try:
                        self.apply_data_slot(previous)
                    except Exception as error:
                        print('cerro-cellular: could not restore previous data selection:', type(error).__name__, flush=True)
                raise
            finally:self.busy=False
    def initialize(self):
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            v=subprocess.run(['mmcli','-m','any','-K'],capture_output=True,text=True,timeout=10)
            states=[line.split(':',1)[1].strip() for line in v.stdout.splitlines() if line.split(':',1)[0].strip()=='modem.generic.state']
            if states and (states[0] in ('enabled','registered','connected','connecting','searching')
                           or self.native_sim2 and states[0] == 'disabled'):break
            time.sleep(.5)
        else:raise RuntimeError('ModemManager hardware initialization not ready')
        with self.lock:self.sms.configure_routes()
        self.select(self.slot,bootstrap=True);self.ready=True
        notify('READY=1\nSTATUS=Dual SIM messaging and selected data initialized')
    def status(self):
        result={'ready':self.ready,'busy':self.busy,'data_slot':self.slot,'slots':[]}
        r=routes()
        for sub in (1,2):
            item={'slot':sub,'number':'','registered':False,'operator':'','technology':''}
            for service in (2,3):
                c=Client(service,r)
                try:
                    c.bind(service,sub)
                    if service==2:item['number']=c.request(0x24)[1].decode('ascii').strip('\0')
                    else:
                        v=c.request(0x24);serving=v.get(1,b'');plmn=v.get(0x12,b'')
                        item['registered']=bool(serving and serving[0]==1)
                        names={1:'CDMA',2:'3G',4:'2G GSM',5:'3G UMTS',8:'4G LTE',9:'3G',12:'5G NR'}
                        item['technology']=' + '.join(names.get(x,str(x)) for x in serving[5:])
                        if len(plmn)>=5:item['operator']=plmn[5:5+plmn[4]].decode(errors='replace')
                except Exception:item['error']='正在读取卡状态'
                finally:c.close()
            result['slots'].append(item)
        return result
    def dispatch(self,request):
        action=request.get('action')
        if action=='status':return self.status()
        if not self.ready:raise RuntimeError('双卡正在初始化，请稍候')
        if action=='messages':
            with self.lock:return self.sms.list()
        if action=='select_data':self.select(request.get('slot'));return {'selected':self.slot}
        if action=='send_sms':
            slot=request.get('slot');number=request.get('number');text=request.get('text')
            if type(slot) is not int or slot not in (1,2) or not isinstance(number,str) or not isinstance(text,str):raise ValueError('短信参数无效')
            with self.lock:self.sms.send(slot,number,text)
            return {'sent':True}
        raise ValueError('不支持的操作')

controller=Controller();server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
pathlib.Path('/run/cerro-cellular').mkdir(mode=0o755,exist_ok=True)
try:os.unlink(SOCK)
except FileNotFoundError:pass
server.bind(SOCK);os.chown(SOCK,0,OWNER.pw_gid);os.chmod(SOCK,0o660);server.listen(8)

def handle(conn):
    with conn:
        conn.settimeout(100)
        try:
            pid,uid,gid=struct.unpack('3i',conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            if uid not in (0,OWNER.pw_uid):raise PermissionError('此账户无权操作手机双卡')
            f=conn.makefile('rb');data=f.readline(16385)
            if len(data)>16384:raise ValueError('请求过长')
            request=json.loads(data)
            if not isinstance(request,dict):raise ValueError('请求无效')
            value=controller.dispatch(request);reply={'ok':True,'result':value}
        except Exception as exc:
            if isinstance(exc,(ValueError,PermissionError)):message=str(exc)
            elif isinstance(exc,(TimeoutError,socket.timeout)):message='操作状态未确认，请刷新检查，避免重复发送短信'
            else:message='操作未完成（'+type(exc).__name__+'），请刷新状态后重试'
            reply={'ok':False,'error':message}
        try:conn.sendall((json.dumps(reply,ensure_ascii=False)+'\n').encode())
        except (OSError,TimeoutError):pass

def initialize():
    try:controller.initialize()
    except Exception as exc:
        import traceback
        print('cerro-cellular initialization failed:',type(exc).__name__,'QMI code',getattr(exc,'error',None),flush=True)
        for frame in traceback.extract_tb(exc.__traceback__):
            print('  at',pathlib.Path(frame.filename).name,frame.lineno,frame.name,flush=True)
        notify('STATUS=Dual SIM initialization failed');os._exit(1)

def shutdown(*args):
    notify('STOPPING=1')
    try:
        if controller.secondary.handle:controller.secondary.close()
    finally:os._exit(0)

signal.signal(signal.SIGTERM,shutdown);signal.signal(signal.SIGINT,shutdown)
threading.Thread(target=initialize,daemon=True).start()
while True:
    connection,_=server.accept();threading.Thread(target=handle,args=(connection,),daemon=True).start()
