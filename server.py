import socket, threading, pickle, time
from poker import make_deck, best

PORT = 5555

players=[]
clients=[]
lock=threading.Lock()

state={
    "players":[],
    "table":[],
    "pot":0,
    "turn_index":0,
    "round_stage":"waiting",
    "game_started":False,
    "winner":None
}

deck=[]

def broadcast():
    for c in clients:
        try: c.sendall(pickle.dumps(state))
        except: pass

def active():
    return [p for p in players if p["active"]]

def alive():
    return [p for p in players if p["chips"]>0]

def reset_round():
    global deck
    deck=make_deck()
    state["table"]=[]
    state["pot"]=0
    state["round_stage"]="preflop"
    state["winner"]=None
    state["turn_index"]=0
    for p in players:
        if p["chips"]>0:
            p["hand"]=[deck.pop(),deck.pop()]
            p["active"]=True
            p["current_bet"]=0
        else:
            p["active"]=False
    broadcast()

def next_turn():
    n=len(players)
    while True:
        state["turn_index"]=(state["turn_index"]+1)%n
        if players[state["turn_index"]]["active"]: break

def bets_equal():
    b=[p["current_bet"] for p in active()]
    return len(set(b))==1

def showdown():
    best_r=None
    wins=[]
    for p in active():
        r=best(p["hand"]+state["table"])
        if best_r is None or r>best_r:
            best_r=r
            wins=[p]
        elif r==best_r:
            wins.append(p)
    share=state["pot"]//len(wins)
    for w in wins:
        w["chips"]+=share
    state["winner"]=", ".join(w["name"] for w in wins)
    state["round_stage"]="showdown"
    broadcast()
    time.sleep(3)
    if len(alive())>1:
        reset_round()
    else:
        state["game_started"]=False
        broadcast()

def handle(conn):
    name=pickle.loads(conn.recv(4096))
    p={"name":name,"chips":500,"hand":[],"current_bet":0,"active":False}
    with lock:
        players.append(p)
        clients.append(conn)
        state["players"]=players
        if len(alive())>=2 and not state["game_started"]:
            state["game_started"]=True
            reset_round()
        broadcast()

    while True:
        try:
            msg=pickle.loads(conn.recv(4096))
            if not p["active"]: continue
            act=msg["action"]
            if act=="fold":
                p["active"]=False
            else:
                need=max(x["current_bet"] for x in players)-p["current_bet"]
                if act=="call":
                    pay=min(need,p["chips"])
                elif act=="raise":
                    pay=min(need+msg["amount"],p["chips"])
                else:
                    pay=p["chips"]
                p["chips"]-=pay
                p["current_bet"]+=pay
                state["pot"]+=pay
            if len(active())==1:
                active()[0]["chips"]+=state["pot"]
                showdown()
                continue
            if bets_equal():
                for x in players: x["current_bet"]=0
                if state["round_stage"]=="preflop":
                    state["table"]+=[deck.pop(),deck.pop(),deck.pop()]
                    state["round_stage"]="flop"
                elif state["round_stage"]=="flop":
                    state["table"].append(deck.pop())
                    state["round_stage"]="turn"
                elif state["round_stage"]=="turn":
                    state["table"].append(deck.pop())
                    state["round_stage"]="river"
                elif state["round_stage"]=="river":
                    showdown()
                    continue
            next_turn()
            broadcast()
        except:
            break
    conn.close()

s=socket.socket()
s.bind(("",PORT))
s.listen()

while True:
    c,_=s.accept()
    threading.Thread(target=handle,args=(c,),daemon=True).start()
