from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from .coords import BoardCoords, index_to_square, square_to_index


class PieceKind(str, Enum):
    PAWN = "pawn"
    KNIGHT = "knight"
    BISHOP = "bishop"
    ROOK = "rook"
    QUEEN = "queen"
    KING = "king"


class ActionType(str, Enum):
    PICK_UP = "pick_up"
    DROP = "drop"
    PARK_CAPTURED = "park_captured"
    PROMOTE = "promote"


@dataclass(frozen=True)
class PlannedAction:
    action: ActionType
    square: str | None = None
    x: float | None = None
    y: float | None = None
    detail: str | None = None


@dataclass(frozen=True)
class MovePlan:
    from_square: str
    to_square: str
    piece: PieceKind = PieceKind.PAWN
    capture_square: str | None = None
    promotion: PieceKind | None = None
    is_castle: bool = False
    actions: list[PlannedAction] = field(default_factory=list)


class MotorRouteError(ValueError):
    """Raised when a safe Neo motor route cannot be planned."""


@dataclass(frozen=True)
class MotorRoutePlan:
    from_square: str
    to_square: str
    route: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class CastlingPlan:
    king: MotorRoutePlan
    rook: MotorRoutePlan


@dataclass(frozen=True)
class CaptureRoutePlan:
    captured_square: str
    parking_position: tuple[float, float]
    parking_route: tuple[tuple[float, float], ...]
    capturing_route: tuple[tuple[float, float], ...]


class NeoMotorRoutePlanner:
    """Plans a direct Neo route or an obstacle-aware knight route."""

    @staticmethod
    def decode_board_state(data: bytes | str) -> frozenset[str]:
        bitmap = data.decode("ascii") if isinstance(data, bytes) else data
        bitmap = bitmap.strip()
        if len(bitmap) != 64 or any(bit not in "01" for bit in bitmap):
            raise MotorRouteError("board state must be a 64-character occupancy bitmap")
        return frozenset(
            index_to_square(index // 8, index % 8)
            for index, bit in enumerate(bitmap)
            if bit == "1"
        )

    def plan_route(
        self,
        from_square: str,
        to_square: str,
        *,
        occupied_squares: Iterable[str],
    ) -> tuple[tuple[float, float], ...]:
        start = square_to_index(from_square)
        target = square_to_index(to_square)
        if start == target:
            raise MotorRouteError("start and destination squares must differ")

        occupied = {square_to_index(square) for square in occupied_squares}
        if start not in occupied:
            raise MotorRouteError(f"source square {from_square} is not occupied")
        if target in occupied:
            raise MotorRouteError(
                f"destination {to_square} is occupied; capture routes are not supported"
            )

        file_delta = target[0] - start[0]
        rank_delta = target[1] - start[1]
        if (abs(file_delta), abs(rank_delta)) in {(1, 2), (2, 1)}:
            return self._plan_knight_route(start, target, occupied)

        if not (
            file_delta == 0
            or rank_delta == 0
            or abs(file_delta) == abs(rank_delta)
        ):
            raise MotorRouteError(
                f"{from_square}->{to_square} is not a straight or knight move"
            )

        steps = max(abs(file_delta), abs(rank_delta))
        file_step = (file_delta > 0) - (file_delta < 0)
        rank_step = (rank_delta > 0) - (rank_delta < 0)
        for step in range(1, steps):
            square = (start[0] + file_step * step, start[1] + rank_step * step)
            if square in occupied:
                raise MotorRouteError(
                    f"route is blocked at {chr(square[0] + 97)}{square[1] + 1}"
                )

        return (start, target)

    def plan_castle(
        self,
        king_from: str,
        king_to: str,
        *,
        occupied_squares: Iterable[str],
    ) -> CastlingPlan:
        king_start = square_to_index(king_from)
        king_target = square_to_index(king_to)
        home_rank = king_start[1]
        if king_start[0] != 4 or home_rank not in {0, 7}:
            raise MotorRouteError("castling king must start on e1 or e8")
        if king_target[1] != home_rank or king_target[0] not in {2, 6}:
            raise MotorRouteError("castling king target must be c1, g1, c8, or g8")

        kingside = king_target[0] == 6
        rook_from = index_to_square(7 if kingside else 0, home_rank)
        rook_to = index_to_square(5 if kingside else 3, home_rank)
        occupied = frozenset(occupied_squares)

        king_route = self.plan_route(
            king_from,
            king_to,
            occupied_squares=occupied,
        )
        self.plan_route(
            rook_from,
            rook_to,
            occupied_squares=occupied,
        )

        file_direction = -1 if kingside else 1
        rank_direction = 1 if home_rank == 0 else -1
        rook_start_file = 7 if kingside else 0
        rook_target_file = 5 if kingside else 3
        corners = tuple(
            (
                rook_start_file + file_direction * (step + 0.5),
                home_rank + rank_direction * 0.5,
            )
            for step in range(abs(rook_target_file - rook_start_file))
        )
        rook_route = (
            square_to_index(rook_from),
            *corners,
            square_to_index(rook_to),
        )

        return CastlingPlan(
            king=MotorRoutePlan(king_from, king_to, king_route),
            rook=MotorRoutePlan(rook_from, rook_to, rook_route),
        )

    def plan_capture(
        self,
        from_square: str,
        captured_square: str,
        *,
        occupied_squares: Iterable[str],
        parking_position: tuple[float, float] = (8.0, 3.0),
    ) -> CaptureRoutePlan:
        start = square_to_index(from_square)
        captured = square_to_index(captured_square)
        occupied = {square_to_index(square) for square in occupied_squares}
        if start not in occupied:
            raise MotorRouteError(f"source square {from_square} is not occupied")
        if captured not in occupied:
            raise MotorRouteError(
                f"capture square {captured_square} is not occupied"
            )
        if start == captured:
            raise MotorRouteError("capturing piece and captured piece must differ")

        parking_file, parking_rank = parking_position
        if not 7.5 < parking_file <= 8.5:
            raise MotorRouteError("capture parking must be just right of the h-file")
        if not 0 <= parking_rank <= 7 or not parking_rank.is_integer():
            raise MotorRouteError("capture parking rank must align with a board rank")

        entry = (7, int(parking_rank))
        remaining_occupied = occupied - {captured}
        if entry in remaining_occupied:
            raise MotorRouteError("capture parking entry square is occupied")

        parents: dict[tuple[int, int], tuple[int, int] | None] = {captured: None}
        frontier = deque([captured])
        while frontier and entry not in parents:
            current = frontier.popleft()
            for file_step, rank_step in ((1, 0), (0, -1), (0, 1), (-1, 0)):
                candidate = (current[0] + file_step, current[1] + rank_step)
                if not (0 <= candidate[0] < 8 and 0 <= candidate[1] < 8):
                    continue
                if candidate in remaining_occupied or candidate in parents:
                    continue
                parents[candidate] = current
                frontier.append(candidate)

        if entry not in parents:
            raise MotorRouteError("no clear route to the capture parking entry")

        board_path = [entry]
        while board_path[-1] != captured:
            parent = parents[board_path[-1]]
            if parent is None:
                raise MotorRouteError("could not reconstruct capture parking route")
            board_path.append(parent)
        board_path.reverse()
        parking_route = tuple(board_path) + (parking_position,)
        remaining_occupied_squares = {
            index_to_square(file_index, rank_index)
            for file_index, rank_index in remaining_occupied
        }
        capturing_route = self.plan_route(
            from_square,
            captured_square,
            occupied_squares=remaining_occupied_squares,
        )
        return CaptureRoutePlan(
            captured_square=captured_square,
            parking_position=parking_position,
            parking_route=parking_route,
            capturing_route=capturing_route,
        )

    def plan_move(
        self,
        move: MovePlan,
        *,
        occupied_squares: Iterable[str],
    ) -> tuple[tuple[float, float], ...]:
        if move.is_castle:
            raise MotorRouteError("use plan_castle to plan both castling pieces")
        if move.promotion is not None:
            raise MotorRouteError("promotion needs a physical piece replacement")
        if move.capture_square is not None:
            raise MotorRouteError("capture moves need a verified piece-parking route")
        return self.plan_route(
            move.from_square,
            move.to_square,
            occupied_squares=occupied_squares,
        )

    def encode_route(self, route: tuple[tuple[float, float], ...]) -> str:
        if len(route) < 2:
            raise MotorRouteError("a motor route needs a start and destination")

        def format_coordinate(value: float) -> str:
            return str(int(value)) if value.is_integer() else str(value)

        waypoints = [
            f"{format_coordinate(file_index)},{format_coordinate(rank_index)}"
            for file_index, rank_index in route[:-1]
        ]
        previous_file, previous_rank = route[-2]
        target_file, target_rank = route[-1]
        if target_file != previous_file:
            target_file += 0.08 if target_file > previous_file else -0.08
            target_file_text = f"{target_file:.2f}"
        else:
            target_file_text = format_coordinate(target_file)
        if target_rank != previous_rank:
            target_rank += 0.08 if target_rank > previous_rank else -0.08
            target_rank_text = f"{target_rank:.2f}"
        else:
            target_rank_text = format_coordinate(target_rank)
        waypoints.append(f"{target_file_text},{target_rank_text}")
        return ":".join(waypoints) + "|"

    def _plan_knight_route(
        self,
        start: tuple[int, int],
        target: tuple[int, int],
        occupied: set[tuple[int, int]],
    ) -> tuple[tuple[float, float], ...]:
        start_file, start_rank = start
        target_file, target_rank = target
        middle_file = (start_file + target_file) / 2
        middle_rank = (start_rank + target_rank) / 2

        if abs(target_rank - start_rank) == 2:
            candidates = (
                (
                    ((target_file, start_rank), (target_file, middle_rank)),
                    (target_file, start_rank),
                ),
                (
                    ((start_file, target_rank), (start_file, middle_rank)),
                    (start_file, target_rank),
                ),
                (((target_file, middle_rank),), (target_file, middle_rank)),
            )
            direction = 1 if target_rank > start_rank else -1
            corners = (
                (middle_file, start_rank + 0.5 * direction),
                (middle_file, start_rank + 1.5 * direction),
            )
        else:
            candidates = (
                (
                    ((target_file, start_rank), (middle_file, start_rank)),
                    (target_file, start_rank),
                ),
                (
                    ((start_file, target_rank), (start_file, middle_rank)),
                    (start_file, target_rank),
                ),
                (((middle_file, target_rank),), (middle_file, target_rank)),
            )
            direction = 1 if target_file > start_file else -1
            corners = (
                (start_file + 0.5 * direction, middle_rank),
                (start_file + 1.5 * direction, middle_rank),
            )

        for checks, waypoint in candidates:
            if not any(square in occupied for square in checks):
                return (start, waypoint, target)

        return (start, *corners, target)


class MovePlanner:
    """Turns chess moves into a physical action plan.

    This first version is intentionally generic. The exact motor path can be
    replaced later once the board protocol and travel geometry are confirmed.
    """

    def __init__(self, coords: BoardCoords | None = None) -> None:
        self.coords = coords or BoardCoords()

    def plan_move(
        self,
        from_square: str,
        to_square: str,
        *,
        piece: PieceKind = PieceKind.PAWN,
        capture_square: str | None = None,
        promotion: PieceKind | None = None,
        is_castle: bool = False,
    ) -> MovePlan:
        actions: list[PlannedAction] = []

        from_x, from_y = self.coords.square_to_xy(from_square)
        to_x, to_y = self.coords.square_to_xy(to_square)
        actions.append(PlannedAction(ActionType.PICK_UP, from_square, from_x, from_y))

        if capture_square is not None:
            cap_x, cap_y = self.coords.square_to_xy(capture_square)
            actions.append(
                PlannedAction(
                    ActionType.PARK_CAPTURED,
                    capture_square,
                    cap_x,
                    cap_y,
                    detail="move captured piece off board first",
                )
            )

        actions.append(PlannedAction(ActionType.DROP, to_square, to_x, to_y))

        if promotion is not None:
            actions.append(
                PlannedAction(
                    ActionType.PROMOTE,
                    to_square,
                    to_x,
                    to_y,
                    detail=promotion.value,
                )
            )

        return MovePlan(
            from_square=from_square,
            to_square=to_square,
            piece=piece,
            capture_square=capture_square,
            promotion=promotion,
            is_castle=is_castle,
            actions=actions,
        )
