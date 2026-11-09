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

Opcionalmente, el servidor acepta el puerto y los segundos de pausa entre manos:

```bash
python server.py 5555 3
```

## Tests

```bash
python -m pytest
```

## Archivos

- `poker.py`: las reglas (clase `Table`): ciegas, turnos, apuestas, botes secundarios y ganador.
- `server.py`: servidor de red; usa `Table` y habla JSON, un mensaje por línea.
- `client.py`: cliente de terminal.
- `tests/`: tests de las reglas y del servidor con bots.

> Antes estaba dividido en dos repos: `poker-server` y `poker-client`.
