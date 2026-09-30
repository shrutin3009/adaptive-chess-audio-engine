/**
 * Adaptive sound for the game: a looping ambience bed per difficulty, a sting for each move
 * classification, dramatic cues for mate and resignation, and Web Audio sine tones as a fallback.
 *
 * Mix: SFX sit only modestly above the ambience bed so it stays present (masters are pre-limited).
 * Dramatic cues duck the ambience with a short fade first; SFX use a short fade-in/out to avoid clicks.
 */

const AUDIO_ROOT = '/static/audio';
/** Bump when replacing files under static/audio/ — browsers cache audio URLs aggressively. */
const AUDIO_CACHE_VERSION = '109a1f9b';

const AMBIENCE_FADE_BEFORE_DRAMATIC_MS = 500;
const AMBIENCE_FADE_IN_MS = 110;
const SFX_FADE_IN_MS = 48;
const SFX_FADE_OUT_MS = 72;

const MIX_AMBIENCE = 0.22;
/** Easy has no move WAVs: its ambience and sine stings are boosted instead. */
const MIX_EASY_AMBIENCE_MUL = 1.5;
const MIX_EASY_SYNTH_MUL = 1.75;
/** Hard pack masters read hot, so its SFX and bed are scaled down relative to Medium. */
const MIX_HARD_PACK_MUL = 0.72;
const MIX_HARD_AMBIENCE_MUL = 0.78;
/** Hard mate-loss sting (also the resign lead-in) sits below the other Hard SFX. */
const MIX_HARD_MATE_LOSS_EXTRA_MUL = 0.66;
const MIX_SFX_MOVE = 0.32;
const MIX_SFX_EXCELLENT = 0.66;
const MIX_SFX_EXCELLENT_HARD = 0.74;
const MIX_SFX_GOOD = 0.64;
const MIX_SFX_GOOD_HARD = 0.7;
const MIX_SFX_INACCURACY = 0.5;
const MIX_SFX_MISTAKE = 0.58;
const MIX_SFX_BLUNDER = 0.6;
const MIX_SFX_BLUNDER_HARD = 0.72;
const MIX_SFX_GREAT = 0.56;
const MIX_SFX_BEST = 0.6;
const MIX_SFX_BOOK = 0.56;
const MIX_SFX_DRAMATIC = 0.38;
const MIX_SFX_CHECKMATE_WIN = 0.82;
const MIX_SFX_MATE_LOSS = 0.62;

const MOVE_SOUND_FILES = {
  best: 'best.wav',
  blunder: 'blunder.wav',
  book: 'book.wav',
  checkmate: 'checkmate_win.wav',
  excellent: 'excellent.wav',
  good: 'good.wav',
  great: 'great.wav',
  inaccuracy: 'inaccuracy.wav',
  mistake: 'mistake.wav',
};

const MOVE_VOLUMES = {
  checkmate: MIX_SFX_CHECKMATE_WIN,
  best: MIX_SFX_BEST,
  great: MIX_SFX_GREAT,
  excellent: MIX_SFX_EXCELLENT,
  good: MIX_SFX_GOOD,
  book: MIX_SFX_BOOK,
  inaccuracy: MIX_SFX_INACCURACY,
  mistake: MIX_SFX_MISTAKE,
  blunder: MIX_SFX_BLUNDER,
};

const HARD_MOVE_VOLUMES = {
  excellent: MIX_SFX_EXCELLENT_HARD,
  good: MIX_SFX_GOOD_HARD,
  blunder: MIX_SFX_BLUNDER_HARD,
};

const SYNTH_TONES = {
  blunder: { hz: 196, seconds: 0.34 },
  mistake: { hz: 220, seconds: 0.28 },
  inaccuracy: { hz: 247, seconds: 0.24 },
  good: { hz: 294, seconds: 0.2 },
  excellent: { hz: 349, seconds: 0.22 },
  best: { hz: 392, seconds: 0.24 },
  great: { hz: 523, seconds: 0.3 },
  book: { hz: 311, seconds: 0.18 },
  checkmate: { hz: 659, seconds: 0.45 },
};

const SHARED_CHECKMATE_URL = `${AUDIO_ROOT}/shared/checkmate.wav`;
const SHARED_RESIGN_URL = `${AUDIO_ROOT}/shared/resign.wav`;

/** 'easy' | 'medium' | 'hard' */
let currentPack = 'medium';
let audioContext = null;
/** @type {HTMLAudioElement | null} */
let ambienceAudio = null;
/** @type {ReturnType<typeof setInterval> | null} */
let ambienceFadeTimer = null;
let reportUnsupported = () => {};

function packForDifficulty(difficulty) {
  const level = (difficulty || 'medium').toLowerCase();
  return level === 'easy' || level === 'hard' ? level : 'medium';
}

export function setDifficulty(difficulty) {
  currentPack = packForDifficulty(difficulty);
}

export function onAudioUnsupported(handler) {
  reportUnsupported = handler;
}

function withCacheBuster(path) {
  return `${path}?v=${AUDIO_CACHE_VERSION}`;
}

function moveSoundUrl(label) {
  if (currentPack === 'easy') return null;
  const file = MOVE_SOUND_FILES[label];
  return file ? withCacheBuster(`${AUDIO_ROOT}/${currentPack}/${file}`) : null;
}

function ambienceUrl() {
  return withCacheBuster(`${AUDIO_ROOT}/${currentPack}/ambience.wav`);
}

function mateLossUrl() {
  if (currentPack === 'easy') return null;
  return withCacheBuster(`${AUDIO_ROOT}/${currentPack}/checkmate_loss.wav`);
}

function ambienceVolume() {
  if (currentPack === 'easy') return Math.min(0.95, MIX_AMBIENCE * MIX_EASY_AMBIENCE_MUL);
  if (currentPack === 'hard') return MIX_AMBIENCE * MIX_HARD_AMBIENCE_MUL;
  return MIX_AMBIENCE;
}

function mateLossVolume() {
  if (currentPack === 'hard') {
    return Math.min(0.98, MIX_SFX_MATE_LOSS * MIX_HARD_PACK_MUL * MIX_HARD_MATE_LOSS_EXTRA_MUL);
  }
  return MIX_SFX_MATE_LOSS;
}

function moveSoundVolume(label) {
  if (currentPack === 'hard') {
    const volume = HARD_MOVE_VOLUMES[label] ?? MOVE_VOLUMES[label] ?? MIX_SFX_MOVE;
    return Math.min(0.98, volume * MIX_HARD_PACK_MUL);
  }
  return MOVE_VOLUMES[label] ?? MIX_SFX_MOVE;
}

function getAudioContext() {
  if (!audioContext) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return null;
    audioContext = new AudioContextClass();
  }
  return audioContext;
}

function playTone(context, frequency, durationSec, gainScale = 1) {
  if (!context) return;
  const attack = 0.02;
  const release = 0.025;
  const peak = Math.min(0.98, 0.34 * MIX_SFX_MOVE * gainScale);
  const start = context.currentTime;
  const end = start + Math.max(durationSec, attack + release + 0.03);
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.type = 'sine';
  oscillator.frequency.setValueAtTime(frequency, start);
  gain.gain.setValueAtTime(0, start);
  gain.gain.linearRampToValueAtTime(peak, start + attack);
  gain.gain.linearRampToValueAtTime(peak, end - release);
  gain.gain.linearRampToValueAtTime(0, end);
  oscillator.connect(gain);
  gain.connect(context.destination);
  oscillator.start(start);
  oscillator.stop(end + 0.02);
}

/** Browsers keep audio suspended until a user gesture; run fn once the context is running. */
function withAudioUnlocked(fn) {
  const context = getAudioContext();
  if (!context) {
    reportUnsupported();
    return;
  }
  if (context.state === 'running') {
    fn();
    return;
  }
  context.resume().then(fn).catch((error) => console.error(error));
}

export function unlockAudio() {
  withAudioUnlocked(() => {});
}

/** @param {boolean} [replacesFailedFile] a tone standing in for a WAV that failed plays at normal level. */
function playSynthTone(tone, replacesFailedFile = false) {
  const context = getAudioContext();
  if (!context) return;
  const gainScale = !replacesFailedFile && currentPack === 'easy' ? MIX_EASY_SYNTH_MUL : 1;
  playWhenRunning(context, () => playTone(context, tone.hz, tone.seconds, gainScale));
}

function playWhenRunning(context, play) {
  if (context.state === 'running') play();
  else context.resume().then(play).catch(() => {});
}

function cancelAmbienceFade() {
  if (ambienceFadeTimer !== null) {
    clearInterval(ambienceFadeTimer);
    ambienceFadeTimer = null;
  }
}

function stopAmbience() {
  cancelAmbienceFade();
  if (!ambienceAudio) return;
  try {
    ambienceAudio.pause();
    ambienceAudio.removeAttribute('src');
    ambienceAudio.load();
  } catch (error) {
    // The element may already be torn down; nothing left to stop.
  }
  ambienceAudio = null;
}

/**
 * Move element.volume linearly between two levels. Uses setInterval rather than
 * requestAnimationFrame because rAF timestamp quirks can produce NaN volumes.
 * Returns the interval id; the ramp also stops itself once shouldStop() is true.
 */
function rampVolume(element, fromVolume, toVolume, durationMs, { stepMs = 16, shouldStop, onDone } = {}) {
  const startedAt = performance.now();
  const timer = setInterval(() => {
    if (shouldStop && shouldStop()) {
      clearInterval(timer);
      return;
    }
    const progress = Math.min(1, (performance.now() - startedAt) / durationMs);
    element.volume = Math.max(0, fromVolume + (toVolume - fromVolume) * progress);
    if (progress >= 1) {
      clearInterval(timer);
      element.volume = toVolume;
      if (onDone) onDone();
    }
  }, stepMs);
  return timer;
}

export function startAmbience() {
  stopAmbience();
  const element = new Audio(ambienceUrl());
  element.loop = true;
  element.volume = 0;
  ambienceAudio = element;
  element
    .play()
    .then(() => {
      cancelAmbienceFade();
      ambienceFadeTimer = rampVolume(element, 0, ambienceVolume(), AMBIENCE_FADE_IN_MS, {
        shouldStop: () => ambienceAudio !== element,
      });
    })
    .catch((error) => console.warn('Ambience could not play:', error));
}

/** Fade the ambience to silence, call onDone, then stop it. */
export function fadeOutAmbience(onDone, durationMs = AMBIENCE_FADE_BEFORE_DRAMATIC_MS) {
  cancelAmbienceFade();
  const element = ambienceAudio;
  if (!element) {
    onDone();
    return;
  }
  let startVolume = element.volume;
  if (typeof startVolume !== 'number' || Number.isNaN(startVolume)) {
    startVolume = ambienceVolume();
  }
  if (element.paused) {
    element.play().catch(() => {});
  }
  ambienceFadeTimer = rampVolume(element, startVolume, 0, durationMs, {
    stepMs: 40,
    shouldStop: () => ambienceAudio !== element,
    onDone: () => {
      onDone();
      stopAmbience();
    },
  });
}

export function preloadDramaticStings() {
  for (const url of [moveSoundUrl('checkmate'), mateLossUrl()]) {
    if (!url) continue;
    const element = new Audio();
    element.preload = 'auto';
    element.src = url;
    element.load();
  }
}

/**
 * One-shot sound effect. Each call gets its own element so stings can overlap each other and the
 * ambience. fadeInMs 0 lets a sting land right after an ambience duck (those masters are pre-enveloped).
 */
function playSfx(url, peak, { onFail, onEnded, fadeInMs = SFX_FADE_IN_MS } = {}) {
  const element = new Audio(url);
  let failed = false;
  const fail = () => {
    if (failed) return;
    failed = true;
    if (onFail) onFail();
  };
  element.addEventListener('error', fail);
  element.preload = 'auto';
  element.volume = 0;
  let tailFadeStarted = false;
  let fadeInTimer = null;

  element.addEventListener(
    'playing',
    () => {
      // Clips this short end before a tail fade could run.
      if (element.duration && element.duration < 0.14) tailFadeStarted = true;
    },
    { once: true }
  );

  element.addEventListener('timeupdate', () => {
    if (tailFadeStarted) return;
    const duration = element.duration;
    if (!duration || !isFinite(duration) || duration <= 0) return;
    if (duration - element.currentTime > SFX_FADE_OUT_MS / 1000 + 0.03) return;
    tailFadeStarted = true;
    rampVolume(element, Math.max(0, Math.min(peak, element.volume)), 0, SFX_FADE_OUT_MS);
  });

  element.addEventListener('ended', () => {
    if (fadeInTimer !== null) {
      clearInterval(fadeInTimer);
      fadeInTimer = null;
    }
    element.volume = 0;
    if (onEnded) onEnded();
  });

  const fadeIn = () => {
    if (fadeInMs <= 0) {
      element.volume = peak;
      return;
    }
    fadeInTimer = rampVolume(element, 0, peak, fadeInMs, {
      onDone: () => {
        fadeInTimer = null;
      },
    });
  };

  element.play().then(fadeIn).catch(fail);
}

export function playMoveSound(label) {
  const tone = SYNTH_TONES[label] || SYNTH_TONES.good;
  const url = moveSoundUrl(label);
  if (!url) {
    withAudioUnlocked(() => playSynthTone(tone));
    return;
  }
  const playFallbackTone = () => playSynthTone(tone, true);
  const isCheckmate = label === 'checkmate';
  playSfx(url, moveSoundVolume(label), {
    // A failed pack win sting falls back to the shared checkmate sting before a tone.
    onFail: isCheckmate
      ? () => playSfx(SHARED_CHECKMATE_URL, MIX_SFX_CHECKMATE_WIN, { onFail: playFallbackTone, fadeInMs: 0 })
      : playFallbackTone,
    fadeInMs: isCheckmate ? 0 : SFX_FADE_IN_MS,
  });
}

export function playMateLossSound() {
  const url = mateLossUrl();
  if (!url) {
    withAudioUnlocked(() => playSynthTone(SYNTH_TONES.checkmate));
    return;
  }
  playSfx(url, mateLossVolume(), { onFail: () => playSynthTone(SYNTH_TONES.checkmate, true), fadeInMs: 0 });
}

function playResignSting() {
  let volume = MIX_SFX_DRAMATIC;
  if (currentPack === 'hard') {
    volume = Math.min(0.98, volume * MIX_HARD_PACK_MUL);
  }
  playSfx(SHARED_RESIGN_URL, volume);
}

/** Easy: a short descending sine pair instead of the resign sting. */
function playEasyResignSynth() {
  const context = getAudioContext();
  if (!context) return;
  playWhenRunning(context, () => {
    playTone(context, 233, 0.14, MIX_EASY_SYNTH_MUL);
    setTimeout(() => playTone(context, 175, 0.22, MIX_EASY_SYNTH_MUL), 100);
  });
}

function playResignCue() {
  if (currentPack === 'easy') {
    withAudioUnlocked(playEasyResignSynth);
    return;
  }
  playResignSting();
}

/** The mate-loss sting as a lead-in, then the resign cue once it ends (or fails to load). */
export function playResignSequence() {
  const leadInUrl = mateLossUrl();
  let resignCuePlayed = false;
  const playResignCueOnce = () => {
    if (resignCuePlayed) return;
    resignCuePlayed = true;
    playResignCue();
  };
  if (!leadInUrl) {
    playResignCueOnce();
    return;
  }
  playSfx(leadInUrl, mateLossVolume(), { onFail: playResignCueOnce, onEnded: playResignCueOnce, fadeInMs: 0 });
}
