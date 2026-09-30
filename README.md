# Styra Neo

Minimal starter for exploring direct control of a Square Off Neo chessboard.

## What is included

- BLE board wrapper stub
- Protocol helpers for board command framing
- Coordinate helpers for board-square mapping
- Simple move planner for normal moves and common chess specials

## Next step

Connect the BLE wrapper to the board-specific service/characteristics and replace the planner's generic actions with the exact motor sequence once the protocol is confirmed.