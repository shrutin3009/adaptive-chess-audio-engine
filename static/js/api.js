/**
 * Calls to the Flask JSON API. Each resolves to { ok, data } for any HTTP status and rejects
 * only when the request fails or the body is not JSON.
 */

async function postJson(url, body) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  return { ok: response.ok, data };
}

export function fetchBotMove(fen, difficulty) {
  return postJson('/api/bot-move', { fen, difficulty });
}

export function fetchMoveAnalysis(fenBefore, fenAfter, playedUci) {
  return postJson('/api/analyze-move', {
    fen_before: fenBefore,
    fen_after: fenAfter,
    played_uci: playedUci,
  });
}
