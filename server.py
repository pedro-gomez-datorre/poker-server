import socket
import threading
import pickle
import random
import struct
import time

HOST = "0.0.0.0"
PORT = 5555

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen()
print(f"[SERVER] Listening on {HOST}:{PORT}")

clients = []
players = []
state_lock = threading.Lock()

ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
suits = ["♠", "♥", "♦", "♣"]
rank_values = {r: i for i, r in enumerate(ranks, 2)}

game_state = {
    "round": "waiting",
    "table": [],
    "pot": 0,
    "players": [],
    "message": "Waiting for players...",
}

# ----------------------------
# Helper functions
# ----------------------------
def send_full(conn, obj):
    data = pickle.dumps(obj)
    conn.sendall(struct.pack(">I", len(data)) + data)

def recvall(conn, n):
    data = b""
    while len(data) < n:
        packet = conn.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

def recv_full(conn):
    raw_len = recvall(conn, 4)
    if not raw_len:
        return None
    msg_len = struct.unpack(">I", raw_len)[0]
    return pickle.loads(recvall(conn, msg_len))

def broadcast_state():
    with state_lock:
        for c in clients.copy():
            try:
                send_full(c, game_state)
            except Exception:
                clients.remove(c)

def make_deck():
    return [r + s for r in ranks for s in suits]

# ----------------------------
# Game logic
# ----------------------------
def start_hand():
    with state_lock:
        active = [p for p in players if not p.get("disconnected")]
        if len(active) < 2:
            game_state["round"] = "waiting"
            game_state["message"] = "Waiting for players..."
            broadcast_state()
            print("[SERVER] Not enough players yet.")
            return

        print("[SERVER] Starting new hand!")
        deck = make_deck()
        random.shuffle(deck)

        # Deal 2 cards per player
        for p in active:
            p["hand"] = [deck.pop(), deck.pop()]
            p["folded"] = False

        # Deal 5 table cards
        game_state["table"] = [deck.pop() for _ in range(5)]
        game_state["round"] = "showdown"
        game_state["pot"] = 0
        game_state["players"] = players.copy()

        # Determine winner
        best_val = -1
        winner = None
        for p in active:
            vals = [rank_values[c[:-1]] for c in p["hand"]]
            top = max(vals)
            if top > best_val:
                best_val = top
                winner = p

        if winner:
            winner["chips"] += 100
            game_state["message"] = f"{winner['name']} wins the round!"
        else:
            game_state["message"] = "No winner?"

        broadcast_state()

    print("[SERVER] Round complete. Restarting soon...")
    threading.Timer(5.0, start_hand).start()

# ----------------------------
# Networking
# ----------------------------
def handle_client(conn, addr):
    print(f"[SERVER] Connection from {addr}")
    name = recv_full(conn)
    if not name:
        conn.close()
        return

    with state_lock:
        clients.append(conn)
        player = {"name": name, "chips": 1000, "hand": [], "folded": False}
        players.append(player)
        game_state["players"] = players.copy()
        print(f"[SERVER] {name} joined. Total players: {len(players)}")

        # Always check if enough players to start
        if len([p for p in players if not p.get("disconnected")]) >= 2:
            print("[SERVER] Enough players -> starting hand")
            threading.Thread(target=start_hand, daemon=True).start()

    broadcast_state()

    try:
        while True:
            data = recv_full(conn)
            if not data:
                break
    except Exception as e:
        print(f"[SERVER] Error with {addr}: {e}")

    finally:
        with state_lock:
            for p in players:
                if p["name"] == name:
                    p["disconnected"] = True
            if conn in clients:
                clients.remove(conn)
        conn.close()
        broadcast_state()
        print(f"[SERVER] {name} disconnected")

def start_server():
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    print("[SERVER] Waiting for players...")
    start_server()
