from shared import make_deck, draw_card, hand_rank
import socket
import threading
import pickle
import random
import time

# SERVER SETUP
HOST = '0.0.0.0'
PORT = 5555

clients = []
players_names = []

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen()

# GAME STATE
game_state = {
    "players": [],
    "deck": [],
    "table": [],
    "pot": 0,
    "current_bet": 0,
    "turn_index": 0,
    "round_stage": "preflop",  # preflop, flop, turn, river, showdown
    "game_started": False
}

lock = threading.Lock()

# BROADCAST GAME STATE
def broadcast_state():
    for c in clients[:]:
        try:
            c.sendall(pickle.dumps(game_state))
        except:
            clients.remove(c)
            c.close()

# CALCULATE WINNER AT SHOWDOWN
def calculate_winner():
    active_players = [p for p in game_state["players"] if p["active"]]
    if not active_players:
        return None
    best_rank = None
    winner = None
    for p in active_players:
        rank = hand_rank(p["hand"] + game_state["table"])
        if best_rank is None or rank > best_rank:
            best_rank = rank
            winner = p
    return winner

# END ROUND AND PAY POT
def end_round():
    winner = calculate_winner()
    if winner:
        winner["chips"] += game_state["pot"]
        print(f"Winner: {winner['name']} wins {game_state['pot']} chips")
    game_state["pot"] = 0
    # Reset hands for next round
    for p in game_state["players"]:
        p["hand"] = []
        p["active"] = True
        p["current_bet"] = 0
    game_state["table"] = []
    game_state["current_bet"] = 0
    game_state["round_stage"] = "preflop"
    game_state["turn_index"] = 0
    broadcast_state()

# PROCESS PLAYER ACTION
def process_action(action):
    global game_state
    with lock:
        player_name = action["player"]
        act = action["action"]
        amt = action.get("amount", 0)

        player = next((p for p in game_state["players"] if p["name"] == player_name), None)
        if not player or not player["active"]:
            return

        if act == "fold":
            player["active"] = False
        elif act == "call":
            diff = game_state["current_bet"] - player.get("current_bet", 0)
            diff = min(diff, player["chips"])
            player["chips"] -= diff
            player["current_bet"] = game_state["current_bet"]
            game_state["pot"] += diff
        elif act == "raise":
            game_state["current_bet"] += amt
            diff = game_state["current_bet"] - player.get("current_bet", 0)
            diff = min(diff, player["chips"])
            player["chips"] -= diff
            player["current_bet"] = game_state["current_bet"]
            game_state["pot"] += diff
        elif act == "allin":
            allin_amt = player["chips"]
            player["chips"] = 0
            player["current_bet"] += allin_amt
            game_state["current_bet"] = max(game_state["current_bet"], player["current_bet"])
            game_state["pot"] += allin_amt

        # Move to next player
        alive_players = [p for p in game_state["players"] if p["active"] and p["chips"] > 0]
        if len(alive_players) <= 1:
            game_state["turn_index"] = -1
            end_round()
        else:
            while True:
                game_state["turn_index"] = (game_state["turn_index"] + 1) % len(game_state["players"])
                next_player = game_state["players"][game_state["turn_index"]]
                if next_player["active"] and next_player["chips"] > 0:
                    break

# ADVANCE ROUND (DEAL TABLE CARDS)
def advance_round():
    with lock:
        if game_state["round_stage"] == "preflop":
            game_state["table"] = draw_card(game_state["deck"], 3)  # flop
            game_state["round_stage"] = "flop"
        elif game_state["round_stage"] == "flop":
            game_state["table"] += draw_card(game_state["deck"], 1)  # turn
            game_state["round_stage"] = "turn"
        elif game_state["round_stage"] == "turn":
            game_state["table"] += draw_card(game_state["deck"], 1)  # river
            game_state["round_stage"] = "river"
        elif game_state["round_stage"] == "river":
            game_state["round_stage"] = "showdown"
            end_round()
        broadcast_state()

# HANDLE CLIENT
def handle_client(conn, addr):
    print(f"New connection from {addr}")
    try:
        name = pickle.loads(conn.recv(1024))
    except:
        conn.close()
        return

    with lock:
        clients.append(conn)
        players_names.append(name)
        game_state["players"].append({
            "name": name,
            "chips": 1000,
            "hand": [],
            "active": True,
            "current_bet": 0
        })

    broadcast_state()

    while True:
        try:
            msg = conn.recv(4096)
            if not msg:
                break
            action = pickle.loads(msg)
            process_action(action)
            broadcast_state()
            if all(p["current_bet"] == game_state["current_bet"] or not p["active"] for p in game_state["players"]):
                for p in game_state["players"]:
                    p["current_bet"] = 0
                advance_round()
        except:
            with lock:
                if name in players_names:
                    idx = players_names.index(name)
                    del players_names[idx]
                    del game_state["players"][idx]
                if conn in clients:
                    clients.remove(conn)
            conn.close()
            broadcast_state()
            break

# START GAME
def start_game():
    with lock:
        game_state["deck"] = make_deck()
        random.shuffle(game_state["deck"])
        game_state["table"] = []
        game_state["pot"] = 0
        game_state["current_bet"] = 0
        game_state["turn_index"] = 0
        game_state["round_stage"] = "preflop"
        game_state["game_started"] = True

        for player in game_state["players"]:
            player["hand"] = draw_card(game_state["deck"], 2)
            player["active"] = True
            player["current_bet"] = 0

    broadcast_state()
    print("Game started with players:", [p["name"] for p in game_state["players"]])

# SERVER LOOP
def start_server():
    print(f"Server running on {HOST}:{PORT}")
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

# MAIN LOOP
if __name__ == "__main__":
    threading.Thread(target=start_server, daemon=True).start()
    while True:
        if len(game_state["players"]) >= 2 and not game_state["game_started"]:
            start_game()
        time.sleep(1)
