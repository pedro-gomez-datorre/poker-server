import socket, threading, json, sys
from poker import Table

PORT=5555
DELAY=3

table=Table()
clients={}
lock=threading.RLock()
next_id=0
pending=False

def send(conn,msg):
    try: conn.sendall((json.dumps(msg)+"\n").encode())
    except OSError: pass

def view(pid):
    t=table
    show=t.phase=="showdown"
    turn=t.players[t.turn]["id"] if t.turn is not None else None
    players=[]
    for p in t.players:
        if p["gone"]: continue
        if p["id"]==pid or (show and p["in_round"]): hand=p["hand"]
        else: hand=["??"]*len(p["hand"])
        players.append({
            "id":p["id"],
            "name":p["name"],
            "chips":p["chips"],
            "bet":p["current_bet"],
            "in_round":p["in_round"],
            "allin":p["allin"],
            "hand":hand
        })
    return {
        "type":"state",
        "you":pid,
        "phase":t.phase,
        "table":t.community_cards,
        "pot":sum(p["total_bet"] for p in t.players),
        "turn":turn,
        "button":t.players[t.button]["id"] if 0<=t.button<len(t.players) else None,
        "players":players,
        "actions":t.legal_actions() if turn==pid else None,
        "results":t.results
    }

def broadcast():
    for pid,conn in list(clients.items()): send(conn,view(pid))

def update():
    global pending
    broadcast()
    if table.phase in ("hand_over","showdown") and not pending:
        pending=True
        threading.Timer(DELAY,new_hand).start()

def new_hand():
    global pending
    with lock:
        pending=False
        table.start_hand()
        update()

def handle(conn):
    global next_id
    f=conn.makefile("r",encoding="utf-8")
    pid=None
    try:
        msg=json.loads(f.readline())
        name=str(msg.get("name","")).strip()[:20]
        with lock:
            if not name or any(p["name"]==name and not p["gone"] for p in table.players):
                send(conn,{"type":"error","msg":"Nombre vacío o ya en uso"})
                return
            pid=next_id
            next_id+=1
            table.add_player(pid,name)
            clients[pid]=conn
            send(conn,{"type":"welcome","id":pid})
            if table.phase=="waiting" and not pending: table.start_hand()
            update()
        for line in f:
            msg=json.loads(line)
            with lock:
                err=table.act(pid,msg.get("action"),msg.get("amount",0))
                if err: send(conn,{"type":"error","msg":err})
                else: update()
    except (OSError,ValueError,AttributeError):
        pass
    finally:
        with lock:
            if pid is not None:
                clients.pop(pid,None)
                table.leave(pid)
                update()
        conn.close()

def main():
    s=socket.socket()
    s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    s.bind(("",PORT))
    s.listen()
    print("Servidor en el puerto",PORT)
    while True:
        c,_=s.accept()
        threading.Thread(target=handle,args=(c,),daemon=True).start()

if __name__=="__main__":
    if len(sys.argv)>1: PORT=int(sys.argv[1])
    if len(sys.argv)>2: DELAY=float(sys.argv[2])
    main()
