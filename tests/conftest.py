from __future__ import annotations

import chess
import chess.engine
import pytest

import server


class FakeEngine:
    """
    Deterministic stand-in for a Stockfish ``SimpleEngine``.

    Each position has a static White-POV score (``scores`` keyed by FEN, else 0). Candidate
    moves are ranked by the score of the resulting position from the mover's side, so the
    root score always equals the best line's score, as with a real engine.
    """

    def __init__(self, scores: dict[str, int] | None = None) -> None:
        self.scores = scores or {}
        self.configured: list[dict] = []
        self.options = {
            "UCI_Elo": chess.engine.Option("UCI_Elo", "spin", 1320, 1320, 3190, []),
            "Skill Level": chess.engine.Option("Skill Level", "spin", 20, 0, 20, []),
        }

    def configure(self, options: dict) -> None:
        self.configured.append(dict(options))

    def _static_white_cp(self, board: chess.Board) -> int:
        return self.scores.get(board.fen(), 0)

    def _ranked_lines(self, board: chess.Board) -> list[tuple[chess.Move, int]]:
        lines = []
        for move in sorted(board.legal_moves, key=lambda m: m.uci()):
            child = board.copy()
            child.push(move)
            lines.append((move, self._static_white_cp(child)))
        sign = 1 if board.turn == chess.WHITE else -1
        lines.sort(key=lambda line: -sign * line[1])
        return lines

    def analyse(self, board: chess.Board, limit, multipv: int | None = None):
        if board.is_checkmate():
            infos = [{"score": chess.engine.PovScore(chess.engine.Mate(0), board.turn), "pv": []}]
        else:
            infos = [
                {"score": chess.engine.PovScore(chess.engine.Cp(cp), chess.WHITE), "pv": [move]}
                for move, cp in self._ranked_lines(board)
            ]
        if multipv is None:
            return infos[0]
        return infos[:multipv]

    def play(self, board: chess.Board, limit) -> chess.engine.PlayResult:
        move, _ = self._ranked_lines(board)[0]
        return chess.engine.PlayResult(move, None)


@pytest.fixture(scope="session", autouse=True)
def close_real_engine():
    # python-chess keeps Stockfish on a non-daemon thread, so the interpreter
    # would wait on it forever at exit unless the engine is quit explicitly.
    yield
    server.close_engine()


@pytest.fixture
def fake_engine(monkeypatch) -> FakeEngine:
    engine = FakeEngine()
    monkeypatch.setattr(server, "get_engine", lambda: engine)
    return engine


@pytest.fixture
def client():
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c
