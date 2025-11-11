import random
from collections import Counter

ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King", "Ace"]
suits = ["♠", "♥", "♦", "♣"]

def make_deck():
    return [rank + suit for rank in ranks for suit in suits]

def draw_card(deck, n):
    hand = deck[:n]
    del deck[:n]

def hand_rank(cards):
    ranks = [c[:-1] for c in cards]
    suits = [c[-1] for c in cards]
    values = []
    for r in ranks:
        if r == "Ace":
          values.append(14)
        elif r == "King":
          values.append(13)
        elif r == "Queen":
          values.append(12)
        elif r == "Jack":
          values.append(11)
        else:
          values.append(int(r))
    values.sort()
    counts = Counter(values)
    flush = len(set(suits)) == 1
    unique_vals = sorted(set(values))
    straight = any(unique_vals[i:i+5] == list(range(unique_vals[i], unique_vals[i]+5)) for i in range(len(unique_vals)-4))
    if set([14, 2, 3, 4, 5]).issubset(values):
      straight = True
    if flush and set([10, 11, 12, 13, 14]).issubset(values):
      return ("Royal Flush", 10)
    elif flush and straight:
      return ("Straight Flush", 9)
    elif 4 in counts.values():
      return ("Poker", 8)
    elif 3 in counts.values() and 2 in counts.values():
      return ("Full House", 7)
    elif flush:
      return ("Flush", 6)
    elif straight:
      return ("Straight", 5)
    elif 3 in counts.values():
      return ("Trio", 4)
    elif list(counts.values()).count(2) == 2:
      return ("Double Pair", 3)
    elif 2 in counts.values():
      return ("Pair", 2)
    else:
      return ("High Card", 1)