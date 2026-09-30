from __future__ import annotations

import unittest

from styra_neo.move_planner import (
    MotorRouteError,
    MovePlan,
    NeoMotorRoutePlanner,
    PieceKind,
)


class NeoMotorRoutePlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = NeoMotorRoutePlanner()

    def test_encodes_clear_straight_route(self) -> None:
        route = self.planner.plan_route("d2", "d4", occupied_squares={"d2"})

        self.assertEqual(self.planner.encode_route(route), "3,1:3,3.08|")

    def test_offsets_horizontal_endpoint_on_file_axis(self) -> None:
        route = self.planner.plan_route("a1", "c1", occupied_squares={"a1"})

        self.assertEqual(self.planner.encode_route(route), "0,0:2.08,0|")

    def test_offsets_endpoint_in_negative_rank_direction(self) -> None:
        route = self.planner.plan_route("d4", "d2", occupied_squares={"d4"})

        self.assertEqual(self.planner.encode_route(route), "3,3:3,0.92|")

    def test_decodes_board_occupancy_bitmap(self) -> None:
        bitmap = ["0"] * 64
        bitmap[25] = "1"

        self.assertEqual(
            self.planner.decode_board_state("".join(bitmap)), frozenset({"d2"})
        )

    def test_rejects_invalid_board_occupancy_bitmap(self) -> None:
        with self.assertRaisesRegex(MotorRouteError, "64-character occupancy bitmap"):
            self.planner.decode_board_state("101")

    def test_rejects_blocked_straight_route(self) -> None:
        with self.assertRaisesRegex(MotorRouteError, "blocked at d3"):
            self.planner.plan_route(
                "d2", "d4", occupied_squares={"d2", "d3"}
            )

    def test_finds_knight_route_around_occupied_squares(self) -> None:
        route = self.planner.plan_route(
            "b1",
            "c3",
            occupied_squares={"b1", "c1", "c2", "b2"},
        )

        self.assertEqual(
            self.planner.encode_route(route),
            "1,0:1.5,0.5:1.5,1.5:2.08,2.08|",
        )

    def test_rejects_occupied_destination(self) -> None:
        with self.assertRaisesRegex(MotorRouteError, "capture routes are not supported"):
            self.planner.plan_route(
                "d2", "d4", occupied_squares={"d2", "d4"}
            )

    def test_plans_capture_to_i4_before_capturing_move(self) -> None:
        occupied = {
            "a1", "a2", "a7", "a8", "b1", "b2", "b8", "c1", "c2", "c7",
            "c8", "d1", "d7", "d8", "e1", "e2", "e7", "e8", "f1", "f2",
            "f7", "f8", "g1", "g2", "g7", "g8", "h1", "h2", "h7", "h8",
        }

        plan = self.planner.plan_capture(
            "d1", "d7", occupied_squares=occupied
        )

        self.assertEqual(
            self.planner.encode_route(plan.parking_route),
            "3,6:3,5:4,5:5,5:6,5:7,5:7,4:7,3:8.08,2.92|",
        )
        self.assertEqual(
            self.planner.encode_route(plan.capturing_route), "3,0:3,6.08|"
        )

    def test_rejects_capture_and_special_moves(self) -> None:
        occupied = {"e5", "f7"}
        unsupported_moves = (
            MovePlan("e5", "f7", capture_square="f7"),
            MovePlan("e1", "g1", piece=PieceKind.KING, is_castle=True),
            MovePlan("e7", "e8", promotion=PieceKind.QUEEN),
        )

        for move in unsupported_moves:
            with self.subTest(move=move):
                with self.assertRaises(MotorRouteError):
                    self.planner.plan_move(move, occupied_squares=occupied)

    def test_plans_all_castling_routes_king_first(self) -> None:
        cases = (
            (
                "e1",
                "g1",
                {"e1", "h1"},
                "4,0:6.08,0|",
                "7,0:6.5,0.5:5.5,0.5:4.92,0|",
            ),
            (
                "e1",
                "c1",
                {"e1", "a1"},
                "4,0:1.92,0|",
                "0,0:0.5,0.5:1.5,0.5:2.5,0.5:3.08,0|",
            ),
            (
                "e8",
                "g8",
                {"e8", "h8"},
                "4,7:6.08,7|",
                "7,7:6.5,6.5:5.5,6.5:4.92,7|",
            ),
            (
                "e8",
                "c8",
                {"e8", "a8"},
                "4,7:1.92,7|",
                "0,7:0.5,6.5:1.5,6.5:2.5,6.5:3.08,7|",
            ),
        )

        for king_from, king_to, occupied, king_route, rook_route in cases:
            with self.subTest(king_from=king_from, king_to=king_to):
                plan = self.planner.plan_castle(
                    king_from, king_to, occupied_squares=occupied
                )

                self.assertEqual(self.planner.encode_route(plan.king.route), king_route)
                self.assertEqual(self.planner.encode_route(plan.rook.route), rook_route)

    def test_rejects_castle_with_blocked_king_path(self) -> None:
        with self.assertRaisesRegex(MotorRouteError, "blocked at f1"):
            self.planner.plan_castle(
                "e1", "g1", occupied_squares={"e1", "f1", "h1"}
            )

    def test_rejects_non_line_non_knight_route(self) -> None:
        with self.assertRaisesRegex(MotorRouteError, "not a straight or knight move"):
            self.planner.plan_route("a1", "c4", occupied_squares={"a1"})


if __name__ == "__main__":
    unittest.main()
