import socket
import threading
import pickle
import random
import time

PORT = 5555

def make_deck():
    suits = ["♠", "♥", "♦", "♣"]
    ranks = ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
    deck = [r+s for s in suits for r in ranks]
    random.shuffle(deck)
    return deck

RANK_ORDER = {r:i for i,r in enumerate("23456789TJQKA", start=2)}

def cv(c):
    r=c[:-1]
    if r=="10": r="T"
    return RANK_ORDER[r]

from collections import Counter

def is_straight(v):
    u=sorted(set(v))
    if len(u)<5: return False,None
    if set([14,5,4,3,2]).issubset(v): return True,5
    for i in range(len(u)-4):
        w=u[i:i+5]
        if w==list(range(w[0],w[0]+5)): return True,w[-1]
    return False,None

def rank5(cards):
    v=sorted([cv(c) for c in cards],reverse=True)
    s=[c[-1] for c in cards]
    f=len(set(s))==1
    st,hi=is_straight(v)
    c=Counter(v)
    g=sorted(c.items(),key=lambda x:(x[1],x[0]),reverse=True)
    freq=[x[1] for x in g]
    ordered=[x[0] for x in g for _ in range(x[1])]
    if st and f:
        if hi==14: return (9,[14])
        return (8,[hi])
    if freq==[4,1]: return (7,ordered)
    if freq==[3,2]: return (6,ordered)
    if f: return (5,v)
    if st: return (4,[hi])
    if freq==[3,1,1]: return (3,ordered)
    if freq==[2,2,1]: return (2,ordered)
    if freq==[2,1,1,1]: return (1,ordered)
    return (0,v)

def best_rank(cards):
    best=None
    n=len(cards)
    for i in range(n-4):
        for j in range(i+1,n-3):
            for k in range(j+1,n-2):
                for l in range(k+1,n-1):
                    for m in range(l+1,n):
                        h=[cards[i],cards[j],cards[k],cards[l],cards[m]]
                        r=rank5(h)
                        if best is None or r>best:
                            best=r
    return best

clients=[]
players=[]
lock=threading.Lock()
game_state={
    "players":[],
    "table":[],
    "pot":0,
    "turn_index":0,
    "game_started":False,
    "round_stage":"preflop",
    "winner":None
}

def broadcast():
    data=pickle.dumps(game_state)
    for c in clients:
        try: c.sendall(data)
        except: pass

def next_player():
    n=len(players)
    while True:
        game_state["turn_index"]=(game_state["turn_index"]+1)%n
        if players[game_state["turn_index"]]["active"]:
            break

def all_bets_equal():
    b=[p["current_bet"] for p in players if p["active"]]
    return len(set(b))==1

def active_count():
    return sum(1 for p in players if p["active"])

def reset_bets():
    for p in players:
        p["current_bet"]=0

def deal_flop(deck):
    game_state["table"]+= [deck.pop(),deck.pop(),deck.pop()]

def deal_turn(deck):
    game_state["table"].append(deck.pop())

def deal_river(deck):
    game_state["table"].append(deck.pop())

def showdown():
    best=None
    win=None
    for p in players:
        if p["active"]:
            cards=p["hand"]+game_state["table"]
            r=best_rank(cards)
            p["rank"]=r
            if best is None or r>best:
                best=r
                win=p["name"]
    game_state["winner"]=win
    for p in players:
        if p["name"]==win:
            p["chips"]+=game_state["pot"]
    game_state["pot"]=0

def handle_player(conn,addr):
    name=pickle.loads(conn.recv(4096))
    with lock:
        clients.append(conn)
        players.append({
            "name":name,
            "chips":1000,
            "hand":[],
            "current_bet":0,
            "active":True
        })
        game_state["players"]=players.copy()
    broadcast()

    while True:
        try:
            data=conn.recv(4096)
            if not data: break
            action=pickle.loads(data)
            with lock:
                p=[x for x in players if x["name"]==action["player"]][0]
                if action["action"]=="fold":
                    p["active"]=False
                elif action["action"]=="call":
                    mb=max(x["current_bet"] for x in players)
                    diff=mb-p["current_bet"]
                    if diff>p["chips"]: diff=p["chips"]
                    p["chips"]-=diff
                    p["current_bet"]+=diff
                    game_state["pot"]+=diff
                elif action["action"]=="raise":
                    mb=max(x["current_bet"] for x in players)
                    amt=action["amount"]
                    total=mb-p["current_bet"]+amt
                    if total>p["chips"]: total=p["chips"]
                    p["chips"]-=total
                    p["current_bet"]+=total
                    game_state["pot"]+=total
                elif action["action"]=="allin":
                    total=p["chips"]
                    p["chips"]=0
                    p["current_bet"]+=total
                    game_state["pot"]+=total

                if active_count()==1:
                    for x in players:
                        if x["active"]:
                            x["chips"]+=game_state["pot"]
                    game_state["round_stage"]="showdown"
                    game_state["winner"]=[x["name"] for x in players if x["active"]][0]
                    game_state["pot"]=0
                    broadcast()
                    continue

                if all_bets_equal():
                    if game_state["round_stage"]=="preflop":
                        deal_flop(deck)
                        reset_bets()
                        game_state["round_stage"]="flop"
                    elif game_state["round_stage"]=="flop":
                        deal_turn(deck)
                        reset_bets()
                        game_state["round_stage"]="turn"
                    elif game_state["round_stage"]=="turn":
                        deal_river(deck)
                        reset_bets()
                        game_state["round_stage"]="river"
                    elif game_state["round_stage"]=="river":
                        game_state["round_stage"]="showdown"
                        showdown()

                next_player()
            broadcast()
        except:
            break
    conn.close()

s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.bind(("",PORT))
s.listen()

deck=None

def game_loop():
    global deck
    while True:
        if len(players)>=2 and not game_state["game_started"]:
            deck=make_deck()
            for p in players:
                p["hand"]=[deck.pop(),deck.pop()]
                p["active"]=True
                p["current_bet"]=0
            game_state["table"]=[]
            game_state["pot"]=0
            game_state["turn_index"]=0
            game_state["round_stage"]="preflop"
            game_state["winner"]=None
            game_state["game_started"]=True
            broadcast()
        time.sleep(1)

threading.Thread(target=game_loop,daemon=True).start()

while True:
    c,a=s.accept()
    threading.Thread(target=handle_player,args=(c,a),daemon=True).start()
