import random
from collections import Counter

R={r:i for i,r in enumerate("23456789TJQKA",start=2)}
HAND_NAMES=["Carta alta","Pareja","Doble pareja","Trío","Escalera","Color","Full","Póker","Escalera de color","Escalera real"]

def make_deck():
    suits=["♠","♥","♦","♣"]
    ranks=["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
    d=[r+s for s in suits for r in ranks]
    random.shuffle(d)
    return d

def cv(c):
    r=c[:-1]
    if r=="10": r="T"
    return R[r]

def straight(v):
    u=sorted(set(v))

    if len(u)<5: return False,None

    if set([14,5,4,3,2]).issubset(v): return True,5

    for i in range(len(u)-4):
        if u[i:i+5]==list(range(u[i],u[i]+5)): return True,u[i+4]
    return False,None

def rank5(cards):
    v=sorted([cv(c) for c in cards],reverse=True)
    s=[c[-1] for c in cards]
    f=len(set(s))==1
    st,hi=straight(v)
    c=Counter(v)
    g=sorted(c.items(),key=lambda x:(x[1],x[0]),reverse=True)
    freq=[x[1] for x in g]
    o=[x[0] for x in g for _ in range(x[1])]

    if st and f:
        if hi==14: return (9,[14])
        return (8,[hi])
    
    if freq==[4,1]: return (7,o)
    if freq==[3,2]: return (6,o)
    if f: return (5,v)
    if st: return (4,[hi])
    if freq==[3,1,1]: return (3,o)
    if freq==[2,2,1]: return (2,o)
    if freq==[2,1,1,1]: return (1,o)

    return (0,v)

def best(cards):
    b=None
    n=len(cards)
    for i in range(n-4):
        for j in range(i+1,n-3):
            for k in range(j+1,n-2):
                for l in range(k+1,n-1):
                    for m in range(l+1,n):
                        r=rank5([cards[i],cards[j],cards[k],cards[l],cards[m]])
                        if b is None or r>b: b=r
    return b

class Table:
    def __init__(self, small_blind=5, big_blind=10, initial_chips=500):
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.initial_chips = initial_chips
        self.players = []
        self.button = -1
        self.turn = None
        self.phase = "waiting"
        self.community_cards = []
        self.deck = []
        self.highest_bet = 0
        self.min_raise = big_blind
        self.results = []

    def add_player(self, id_,name):
        self.players.append({
            "id": id_,
            "name": name,
            "chips": self.initial_chips,
            "hand": [],
            "current_bet": 0,
            "total_bet": 0,
            "in_round": False,
            "allin": False,
            "talked": False,
            "gone": False
        })

    def _next_index(self, start, cond):
        n = len(self.players)
        for k in range(1, n + 1):
            i = (start + k) % n
            if cond(self.players[i]):
                return i
        return None

    def _can_act(self, p):
        return p["in_round"] and not p["allin"]

    def _put_chips(self, p, amount):
        pay = min(amount, p["chips"])
        p["chips"] -= pay
        p["current_bet"] += pay
        p["total_bet"] += pay
        if p["chips"] == 0:
            p["allin"] = True
        return pay

    def start_hand(self):
        with_chips = [p for p in self.players if p["chips"] > 0]
        if len(with_chips) < 2:
            self.phase = "waiting"
            return False

        self.deck = make_deck()
        self.results = []
        self.community_cards = []

        for p in self.players:
            p["hand"] = []
            p["current_bet"] = 0
            p["total_bet"] = 0
            p["allin"] = False
            p["talked"] = False
            p["in_round"] = p["chips"] > 0
            if p["in_round"]:
                p["hand"] = [self.deck.pop(), self.deck.pop()]

        in_hand = lambda p: p["in_round"]

        self.button = self._next_index(self.button, in_hand)

        if len(with_chips) == 2:
            sb = self.button
        else:
            sb = self._next_index(self.button, in_hand)
        bb = self._next_index(sb, in_hand)

        self._put_chips(self.players[sb], self.small_blind)
        self._put_chips(self.players[bb], self.big_blind)

        self.highest_bet = self.big_blind
        self.min_raise = self.big_blind
        self.phase = "preflop"

        self.turn = self._next_index(bb, self._needs_to_act)
        if self.turn is None: self._next_street()
        return True

    def legal_actions(self):
        if self.turn is None: return None
        p=self.players[self.turn]
        need=self.highest_bet-p["current_bet"]
        top=p["current_bet"]+p["chips"]
        return {
            "can_check":need==0,
            "to_call":min(need,p["chips"]),
            "can_raise":top>self.highest_bet,
            "min_raise_to":min(self.highest_bet+self.min_raise,top),
            "max_raise_to":top
        }

    def act(self, player_id, action, amount=0):
        if self.turn is None: return "No es momento de apostar"
        p=self.players[self.turn]
        if p["id"]!=player_id: return "No es tu turno"
        need=self.highest_bet-p["current_bet"]
        top=p["current_bet"]+p["chips"]

        if action=="fold":
            p["in_round"]=False
        elif action=="check":
            if need>0: return f"No puedes pasar: tienes que poner {need}"
        elif action=="call":
            if need==0: return "No hay nada que igualar: usa check"
            self._put_chips(p,need)
        elif action in ("raise","allin"):
            if action=="allin": amount=top
            if not isinstance(amount,int): return "La cantidad tiene que ser un número entero"
            if amount>top: return f"No tienes tantas fichas: como mucho {top}"
            if amount<=self.highest_bet:
                if action!="allin": return f"Para subir tienes que pasar de {self.highest_bet}"
                self._put_chips(p,p["chips"])
            else:
                r=amount-self.highest_bet
                if r<self.min_raise and amount<top: return f"La subida mínima es hasta {self.highest_bet+self.min_raise}"
                self._put_chips(p,amount-p["current_bet"])
                if r>=self.min_raise: self.min_raise=r
                self.highest_bet=amount
                for x in self.players:
                    if x is not p: x["talked"]=False
        else:
            return f"Acción desconocida: {action}"

        p["talked"]=True
        self._advance()
        return None

    def _needs_to_act(self, p):
        return self._can_act(p) and (not p["talked"] or p["current_bet"]<self.highest_bet)

    def _advance(self):
        if len([p for p in self.players if p["in_round"]])==1:
            self.turn=None
            self.phase="hand_over"
            self._finish()
            return
        nxt=self._next_index(self.turn,self._needs_to_act)
        if nxt is not None: self.turn=nxt
        else: self._next_street()

    def _next_street(self):
        while True:
            for p in self.players:
                p["current_bet"]=0
                p["talked"]=False
            self.highest_bet=0
            self.min_raise=self.big_blind

            if self.phase=="preflop":
                self.community_cards+=[self.deck.pop(),self.deck.pop(),self.deck.pop()]
                self.phase="flop"
            elif self.phase=="flop":
                self.community_cards.append(self.deck.pop())
                self.phase="turn"
            elif self.phase=="turn":
                self.community_cards.append(self.deck.pop())
                self.phase="river"
            else:
                self.phase="showdown"
                self._finish()
                return

            if sum(self._can_act(p) for p in self.players)>=2:
                self.turn=self._next_index(self.button,self._can_act)
                return

    def _finish(self):
        self.turn=None
        alive=[p for p in self.players if p["in_round"]]
        ranks={p["id"]:best(p["hand"]+self.community_cards) for p in alive} if len(alive)>1 else {}
        n=len(self.players)
        seat=lambda p:(self.players.index(p)-self.button-1)%n
        self.results=[]
        prev=0
        for lv in sorted(set(p["total_bet"] for p in self.players if p["total_bet"]>0)):
            pot=sum(min(p["total_bet"],lv)-min(p["total_bet"],prev) for p in self.players)
            prev=lv
            elig=[p for p in alive if p["total_bet"]>=lv] or alive
            if ranks:
                top=max(ranks[p["id"]] for p in elig)
                win=[p for p in elig if ranks[p["id"]]==top]
                hand=HAND_NAMES[top[0]]
            else:
                win=elig
                hand=None
            win.sort(key=seat)
            share,rest=divmod(pot,len(win))
            for i,p in enumerate(win): p["chips"]+=share+(1 if i<rest else 0)
            names=[p["name"] for p in win]
            if self.results and self.results[-1]["winners"]==names: self.results[-1]["amount"]+=pot
            else: self.results.append({"winners":names,"amount":pot,"hand":hand})
        for p in self.players:
            p["total_bet"]=0
            p["current_bet"]=0

    def leave(self, player_id):
        p=next((x for x in self.players if x["id"]==player_id),None)
        if p is None: return
        if self.turn is not None and self.players[self.turn] is p:
            self.act(player_id,"fold")
        elif self.turn is not None and p["in_round"]:
            p["in_round"]=False
            if len([x for x in self.players if x["in_round"]])==1:
                self.phase="hand_over"
                self._finish()
        p["gone"]=True
        p["chips"]=0
