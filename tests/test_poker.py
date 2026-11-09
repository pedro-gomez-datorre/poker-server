import random
import pytest
import poker
from poker import Table, best

def table(*chips):
    t=Table()
    for i,c in enumerate(chips):
        t.add_player(i,"P%d"%i)
        t.players[i]["chips"]=c
    return t

def rig(monkeypatch,hands,board):
    seq=[c for h in hands for c in h]+board
    deck=list(reversed(seq))
    rest=[c for c in poker.make_deck() if c not in seq]
    monkeypatch.setattr(poker,"make_deck",lambda:rest+deck)

def total(t):
    return sum(p["chips"]+p["total_bet"] for p in t.players)

def do(t,*actions):
    for a in actions:
        p=t.players[t.turn]
        err=t.act(p["id"],*a) if isinstance(a,tuple) else t.act(p["id"],a)
        assert err is None,(a,err)

@pytest.mark.parametrize("cards,rank",[
    (["A♠","K♠","Q♠","J♠","10♠","2♥","3♦"],9),
    (["5♥","4♥","3♥","2♥","A♥","K♦","K♣"],8),
    (["9♠","9♥","9♦","9♣","2♥","3♦","4♣"],7),
    (["9♠","9♥","9♦","2♣","2♥","3♦","4♣"],6),
    (["2♠","7♠","9♠","J♠","K♠","3♦","4♣"],5),
    (["A♠","2♥","3♦","4♣","5♠","9♦","J♣"],4),
    (["9♠","9♥","9♦","2♣","5♥","3♦","K♣"],3),
    (["9♠","9♥","2♦","2♣","5♥","3♦","K♣"],2),
    (["9♠","9♥","2♦","7♣","5♥","3♦","K♣"],1),
    (["A♠","9♥","2♦","7♣","5♥","3♦","K♣"],0),
])
def test_hand_ranks(cards,rank):
    assert best(cards)[0]==rank

def test_wheel_loses_to_six_high_straight():
    assert best(["A♠","2♥","3♦","4♣","5♠","9♦","J♣"])<best(["6♠","2♥","3♦","4♣","5♠","9♦","J♣"])

def test_blinds_and_first_turn():
    t=table(500,500,500)
    t.start_hand()
    assert t.button==0
    assert [p["current_bet"] for p in t.players]==[0,5,10]
    assert t.turn==0
    t.start_hand()
    assert t.button==1 and t.turn==1

def test_heads_up_button_is_small_blind():
    t=table(500,500)
    t.start_hand()
    assert [p["current_bet"] for p in t.players]==[5,10]
    assert t.turn==0

def test_rejects_invalid_actions():
    t=table(500,500,500)
    t.start_hand()
    assert t.act(1,"call")=="No es tu turno"
    assert t.act(0,"raise",-1000) is not None
    assert t.act(0,"raise",15) is not None
    assert t.act(0,"raise",501) is not None
    assert t.act(0,"raise","50") is not None
    assert t.act(0,"check") is not None
    assert t.act(0,"bailar") is not None
    assert [p["chips"] for p in t.players]==[500,495,490]

def test_round_does_not_close_before_big_blind_speaks():
    t=table(500,500,500)
    t.start_hand()
    do(t,"call","call")
    assert t.phase=="preflop" and t.turn==2
    do(t,"check")
    assert t.phase=="flop" and len(t.community_cards)==3

def test_raise_reopens_action():
    t=table(500,500,500)
    t.start_hand()
    do(t,"call","call",("raise",40))
    assert t.phase=="preflop" and t.turn==0
    do(t,"call","call")
    assert t.phase=="flop"

def test_pot_paid_once_when_everyone_folds():
    t=table(500,500,500)
    t.start_hand()
    do(t,("raise",30),"fold","fold")
    assert t.phase=="hand_over"
    assert [p["chips"] for p in t.players]==[515,495,490]
    assert t.results==[{"winners":["P0"],"amount":45,"hand":None}]

def test_showdown_best_hand_wins(monkeypatch):
    rig(monkeypatch,[["A♠","A♥"],["K♠","K♥"]],["2♦","7♣","9♥","J♦","3♠"])
    t=table(500,500)
    t.start_hand()
    do(t,"call","check","check","check","check","check","check","check")
    assert t.phase=="showdown"
    assert [p["chips"] for p in t.players]==[510,490]
    assert t.results[0]["hand"]=="Pareja"

def test_split_pot_with_odd_chip(monkeypatch):
    rig(monkeypatch,[["2♠","3♥"],["4♠","5♦"],["2♦","3♣"]],["A♠","A♥","K♦","K♣","Q♥"])
    t=table(500,500,500)
    t.start_hand()
    do(t,"call","fold","check")
    do(t,"check","check","check","check","check","check")
    assert t.phase=="showdown"
    assert [p["chips"] for p in t.players]==[502,495,503]
    assert t.results==[{"winners":["P2","P0"],"amount":25,"hand":"Doble pareja"}]

def test_side_pot(monkeypatch):
    rig(monkeypatch,[["A♠","A♥"],["K♠","K♥"],["Q♠","Q♥"]],["2♦","7♣","9♥","J♦","3♠"])
    t=table(500,100,500)
    t.start_hand()
    do(t,("raise",300),"allin","call")
    assert t.players[1]["allin"]
    do(t,("raise",200),"call")
    assert t.phase=="showdown"
    assert [p["chips"] for p in t.players]==[1100,0,0]

def test_side_pot_short_stack_wins(monkeypatch):
    rig(monkeypatch,[["K♠","K♥"],["A♠","A♥"],["Q♠","Q♥"]],["2♦","7♣","9♥","J♦","3♠"])
    t=table(500,100,500)
    t.start_hand()
    do(t,("raise",300),"allin","call")
    do(t,("raise",200),"call")
    assert t.phase=="showdown"
    assert [p["chips"] for p in t.players]==[800,300,0]
    assert t.results[0]=={"winners":["P1"],"amount":300,"hand":"Pareja"}
    assert t.results[1]["winners"]==["P0"] and t.results[1]["amount"]==800

def test_short_allin_does_not_block_and_runs_out():
    t=table(500,30,500)
    t.start_hand()
    do(t,("raise",100),"allin","call")
    assert t.phase=="flop"
    do(t,"check","allin","call")
    assert t.phase=="showdown" and len(t.community_cards)==5
    assert total(t)==1030

def test_both_allin_from_blinds_runs_out():
    t=table(5,8)
    t.start_hand()
    assert t.phase=="showdown" and len(t.community_cards)==5
    assert total(t)==13

def test_uncalled_bet_returned():
    t=table(500,500)
    t.start_hand()
    do(t,("raise",300),"fold")
    assert [p["chips"] for p in t.players]==[510,490]

def test_leave_on_turn_and_off_turn():
    t=table(500,500,500)
    t.start_hand()
    t.leave(2)
    assert not t.players[2]["in_round"] and t.turn==0
    do(t,"call")
    t.leave(0)
    assert t.phase=="hand_over"
    assert t.players[1]["chips"]==500-5+5+10+10
    assert t.start_hand() is False

def test_game_over_when_one_player_has_chips():
    t=table(500,0,0)
    assert t.start_hand() is False
    assert t.phase=="waiting"

def random_action(t,rng):
    a=t.legal_actions()
    opts=["fold","allin"]
    opts.append("check" if a["can_check"] else "call")
    if a["can_raise"]: opts+=["raise","raise"]
    act=rng.choice(opts)
    if act=="raise": return act,rng.randint(a["min_raise_to"],a["max_raise_to"])
    return act,0

def test_random_games_keep_chips_and_never_hang():
    rng=random.Random(1)
    for game in range(200):
        n=rng.randint(2,6)
        t=table(*[rng.choice([20,100,500]) for _ in range(n)])
        start=total(t)
        hands=0
        while t.start_hand() and hands<300:
            hands+=1
            steps=0
            while t.turn is not None:
                steps+=1
                assert steps<500
                p=t.players[t.turn]
                act,amt=random_action(t,rng)
                assert t.act(p["id"],act,amt) is None
                assert total(t)==start
            assert t.phase in ("hand_over","showdown")
            assert sum(p["chips"] for p in t.players)==start
            assert all(p["chips"]>=0 for p in t.players)
