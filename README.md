# Poker

Texas Hold'em por red para jugar en la terminal. Servidor y cliente en el mismo repo.

## Cómo jugar

1. Uno arranca el servidor (escucha en el puerto 5555):

   ```bash
   python server.py
   ```

2. Cada jugador abre un cliente y escribe la IP del servidor y su nombre:

   ```bash
   python client.py
   ```

La partida empieza cuando hay al menos 2 jugadores.

## Archivos

- `server.py`: servidor (reparte, gestiona apuestas y decide el ganador).
- `client.py`: cliente de terminal.
- `shared.py`: utilidades de cartas antiguas; ahora mismo no lo usa nadie.

> Antes estaba dividido en dos repos: `poker-server` y `poker-client`.
