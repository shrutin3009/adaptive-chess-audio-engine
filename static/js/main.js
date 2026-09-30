/**
 * Game controller: human vs Stockfish on a chessboard.js board, playing as White or Black
 * (the board orients to the human). Every move is sent for analysis and scored with sound.
 * Relies on the chessboard.js, chess.js and jQuery globals loaded by index.html.
 */

import * as api from './api.js';
import * as audio from './audio.js';

const BOT_REPLY_DELAY_MS = 2000;

const game = new Chess();
let board = null;

/** 'w' | 'b' */
let humanColor = 'w';
let botDifficulty = 'medium';
let gameStarted = false;
let isGameOver = false;
/** @type {null | 'resign'} */
let lossReason = null;
let isBotThinking = false;
/** Prefixed to the status line when /api/bot-move fails. */
let botErrorMessage = '';
/** @type {ReturnType<typeof setTimeout> | null} */
let botReplyTimer = null;
/** Avoid playing the mate-loss sting twice if analyze-move runs more than once. */
let mateLossCuePlayed = false;
/** The bot's last move as { from, to } squares, for the board highlight. */
let lastBotMoveSquares = null;

const statusElement = document.getElementById('status');
const soundHint = document.getElementById('sound-hint');
const difficultySelect = document.getElementById('select-bot-difficulty');
const colorSelect = document.getElementById('select-human-color');
const startButton = document.getElementById('btn-start-game');
const resignButton = document.getElementById('btn-resign');

function botColor() {
  return humanColor === 'w' ? 'b' : 'w';
}

function colorName(color) {
  return color === 'w' ? 'White' : 'Black';
}

function clearBotError() {
  botErrorMessage = '';
}

function setBotError(message) {
  botErrorMessage = message || '';
  updateStatus();
}

function syncControls() {
  const finished = isGameOver || game.game_over();
  if (startButton) {
    const showRestart = gameStarted && finished;
    startButton.disabled = gameStarted && !showRestart;
    startButton.textContent = showRestart ? 'Restart' : 'Start';
  }
  if (resignButton) resignButton.disabled = !gameStarted || finished;
  if (colorSelect) colorSelect.disabled = gameStarted && !finished;
}

function updateStatus() {
  let status;
  if (!gameStarted) {
    status = 'Click Start to begin — pieces are locked until then';
  } else if (isGameOver && lossReason === 'resign') {
    status = colorName(botColor()) + ' wins by resignation';
  } else if (game.in_checkmate()) {
    status = 'Checkmate';
  } else if (game.in_draw()) {
    status = 'Draw';
  } else {
    status = colorName(game.turn()) + ' to move';
    if (game.in_check()) status += ' — Check';
  }
  if (gameStarted && !game.game_over() && !isGameOver) {
    status += ' | You: ' + colorName(humanColor) + (isBotThinking ? ' | Bot thinking…' : '');
  }
  if (botErrorMessage) {
    status = botErrorMessage + (status ? ' — ' + status : '');
  }
  if (statusElement) statusElement.textContent = status;
  syncControls();
}

function uciFromMove(move) {
  if (!move || !move.from || !move.to) return '';
  return move.from + move.to + (move.promotion != null ? move.promotion : '');
}

function applyUciMove(uci) {
  if (!uci || uci.length < 4) return null;
  const promotion = uci.length > 4 ? uci.slice(4, 5) : undefined;
  return game.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: promotion || 'q' });
}

function parseUciToSquares(uci) {
  if (!uci || uci.length < 4) return null;
  const from = uci.slice(0, 2).toLowerCase();
  const to = uci.slice(2, 4).toLowerCase();
  if (!/^[a-h][1-8]$/.test(from) || !/^[a-h][1-8]$/.test(to)) return null;
  return { from, to };
}

function syncBoardOrientation() {
  if (!board) return;
  board.orientation(humanColor === 'w' ? 'white' : 'black');
}

function clearBotMoveHighlight() {
  const boardElement = document.getElementById('board');
  if (!boardElement) return;
  for (const square of boardElement.querySelectorAll('.square-last-bot')) {
    square.classList.remove('square-last-bot');
  }
}

function refreshBotMoveHighlight() {
  clearBotMoveHighlight();
  if (!lastBotMoveSquares) return;
  const boardElement = document.getElementById('board');
  if (!boardElement) return;
  for (const square of [lastBotMoveSquares.from, lastBotMoveSquares.to]) {
    const squareElement = boardElement.querySelector('[data-square="' + square + '"]');
    if (squareElement) squareElement.classList.add('square-last-bot');
  }
}

function setLastBotMoveFromUci(uci) {
  lastBotMoveSquares = parseUciToSquares(uci);
  // chessboard.js redraws squares after position(); highlight once it has.
  setTimeout(refreshBotMoveHighlight, 0);
}

function clearLastBotMove() {
  lastBotMoveSquares = null;
  clearBotMoveHighlight();
}

function readControls() {
  if (difficultySelect) {
    botDifficulty = difficultySelect.value || 'medium';
    audio.setDifficulty(botDifficulty);
  }
  if (colorSelect) {
    humanColor = colorSelect.value === 'b' ? 'b' : 'w';
  }
}

function analyzeMove(fenBefore, fenAfter, playedUci, onDone) {
  api
    .fetchMoveAnalysis(fenBefore, fenAfter, playedUci)
    .then(({ ok, data: analysis }) => {
      if (!ok) {
        onDone();
        return;
      }
      if (analysis.mover === botColor() && analysis.is_checkmate_on_board && !mateLossCuePlayed) {
        mateLossCuePlayed = true;
        audio.fadeOutAmbience(audio.playMateLossSound);
      } else if (analysis.mover === humanColor && !analysis.is_checkmate_on_board) {
        // A mating move by the human already got its win sting in onDrop.
        audio.playMoveSound(analysis.classification);
      }
      onDone();
      updateStatus();
    })
    .catch((error) => {
      console.error(error);
      onDone();
    });
}

function clearBotReplyTimer() {
  if (botReplyTimer !== null) {
    clearTimeout(botReplyTimer);
    botReplyTimer = null;
  }
}

function isBotsTurn() {
  return gameStarted && !isGameOver && !game.game_over() && game.turn() !== humanColor;
}

function scheduleBotReply() {
  if (!isBotsTurn()) return;

  clearBotReplyTimer();
  isBotThinking = true;
  updateStatus();

  botReplyTimer = setTimeout(() => {
    botReplyTimer = null;
    if (isGameOver || game.game_over() || game.turn() === humanColor) {
      isBotThinking = false;
      updateStatus();
      return;
    }
    requestBotMove();
  }, BOT_REPLY_DELAY_MS);
}

function requestBotMove() {
  if (!isBotsTurn()) return;

  isBotThinking = true;
  updateStatus();

  const finishThinking = () => {
    isBotThinking = false;
    updateStatus();
  };

  api
    .fetchBotMove(game.fen(), botDifficulty)
    .then(({ ok, data }) => {
      if (isGameOver) {
        finishThinking();
        return;
      }
      if (!ok) {
        setBotError('Bot error: ' + (data.error || JSON.stringify(data)));
        finishThinking();
        return;
      }
      clearBotError();
      const fenBefore = game.fen();
      if (!applyUciMove(data.uci)) {
        finishThinking();
        return;
      }
      const fenAfter = game.fen();
      updateStatus();
      board.position(fenAfter);
      setLastBotMoveFromUci(data.uci);
      analyzeMove(fenBefore, fenAfter, data.uci, finishThinking);
    })
    .catch((error) => {
      setBotError('Bot request failed: ' + error);
      console.error(error);
      finishThinking();
    });
}

function startGame() {
  readControls();
  clearBotReplyTimer();
  clearBotError();

  isGameOver = false;
  lossReason = null;
  isBotThinking = false;
  mateLossCuePlayed = false;

  game.reset();
  board.position('start');
  clearLastBotMove();
  syncBoardOrientation();

  gameStarted = true;

  audio.preloadDramaticStings();
  audio.startAmbience();

  updateStatus();
  scheduleBotReply();
}

function resignGame() {
  if (!gameStarted || isGameOver || game.game_over()) return;

  clearBotReplyTimer();
  isGameOver = true;
  lossReason = 'resign';
  isBotThinking = false;
  updateStatus();

  audio.fadeOutAmbience(audio.playResignSequence);
}

function onDragStart(source, piece) {
  audio.unlockAudio();
  if (soundHint) soundHint.style.display = 'none';

  if (!gameStarted || isGameOver || isBotThinking || game.game_over()) return false;
  if (game.turn() !== humanColor) return false;
  // piece is e.g. 'wP' or 'bK'; only the side to move may be dragged.
  if (piece[0] !== game.turn()) return false;
}

function onDrop(source, target) {
  if (!gameStarted || isGameOver || game.game_over()) return 'snapback';

  const fenBefore = game.fen();
  const move = game.move({ from: source, to: target, promotion: 'q' });
  if (move === null) return 'snapback';

  const fenAfter = game.fen();
  updateStatus();

  if (game.in_checkmate()) {
    audio.fadeOutAmbience(() => audio.playMoveSound('checkmate'));
  }

  analyzeMove(fenBefore, fenAfter, uciFromMove(move), scheduleBotReply);
}

function onSnapEnd() {
  board.position(game.fen());
  refreshBotMoveHighlight();
}

board = Chessboard('board', {
  draggable: true,
  position: 'start',
  orientation: 'white',
  pieceTheme: 'https://chessboardjs.com/img/chesspieces/wikipedia/{piece}.png',
  onDragStart,
  onDrop,
  onSnapEnd,
});

audio.onAudioUnsupported(() => {
  if (soundHint) soundHint.textContent = 'Web Audio not supported in this browser.';
});

readControls();
syncBoardOrientation();
updateStatus();

if (difficultySelect) {
  difficultySelect.addEventListener('change', readControls);
}
if (colorSelect) {
  colorSelect.addEventListener('change', () => {
    readControls();
    syncBoardOrientation();
    board.position(game.fen());
    refreshBotMoveHighlight();
  });
}
if (startButton) startButton.addEventListener('click', startGame);
if (resignButton) resignButton.addEventListener('click', resignGame);

if (soundHint) soundHint.style.display = 'block';
