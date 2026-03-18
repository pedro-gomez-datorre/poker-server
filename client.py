import socket, pickle, threading, time, os

PORT = 5555

server_ip = input("Enter server IP: ")
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    client.connect((server_ip, PORT))
except:
    print("Connection failed")
    exit()

name = input("Enter your name: ")
client.sendall(pickle.dumps(name))

state = {}
my_index = None
waiting_input = False

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def recv_loop():
    global state, my_index, waiting_input
    while True:
        try:
            data = client.recv(8192)
            if not data:
                break
            state = pickle.loads(data)
            my_index = None
            for i,p in enumerate(state.get("players",[])):
                if p["name"] == name:
                    my_index = i
                    break
            waiting_input = False
            draw()
        except:
            break
    client.close()

def draw():
    global waiting_input
    clear()

    if not state.get("game_started"):
        print("Waiting for players...")
        return

    print("=== TEXAS HOLD'EM ===")
    print("Pot:", state["pot"])
    print("Stage:", state["round_stage"])
    print("Table:", " ".join(state["table"]) if state["table"] else "Empty")
    print()

    for i,p in enumerate(state["players"]):
        t = "-->" if i == state["turn_index"] else "  "
        m = "(You)" if i == my_index else ""
        s = "Active" if p["active"] else "Out"
        print(f"{t} {p['name']} {m} | Chips {p['chips']} | {s} | Bet {p['current_bet']}")

    if my_index is not None:
        hand = state["players"][my_index].get("hand",[])
        if hand:
            print("\nYour hand:", " ".join(hand))

    if state["round_stage"] == "showdown":
        print("\nWinner:", state["winner"])
        return

    if my_index == state["turn_index"] and not waiting_input:
        waiting_input = True
        threading.Thread(target=action, daemon=True).start()

def action():
    global waiting_input
    while True:
        a = input("\nAction (fold/call/raise/allin): ").lower()
        if a not in ["fold","call","raise","allin"]:
            continue
        amt = 0
        if a == "raise":
            try:
                amt = int(input("Raise amount: "))
            except:
                amt = 0
        try:
            client.sendall(pickle.dumps({
                "player": name,
                "action": a,
                "amount": amt
            }))
        except:
            pass
        waiting_input = False
        break

threading.Thread(target=recv_loop, daemon=True).start()

while True:
    time.sleep(1)

