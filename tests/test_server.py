import json, os, random, socket, subprocess, sys, threading, time
import pytest

ROOT=os.path.join(os.path.dirname(__file__),"..")

def free_port():
    s=socket.socket()
    s.bind(("127.0.0.1",0))
    port=s.getsockname()[1]
    s.close()
    return port

@pytest.fixture
def server():
    port=free_port()
    proc=subprocess.Popen([sys.executable,os.path.join(ROOT,"server.py"),str(port),"0.02"],stdout=subprocess.DEVNULL)
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1",port)).close()
            break
        except OSError:
            time.sleep(0.05)
    yield port
    proc.kill()
    proc.wait()

class Bot:
    def __init__(self,port,name):
        self.sock=socket.create_connection(("127.0.0.1",port))
        self.sock.settimeout(10)
        self.f=self.sock.makefile("r",encoding="utf-8")
        self.send({"name":name})
        self.name=name

    def send(self,msg):
        self.sock.sendall((json.dumps(msg)+"\n").encode())

    def recv(self):
        line=self.f.readline()
        assert line,"el servidor cerró la conexión"
        return json.loads(line)

    def close(self):
        try: self.sock.shutdown(socket.SHUT_RDWR)
        except OSError: pass
        self.f.close()
        self.sock.close()

def check_state(st):
    assert sum(p["chips"] for p in st["players"])+st["pot"]==500*len(st["players"])
    for p in st["players"]:
        if p["id"]!=st["you"] and st["phase"]!="showdown":
            assert all(c=="??" for c in p["hand"])

def play(bot,stop,seen,rng):
    last=None
    while not stop.is_set():
        try: st=bot.recv()
        except (socket.timeout,OSError,AssertionError): return
        if st["type"]!="state": continue
        check_state(st)
        if st["phase"] in ("hand_over","showdown") and last not in ("hand_over","showdown"): seen[bot.name]=seen.get(bot.name,0)+1
        last=st["phase"]
        if seen.get(bot.name,0)>=30:
            stop.set()
            return
        live=[p for p in st["players"] if p["chips"]>0]
        if st["phase"]=="waiting" and len(st["players"])==3 and len(live)==1:
            seen["fin"]=1
            stop.set()
            return
        a=st["actions"]
        if not a: continue
        opts=["fold"]+["check" if a["can_check"] else "call"]*12
        if a["can_raise"]: opts+=["raise"]*3
        act=rng.choice(opts)
        if rng.random()<0.02: act="allin"
        amt=rng.randint(a["min_raise_to"],min(a["max_raise_to"],a["min_raise_to"]+50)) if act=="raise" else 0
        bot.send({"action":act,"amount":amt})

def test_bots_play_30_hands_or_until_someone_wins(server):
    rng=random.Random(7)
    bots=[]
    for i,name in enumerate(["Ana","Luis","Eva"]):
        b=Bot(server,name)
        assert b.recv()["type"]=="welcome"
        bots.append(b)
    stop=threading.Event()
    seen={}
    errors=[]
    def run(b):
        try: play(b,stop,seen,random.Random(rng.random()))
        except AssertionError as e:
            errors.append(e)
            stop.set()
    threads=[threading.Thread(target=run,args=(b,)) for b in bots]
    for th in threads: th.start()
    stop.wait(120)
    for b in bots: b.close()
    for th in threads: th.join(10)
    assert not errors,errors
    assert stop.is_set(),"la partida se quedó colgada"
    assert "fin" in seen or max(seen.values())>=30,seen

def test_duplicate_name_rejected(server):
    a=Bot(server,"Ana")
    assert a.recv()["type"]=="welcome"
    b=Bot(server,"Ana")
    assert b.recv()["type"]=="error"
    a.close(); b.close()

def recv_until(bot,cond):
    while True:
        m=bot.recv()
        if cond(m): return m

def test_out_of_turn_and_bad_amount_rejected(server):
    a=Bot(server,"Ana"); a.recv()
    b=Bot(server,"Luis"); b.recv()
    st=recv_until(a,lambda m:m["type"]=="state" and m["phase"]=="preflop")
    mine,other=(a,b) if st["turn"]==st["you"] else (b,a)
    other.send({"action":"call"})
    assert recv_until(other,lambda m:m["type"]=="error")["msg"]=="No es tu turno"
    mine.send({"action":"raise","amount":-1000})
    assert recv_until(mine,lambda m:m["type"]=="error")
    mine.send("esto no es json valido")
    a.close(); b.close()

def test_disconnect_does_not_hang_game(server):
    bots=[Bot(server,n) for n in ["Ana","Luis","Eva"]]
    for b in bots: b.recv()
    st=recv_until(bots[2],lambda m:m["type"]=="state" and m["phase"]=="preflop" and len(m["players"])==3)
    who=[b for b in bots if b.name==[p["name"] for p in st["players"] if p["id"]==st["turn"]][0]][0]
    who.close()
    rest=[b for b in bots if b is not who]
    st=recv_until(rest[0],lambda m:m["type"]=="state" and len(m["players"])==2 and m["turn"] is not None)
    assert st["turn"] in [p["id"] for p in st["players"]]
    for b in rest: b.close()
