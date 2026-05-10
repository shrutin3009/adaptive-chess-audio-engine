/**
 * Chess + Stockfish UI. Human vs computer; play as White or Black (board orients to you).
 * Mix: ambience bed (MIX_AMBIENCE); SFX a little louder (MIX_SFX_MOVE); dramatic cues slightly above that.
 * Dramatic cues (mate / loss / resign) duck ambience with a short fade; SFX use short fade-in/out.
 */

(function () {
  const game = new Chess();
  let board = null;

  /** Human side: ``'w'`` or ``'b'``. */
  let humanColor = 'w';
  const BOT_REPLY_DELAY_MS = 2000;
  /** Ambience fade before mate / loss / resign stings. */
  const AMBIENCE_FADE_BEFORE_DRAMATIC_MS = 500;
  /** Fade ambience in after Start (quiet bed under SFX). */
  const AMBIENCE_FADE_IN_MS = 110;

  /** Mix: SFX only modestly above ambience so the bed stays present (masters are pre-limited). */
  const MIX_AMBIENCE = 0.22;
  /** Easy mode: louder ambience bed and sine move stings (no move WAVs). */
  const MIX_EASY_AMBIENCE_MUL = 1.5;
  const MIX_EASY_SYNTH_MUL = 1.75;
  /** Hard pack masters read hot — scale SFX + bed vs Medium. */
  const MIX_HARD_PACK_MUL = 0.72;
  const MIX_HARD_AMBIENCE_MUL = 0.78;
  const MIX_SFX_MOVE = 0.32;
  /** Move-sting tweaks vs MIX_SFX_MOVE. */
  const MIX_SFX_EXCELLENT = 0.66;
  /** Hard pack ``excellent.wav`` — stays above ``MIX_SFX_GOOD_HARD``. */
  const MIX_SFX_EXCELLENT_HARD = 0.74;
  const MIX_SFX_GOOD = 0.64;
  /** Hard pack ``good.wav`` — louder bed than Medium. */
  const MIX_SFX_GOOD_HARD = 0.7;
  const MIX_SFX_INACCURACY = 0.5;
  const MIX_SFX_MISTAKE = 0.58;
  const MIX_SFX_BLUNDER = 0.6;
  /** Hard pack ``blunder.wav`` — extra presence vs Medium. */
  const MIX_SFX_BLUNDER_HARD = 0.72;
  const MIX_SFX_GREAT = 0.56;
  const MIX_SFX_BEST = 0.6;
  /** Opening-book hits were barely audible at base move level. */
  const MIX_SFX_BOOK = 0.56;
  const MIX_SFX_DRAMATIC = 0.38;
  /** Win sting: pack ``checkmate_win.wav`` + ``/static/sounds/checkmate.wav`` — big moment. */
  const MIX_SFX_CHECKMATE_WIN = 0.82;
  /** Louder than other dramatic stings — ``checkmateLoss.wav`` (mate + resign lead-in). */
  const MIX_SFX_MATE_LOSS = 0.62;
  const SFX_FADE_IN_MS = 48;
  const SFX_FADE_OUT_MS = 72;

  let botDifficulty = 'medium';
  let isBotThinking = false;
  /** @type {ReturnType<typeof setTimeout> | null} */
  let botDelayTimer = null;

  /** @type {HTMLAudioElement | null} */
  let ambienceAudio = null;
  /** @type {ReturnType<typeof setInterval> | null} */
  let ambienceFadeIntervalId = null;

  let gameStarted = false;

  let isGameOver = false;
  /** @type {null | 'white' | 'black'} */
  let winner = null;
  /** @type {null | 'resign'} */
  let lossReason = null;

  /** Avoid double-playing checkmateLoss if analyze-move runs more than once. */
  let checkmateLossCueDone = false;

  /** Bot’s last move `{ from, to }` for board highlight (algebraic). */
  let lastBotMoveSquares = null;

  /** Separate from game ambience — sidebar “test ambience” loop. */
  let testAmbienceAudio = null;
  let testAmbienceRampId = null;

  const logEl = document.getElementById('log');
  const statusEl = document.getElementById('status');
  const fenOut = document.getElementById('fen-out');
  const soundHint = document.getElementById('sound-hint');
  const selectBotDifficulty = document.getElementById('select-bot-difficulty');
  const selectHumanColor = document.getElementById('select-human-color');
  const btnStart = document.getElementById('btn-start-game');
  const btnResign = document.getElementById('btn-resign');

  /**
   * Filenames under ``sounds/<Pack>/``. Hard only ships some WAVs; missing labels use **synth**
   * (no Medium WAVs). Harp* files are unused.
   */
  const MOVE_SOUND_FILENAMES = {
    best: 'best.wav',
    blunder: 'blunder.wav',
    book: 'bookMove.wav',
    checkmate: 'checkmate_win.wav',
    excellent: 'excellent.wav',
    good: 'good.wav',
    great: 'great.wav',
    inaccuracy: 'inaccuracy.wav',
    mistake: 'mistake.wav',
  };

  /** When difficulty is ``hard``, these classifications load from ``sounds/Hard/``. */
  const HARD_PACK_CLASSIFICATIONS = {
    best: true,
    blunder: true,
    book: true,
    checkmate: true,
    excellent: true,
    good: true,
    great: true,
    inaccuracy: true,
    mistake: true,
  };

  /** Hard pack uses different filenames than ``Medium`` for some labels. */
  const HARD_MOVE_FILENAME_OVERRIDES = {
    book: 'book.wav',
  };

  function soundsPackFolder() {
    var d = (botDifficulty || 'medium').toLowerCase();
    if (d === 'hard') return 'Hard';
    if (d === 'easy') return 'Easy';
    return 'Medium';
  }

  /** Easy: sine tones only — no ``sounds/Medium|Hard`` or static dramatic files. */
  function isEasyMode() {
    return (botDifficulty || 'medium').toLowerCase() === 'easy';
  }

  function isHardMode() {
    return (botDifficulty || 'medium').toLowerCase() === 'hard';
  }

  function targetAmbienceVolume() {
    if (isEasyMode()) {
      return Math.min(0.95, MIX_AMBIENCE * MIX_EASY_AMBIENCE_MUL);
    }
    if (isHardMode()) {
      return MIX_AMBIENCE * MIX_HARD_AMBIENCE_MUL;
    }
    return MIX_AMBIENCE;
  }

  /** Test-loop volume: Easy/Hard preview URLs vs default bed. */
  function ambienceBedPeakForTestUrl(url) {
    if (isEasyMode() && url && url.indexOf('/Easy/') !== -1) {
      return targetAmbienceVolume();
    }
    if (url && url.indexOf('/Hard/') !== -1) {
      return MIX_AMBIENCE * MIX_HARD_AMBIENCE_MUL;
    }
    return MIX_AMBIENCE;
  }

  function moveSoundUrlInPack(classification, packFolder) {
    var fname =
      packFolder === 'Hard' && HARD_MOVE_FILENAME_OVERRIDES[classification]
        ? HARD_MOVE_FILENAME_OVERRIDES[classification]
        : MOVE_SOUND_FILENAMES[classification];
    if (!fname) return null;
    if (packFolder === 'Hard' && !HARD_PACK_CLASSIFICATIONS[classification]) {
      return null;
    }
    return '/sounds/' + packFolder + '/' + fname;
  }

  function moveSoundUrl(classification) {
    if (isEasyMode()) return null;
    return moveSoundUrlInPack(classification, soundsPackFolder());
  }

  function ambienceUrl() {
    return '/sounds/' + soundsPackFolder() + '/ambience.wav';
  }

  function mateLossUrlForPack(packFolder) {
    if (packFolder === 'Hard') {
      return '/sounds/Hard/checkmate_loss.wav';
    }
    return '/sounds/' + packFolder + '/checkmateLoss.wav';
  }

  /** Medium: ``checkmateLoss.wav``. Hard: ``checkmate_loss.wav``. */
  function mateLossSoundUrl() {
    if (isEasyMode()) return null;
    return mateLossUrlForPack(soundsPackFolder());
  }

  const SOUND_PROFILE = {
    blunder: { hz: 196, dur: 0.34 },
    mistake: { hz: 220, dur: 0.28 },
    inaccuracy: { hz: 247, dur: 0.24 },
    good: { hz: 294, dur: 0.2 },
    excellent: { hz: 349, dur: 0.22 },
    best: { hz: 392, dur: 0.24 },
    great: { hz: 523, dur: 0.3 },
    book: { hz: 311, dur: 0.18 },
    checkmate: { hz: 659, dur: 0.45 },
  };

  let audioCtx = null;

  function ensureContext() {
    if (!audioCtx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) {
        return null;
      }
      audioCtx = new AC();
    }
    return audioCtx;
  }

  /**
   * @param {number} [peakMul] gain vs default sine peak (1 = default).
   */
  function playTone(ctx, freq, durationSec, peakMul) {
    if (!ctx) return;
    var m = peakMul != null ? peakMul : 1;
    const t0 = ctx.currentTime;
    const atk = 0.02;
    const rel = 0.025;
    const peak = Math.min(0.98, 0.34 * MIX_SFX_MOVE * m);
    const dur = Math.max(durationSec, atk + rel + 0.03);
    const tEnd = t0 + dur;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(freq, t0);
    gain.gain.setValueAtTime(0, t0);
    gain.gain.linearRampToValueAtTime(peak, t0 + atk);
    gain.gain.linearRampToValueAtTime(peak, tEnd - rel);
    gain.gain.linearRampToValueAtTime(0, tEnd);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(t0);
    osc.stop(tEnd + 0.02);
  }

  function withRunningAudio(fn) {
    const ctx = ensureContext();
    if (!ctx) {
      if (soundHint) soundHint.textContent = 'Web Audio not supported in this browser.';
      return;
    }

    function run() {
      if (typeof fn === 'function') fn();
    }

    if (ctx.state === 'running') {
      run();
      return;
    }

    const p = ctx.resume();
    if (p && typeof p.then === 'function') {
      p.then(function () {
        run();
      }).catch(function (e) {
        console.error(e);
        if (logEl) logEl.textContent = 'Audio blocked: ' + (e && e.message ? e.message : e);
      });
    } else {
      run();
    }
  }

  function cancelAmbienceFade() {
    if (ambienceFadeIntervalId !== null) {
      clearInterval(ambienceFadeIntervalId);
      ambienceFadeIntervalId = null;
    }
  }

  function stopAmbienceHard() {
    cancelAmbienceFade();
    if (ambienceAudio) {
      try {
        ambienceAudio.pause();
        ambienceAudio.removeAttribute('src');
        ambienceAudio.load();
      } catch (e) {}
      ambienceAudio = null;
    }
  }

  function startAmbienceVolumeRamp(el, fromV, toV, durationMs, onDone) {
    cancelAmbienceFade();
    var t0 = performance.now();
    ambienceFadeIntervalId = setInterval(function () {
      var u = Math.min(1, (performance.now() - t0) / durationMs);
      if (!ambienceAudio || ambienceAudio !== el) {
        cancelAmbienceFade();
        return;
      }
      el.volume = fromV + (toV - fromV) * u;
      if (u >= 1) {
        cancelAmbienceFade();
        el.volume = toV;
        if (typeof onDone === 'function') onDone();
      }
    }, 16);
  }

  function stopTestAmbience() {
    if (testAmbienceRampId !== null) {
      clearInterval(testAmbienceRampId);
      testAmbienceRampId = null;
    }
    if (testAmbienceAudio) {
      try {
        testAmbienceAudio.pause();
        testAmbienceAudio.removeAttribute('src');
        testAmbienceAudio.load();
      } catch (e) {}
      testAmbienceAudio = null;
    }
  }

  function startTestAmbienceFromUrl(url) {
    stopTestAmbience();
    var a = new Audio(url);
    a.loop = true;
    a.volume = 0;
    testAmbienceAudio = a;
    var p = a.play();
    function ramp() {
      var t0 = performance.now();
      testAmbienceRampId = setInterval(function () {
        if (testAmbienceAudio !== a) {
          if (testAmbienceRampId !== null) {
            clearInterval(testAmbienceRampId);
            testAmbienceRampId = null;
          }
          return;
        }
        var bedPeak = ambienceBedPeakForTestUrl(url);
        var u = Math.min(1, (performance.now() - t0) / AMBIENCE_FADE_IN_MS);
        a.volume = bedPeak * u;
        if (u >= 1) {
          clearInterval(testAmbienceRampId);
          testAmbienceRampId = null;
          a.volume = bedPeak;
        }
      }, 16);
    }
    if (p && typeof p.then === 'function') {
      p.then(ramp).catch(function () {});
    } else {
      ramp();
    }
  }

  function startTestAmbience() {
    var url = ambienceUrl();
    if (!url) return;
    startTestAmbienceFromUrl(url);
  }

  function wireHardPackPreviewPanel() {
    var panel = document.getElementById('hard-audio-test-panel');
    if (!panel) return;
    panel.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-hard-audio-test]');
      if (!btn || !panel.contains(btn)) return;
      var kind = btn.getAttribute('data-hard-audio-test');
      if (!kind) return;
      withRunningAudio(function () {});
      if (kind === 'ambience-start') {
        startTestAmbienceFromUrl('/sounds/Hard/ambience.wav');
        return;
      }
      if (kind === 'ambience-stop') {
        stopTestAmbience();
        return;
      }
      if (kind === 'mate-win') {
        var pathMw = moveSoundUrlInPack('checkmate', 'Hard');
        var profMw = SOUND_PROFILE.checkmate;
        if (!pathMw) {
          triggerSynthFallback(profMw, true);
          return;
        }
        var pkMw = peakForMoveClassification('checkmate', 'Hard');
        playSfxUrl(
          pathMw,
          pkMw,
          function () {
            playSfxUrl(
              '/static/sounds/checkmate.wav',
              pkMw,
              function () {
                triggerSynthFallback(profMw, true);
              },
              null,
              { fadeInMs: 0 }
            );
          },
          null,
          { fadeInMs: 0 }
        );
        return;
      }
      if (kind === 'mate-loss') {
        playUrlThenSynthFallback(
          mateLossUrlForPack('Hard'),
          SOUND_PROFILE.checkmate
        );
        return;
      }
      if (kind === 'resign') {
        playResignCue();
        return;
      }
      var path = moveSoundUrlInPack(kind, 'Hard');
      var profile = SOUND_PROFILE[kind] || SOUND_PROFILE.good;
      if (!path) {
        triggerSynthFallback(profile, true);
        return;
      }
      var peak = peakForMoveClassification(kind, 'Hard');
      playSfxUrl(
        path,
        peak,
        function () {
          triggerSynthFallback(profile, true);
        }
      );
    });
  }

  function wireAudioTestPanel() {
    var panel = document.getElementById('audio-test-panel');
    if (!panel) return;
    panel.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-audio-test]');
      if (!btn || !panel.contains(btn)) return;
      var kind = btn.getAttribute('data-audio-test');
      if (!kind) return;
      withRunningAudio(function () {});
      if (kind === 'ambience-start') {
        startTestAmbience();
        return;
      }
      if (kind === 'ambience-stop') {
        stopTestAmbience();
        return;
      }
      if (kind === 'mate-win') {
        triggerSoundForClassification('checkmate');
        return;
      }
      if (kind === 'mate-loss') {
        playUrlThenSynthFallback(mateLossSoundUrl(), SOUND_PROFILE.checkmate);
        return;
      }
      if (kind === 'resign') {
        playResignCue();
        return;
      }
      triggerSoundForClassification(kind);
    });
  }

  function preloadDramaticStings() {
    [moveSoundUrl('checkmate'), mateLossSoundUrl()]
      .filter(Boolean)
      .forEach(function (src) {
        try {
          var x = new Audio();
          x.preload = 'auto';
          x.src = src;
          x.load();
        } catch (e) {}
      });
  }

  function startAmbience() {
    stopAmbienceHard();
    var url = ambienceUrl();
    if (!url) return;
    var a = new Audio(url);
    a.loop = true;
    a.volume = 0;
    ambienceAudio = a;
    var p = a.play();
    function rampUp() {
      startAmbienceVolumeRamp(
        a,
        0,
        targetAmbienceVolume(),
        AMBIENCE_FADE_IN_MS,
        null
      );
    }
    if (p && typeof p.then === 'function') {
      p.then(rampUp).catch(function (err) {
        console.warn('Ambience could not play:', err);
      });
    } else {
      rampUp();
    }
  }

  /**
   * Fade ambience volume to 0 over durationMs, then stop element.
   * Uses setInterval so volume ramps reliably (rAF timestamp quirks can produce NaN volume).
   */
  function fadeOutAmbienceThen(durationMs, onDone) {
    cancelAmbienceFade();
    var el = ambienceAudio;
    if (!el) {
      if (typeof onDone === 'function') onDone();
      return;
    }
    var startVol = el.volume;
    if (typeof startVol !== 'number' || startVol !== startVol) {
      startVol = targetAmbienceVolume();
    }
    var t0 = performance.now();
    var stepMs = 40;
    try {
      if (el.paused) {
        var rp = el.play();
        if (rp && typeof rp.then === 'function') {
          rp.catch(function () {});
        }
      }
    } catch (e) {}
    ambienceFadeIntervalId = setInterval(function () {
      var elapsed = performance.now() - t0;
      var t = Math.min(1, elapsed / durationMs);
      if (!ambienceAudio || ambienceAudio !== el) {
        cancelAmbienceFade();
        return;
      }
      var vol = startVol * (1 - t);
      el.volume = vol > 0 ? vol : 0;
      if (t >= 1) {
        cancelAmbienceFade();
        var done = onDone;
        if (typeof done === 'function') done();
        stopAmbienceHard();
      }
    }, stepMs);
  }

  function playCheckmateSting() {
    triggerSoundForClassification('checkmate');
  }

  /**
   * One-shot SFX: non-blocking (new element per call), fade-in / fade-out to reduce clicks,
   * overlaps with ambience and other SFX.
   */
  /**
   * @param {object} [opts]
   * @param {number} [opts.fadeInMs] default SFX_FADE_IN_MS; use 0 so sting hits right after ambience duck (masters are pre-enveloped).
   */
  function playSfxUrl(url, peakLevel, onHardFail, onEnded, opts) {
    opts = opts || {};
    var fadeInMs =
      opts.fadeInMs != null ? opts.fadeInMs : SFX_FADE_IN_MS;
    var el = new Audio(url);
    var failedOnce = false;
    function fail() {
      if (failedOnce) return;
      failedOnce = true;
      if (typeof onHardFail === 'function') onHardFail();
    }
    el.addEventListener('error', fail);
    el.preload = 'auto';
    el.volume = 0;
    var fadeOutMs = SFX_FADE_OUT_MS;
    var tailStarted = false;
    var fadeInId = null;

    el.addEventListener('playing', function onPlaying() {
      el.removeEventListener('playing', onPlaying);
      if (el.duration && el.duration < 0.14) {
        tailStarted = true;
      }
    });

    function startTailFade() {
      if (tailStarted) return;
      if (!el.duration || !isFinite(el.duration) || el.duration <= 0) return;
      var rem = el.duration - el.currentTime;
      if (rem > fadeOutMs / 1000 + 0.03) return;
      tailStarted = true;
      var v0 = Math.max(0, Math.min(peakLevel, el.volume));
      var t0 = performance.now();
      var iv = setInterval(function () {
        var u = Math.min(1, (performance.now() - t0) / fadeOutMs);
        el.volume = v0 * (1 - u);
        if (u >= 1) {
          clearInterval(iv);
          el.volume = 0;
        }
      }, 16);
    }

    el.addEventListener('timeupdate', startTailFade);
    el.addEventListener('ended', function () {
      if (fadeInId !== null) {
        clearInterval(fadeInId);
        fadeInId = null;
      }
      el.volume = 0;
      if (typeof onEnded === 'function') onEnded();
    });

    function beginFadeIn() {
      if (fadeInMs <= 0) {
        el.volume = peakLevel;
        return;
      }
      var t0 = performance.now();
      fadeInId = setInterval(function () {
        var u = Math.min(1, (performance.now() - t0) / fadeInMs);
        el.volume = peakLevel * u;
        if (u >= 1) {
          clearInterval(fadeInId);
          fadeInId = null;
          el.volume = peakLevel;
        }
      }, 16);
    }

    var p = el.play();
    if (p && typeof p.then === 'function') {
      p.then(beginFadeIn).catch(fail);
    } else {
      beginFadeIn();
    }
  }

  function playUrlThenSynthFallback(url, profile) {
    if (!url) {
      withRunningAudio(function () {
        triggerSynthFallback(profile);
      });
      return;
    }
    var lossPeak = MIX_SFX_MATE_LOSS;
    if (url && url.indexOf('/Hard/') !== -1) {
      lossPeak = Math.min(0.98, lossPeak * MIX_HARD_PACK_MUL);
    }
    playSfxUrl(
      url,
      lossPeak,
      function () {
        triggerSynthFallback(profile, true);
      },
      null,
      { fadeInMs: 0 }
    );
  }

  function playResignMp3() {
    var dr = MIX_SFX_DRAMATIC;
    if (isHardMode()) {
      dr = Math.min(0.98, dr * MIX_HARD_PACK_MUL);
    }
    playSfxUrl('/static/sounds/resign.mp3', dr, null);
  }

  /** Easy mode: short descending sine pair (no MP3). */
  function playEasyResignSynth() {
    var ctx = ensureContext();
    if (!ctx) return;
    function run() {
      playTone(ctx, 233, 0.14, MIX_EASY_SYNTH_MUL);
      window.setTimeout(function () {
        playTone(ctx, 175, 0.22, MIX_EASY_SYNTH_MUL);
      }, 100);
    }
    if (ctx.state === 'running') run();
    else ctx.resume().then(run).catch(function () {});
  }

  function playResignCue() {
    if (isEasyMode()) {
      withRunningAudio(function () {
        playEasyResignSynth();
      });
      return;
    }
    playResignMp3();
  }

  function peakForMoveClassification(classification, packFolder) {
    var folder = packFolder != null ? packFolder : soundsPackFolder();
    var peak;
    if (classification === 'checkmate') peak = MIX_SFX_CHECKMATE_WIN;
    else if (classification === 'best') peak = MIX_SFX_BEST;
    else if (classification === 'great') peak = MIX_SFX_GREAT;
    else if (classification === 'excellent') {
      peak = folder === 'Hard' ? MIX_SFX_EXCELLENT_HARD : MIX_SFX_EXCELLENT;
    } else if (classification === 'good') {
      peak = folder === 'Hard' ? MIX_SFX_GOOD_HARD : MIX_SFX_GOOD;
    } else if (classification === 'book') peak = MIX_SFX_BOOK;
    else if (classification === 'inaccuracy') peak = MIX_SFX_INACCURACY;
    else if (classification === 'mistake') peak = MIX_SFX_MISTAKE;
    else if (classification === 'blunder') {
      peak = folder === 'Hard' ? MIX_SFX_BLUNDER_HARD : MIX_SFX_BLUNDER;
    } else peak = MIX_SFX_MOVE;

    if (folder === 'Hard') {
      peak = Math.min(0.98, peak * MIX_HARD_PACK_MUL);
    }
    return peak;
  }

  function triggerSoundForClassification(classification) {
    var profile = SOUND_PROFILE[classification] || SOUND_PROFILE.good;
    var path = moveSoundUrl(classification);
    if (!path) {
      withRunningAudio(function () {
        triggerSynthFallback(profile);
      });
      return;
    }
    var peak = peakForMoveClassification(classification);

    var mateOpts = classification === 'checkmate' ? { fadeInMs: 0 } : null;
    playSfxUrl(
      path,
      peak,
      function () {
        if (classification === 'checkmate') {
          playSfxUrl(
            '/static/sounds/checkmate.wav',
            MIX_SFX_CHECKMATE_WIN,
            function () {
              triggerSynthFallback(profile, true);
            },
            null,
            { fadeInMs: 0 }
          );
        } else {
          triggerSynthFallback(profile, true);
        }
      },
      null,
      mateOpts
    );
  }

  /**
   * @param {boolean} [fromFailedPack] if true, use normal synth level (WAV decode/play failed).
   */
  function triggerSynthFallback(profile, fromFailedPack) {
    var ctx = ensureContext();
    if (!ctx) return;
    var mul =
      fromFailedPack === true ? 1 : isEasyMode() ? MIX_EASY_SYNTH_MUL : 1;
    function fire() {
      playTone(ctx, profile.hz, profile.dur, mul);
    }
    if (ctx.state === 'running') {
      fire();
      return;
    }
    ctx.resume().then(fire).catch(function () {});
  }

  function setLog(text) {
    if (logEl) logEl.textContent = text;
  }

  function syncControlButtons() {
    if (btnStart) {
      var finished =
        isGameOver || game.game_over();
      var showRestart = gameStarted && finished;
      btnStart.disabled = gameStarted && !showRestart;
      btnStart.textContent = showRestart ? 'Restart' : 'Start';
    }
    if (btnResign) btnResign.disabled = !gameStarted || isGameOver || game.game_over();
    if (selectHumanColor) {
      selectHumanColor.disabled =
        gameStarted && !(isGameOver || game.game_over());
    }
  }

  function updateStatus() {
    let status = '';
    if (!gameStarted) {
      status = 'Click Start to begin — pieces are locked until then';
    } else if (isGameOver && lossReason === 'resign') {
      status =
        (humanColor === 'w' ? 'Black' : 'White') + ' wins by resignation';
    } else if (game.in_checkmate()) {
      status = 'Checkmate';
    } else if (game.in_draw()) {
      status = 'Draw';
    } else {
      status = (game.turn() === 'w' ? 'White' : 'Black') + ' to move';
      if (game.in_check()) {
        status += ' — Check';
      }
    }
    if (gameStarted && !game.game_over() && !isGameOver) {
      status +=
        ' | You: ' +
        (humanColor === 'w' ? 'White' : 'Black') +
        (isBotThinking ? ' | Bot thinking…' : '');
    }
    if (statusEl) statusEl.textContent = status;
    if (fenOut) fenOut.textContent = game.fen();
    syncControlButtons();
  }

  function uciFromMove(move) {
    if (!move || !move.from || !move.to) return '';
    return (
      move.from +
      move.to +
      (move.promotion !== undefined && move.promotion !== null ? move.promotion : '')
    );
  }

  function applyUciMove(uci) {
    if (!uci || uci.length < 4) return null;
    var from = uci.slice(0, 2);
    var to = uci.slice(2, 4);
    var prom = uci.length > 4 ? uci.slice(4, 5) : undefined;
    return game.move({
      from: from,
      to: to,
      promotion: prom || 'q',
    });
  }

  function syncBoardOrientation() {
    if (!board) return;
    board.orientation(humanColor === 'w' ? 'white' : 'black');
  }

  function parseUciToSquares(uci) {
    if (!uci || uci.length < 4) return null;
    var from = uci.slice(0, 2).toLowerCase();
    var to = uci.slice(2, 4).toLowerCase();
    if (!/^[a-h][1-8]$/.test(from) || !/^[a-h][1-8]$/.test(to)) return null;
    return { from: from, to: to };
  }

  function clearBotMoveHighlight() {
    var root = document.getElementById('board');
    if (!root) return;
    var nodes = root.querySelectorAll('.square-last-bot');
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].classList.remove('square-last-bot');
    }
  }

  function refreshBotMoveHighlight() {
    clearBotMoveHighlight();
    if (!lastBotMoveSquares) return;
    var root = document.getElementById('board');
    if (!root) return;
    var a = root.querySelector('[data-square="' + lastBotMoveSquares.from + '"]');
    var b = root.querySelector('[data-square="' + lastBotMoveSquares.to + '"]');
    if (a) a.classList.add('square-last-bot');
    if (b) b.classList.add('square-last-bot');
  }

  function setLastBotMoveFromUci(uci) {
    lastBotMoveSquares = parseUciToSquares(uci);
    setTimeout(refreshBotMoveHighlight, 0);
  }

  function clearLastBotMove() {
    lastBotMoveSquares = null;
    clearBotMoveHighlight();
  }

  function readControlsFromDom() {
    if (selectBotDifficulty) botDifficulty = selectBotDifficulty.value || 'medium';
    if (selectHumanColor) {
      var hc = selectHumanColor.value || 'w';
      humanColor = hc === 'b' ? 'b' : 'w';
    }
  }

  function botColor() {
    return humanColor === 'w' ? 'b' : 'w';
  }

  function analyzeMove(fenBefore, fenAfter, playedUci, onDone) {
    setLog('Analyzing…');
    fetch('/api/analyze-move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        fen_before: fenBefore,
        fen_after: fenAfter,
        played_uci: playedUci,
      }),
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data };
        });
      })
      .then(function (result) {
        if (!result.ok) {
          setLog('Error: ' + (result.data.error || result.data.message || JSON.stringify(result.data)));
          if (typeof onDone === 'function') onDone();
          return;
        }
        const d = result.data;
        const lines = [
          'Classification: ' + d.classification,
          'Played UCI: ' + (d.played_uci || playedUci),
          'Engine best: ' + (d.best_uci || '?'),
          'Top moves: ' + (d.top_moves_uci || []).join(', '),
          'Mover: ' + (d.mover === 'w' ? 'White' : 'Black'),
          'Phase (after move): ' + (d.game_phase || '?'),
          'Phase (before move): ' + (d.phase_before_move || '?'),
          'Polyglot book move: ' + (d.is_book_move ? 'yes' : 'no'),
          d.book_debug
            ? 'Book path: ' +
                (d.book_debug.opening_book_path || '—') +
                ' | exists: ' +
                d.book_debug.opening_book_path_exists
            : '',
          '',
          (d.classifier || 'Classifier') +
            '\ncp_loss (Eye on Chess): ' +
            (d.cp_loss_eye_on_chess != null ? d.cp_loss_eye_on_chess : '?') +
            '  |  vs-best-child (debug): ' +
            (d.cp_loss_vs_best != null ? d.cp_loss_vs_best : '—'),
          'next_best_eval_white: ' + (d.next_best_eval_white != null ? d.next_best_eval_white : '—'),
          '',
          'Root eval before/after (misleading — side to move flips): ' +
            d.eval_before_cp +
            ' → ' +
            d.eval_after_cp +
            ' (delta ' +
            d.delta_cp +
            ')',
          '',
          'Checkmate on board: ' + (d.is_checkmate_on_board ? 'yes' : 'no'),
          'Stockfish mate (mover POV): is_mate_sequence=' +
            d.is_mate_sequence +
            ' mate_in=' +
            (d.mate_in != null ? d.mate_in : '—') +
            ' mate_for_mover=' +
            d.mate_for_mover,
        ];
        setLog(lines.join('\n'));
        console.log('analyze-move', d);
        // Bot just moved and mated human → loss sting.
        var bc = botColor();
        if (
          d.mover === bc &&
          d.is_checkmate_on_board &&
          !checkmateLossCueDone
        ) {
          checkmateLossCueDone = true;
          fadeOutAmbienceThen(AMBIENCE_FADE_BEFORE_DRAMATIC_MS, function () {
            playUrlThenSynthFallback(mateLossSoundUrl(), SOUND_PROFILE.checkmate);
          });
        } else if (d.mover === humanColor) {
          if (d.is_checkmate_on_board) {
            /* Mate win sting + ambience fade handled in onDrop */
          } else {
            triggerSoundForClassification(d.classification);
          }
        }
        if (typeof onDone === 'function') onDone();
        updateStatus();
      })
      .catch(function (err) {
        setLog('Request failed: ' + err);
        console.error(err);
        if (typeof onDone === 'function') onDone();
      });
  }

  function clearBotDelayTimer() {
    if (botDelayTimer !== null) {
      clearTimeout(botDelayTimer);
      botDelayTimer = null;
    }
  }

  function maybeBotReplyAfterHuman() {
    if (!gameStarted || isGameOver) return;
    if (game.game_over()) return;
    if (game.turn() === humanColor) return;

    clearBotDelayTimer();
    isBotThinking = true;
    updateStatus();

    botDelayTimer = setTimeout(function () {
      botDelayTimer = null;
      if (isGameOver || game.game_over()) {
        isBotThinking = false;
        updateStatus();
        return;
      }
      if (game.turn() === humanColor) {
        isBotThinking = false;
        updateStatus();
        return;
      }
      requestBotMove();
    }, BOT_REPLY_DELAY_MS);
  }

  function requestBotMove() {
    if (!gameStarted || isGameOver) return;
    if (game.game_over()) return;
    if (game.turn() === humanColor) return;

    isBotThinking = true;
    updateStatus();

    fetch('/api/bot-move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        fen: game.fen(),
        difficulty: botDifficulty,
      }),
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data };
        });
      })
      .then(function (result) {
        if (isGameOver) {
          isBotThinking = false;
          updateStatus();
          return;
        }
        if (!result.ok) {
          setLog('Bot error: ' + (result.data.error || JSON.stringify(result.data)));
          isBotThinking = false;
          updateStatus();
          return;
        }
        var d = result.data;
        var fenBefore = game.fen();
        var moved = applyUciMove(d.uci);
        if (!moved) {
          setLog('Bot returned illegal move: ' + d.uci);
          isBotThinking = false;
          updateStatus();
          return;
        }
        var fenAfter = game.fen();
        var uci = d.uci;
        updateStatus();
        board.position(game.fen());
        setLastBotMoveFromUci(uci);
        analyzeMove(fenBefore, fenAfter, uci, function () {
          isBotThinking = false;
          updateStatus();
        });
      })
      .catch(function (err) {
        setLog('Bot request failed: ' + err);
        console.error(err);
        isBotThinking = false;
        updateStatus();
      });
  }

  function startGame() {
    readControlsFromDom();
    clearBotDelayTimer();
    stopTestAmbience();

    isGameOver = false;
    winner = null;
    lossReason = null;
    isBotThinking = false;
    checkmateLossCueDone = false;

    game.reset();
    board.position('start');
    clearLastBotMove();
    syncBoardOrientation();

    gameStarted = true;

    preloadDramaticStings();
    startAmbience();

    setLog('(no move yet)');
    updateStatus();
    maybeBotReplyAfterHuman();
  }

  function resignGame() {
    if (!gameStarted || isGameOver || game.game_over()) return;

    clearBotDelayTimer();

    isGameOver = true;
    winner = humanColor === 'w' ? 'black' : 'white';
    lossReason = 'resign';
    isBotThinking = false;

    updateStatus();
    setLog(
      'Game ended by resignation. ' +
        (humanColor === 'w' ? 'Black' : 'White') +
        ' wins.'
    );
    syncControlButtons();

    fadeOutAmbienceThen(AMBIENCE_FADE_BEFORE_DRAMATIC_MS, function () {
      var lossUrl = mateLossSoundUrl();
      var resignCueDone = false;
      function thenResignSting() {
        if (resignCueDone) return;
        resignCueDone = true;
        playResignCue();
      }
      if (!lossUrl) {
        thenResignSting();
        return;
      }
      var resignLossPeak = MIX_SFX_MATE_LOSS;
      if (lossUrl.indexOf('/Hard/') !== -1) {
        resignLossPeak = Math.min(0.98, resignLossPeak * MIX_HARD_PACK_MUL);
      }
      playSfxUrl(
        lossUrl,
        resignLossPeak,
        thenResignSting,
        thenResignSting,
        { fadeInMs: 0 }
      );
    });
  }

  board = Chessboard('board', {
    draggable: true,
    position: 'start',
    orientation: 'white',
    pieceTheme: 'https://chessboardjs.com/img/chesspieces/wikipedia/{piece}.png',
    lightSquareStyle: { backgroundColor: '#3a3a42' },
    darkSquareStyle: { backgroundColor: '#232328' },

    onDragStart: function (source, piece) {
      withRunningAudio(function () {});
      if (soundHint) soundHint.style.display = 'none';

      if (!gameStarted) return false;
      if (isGameOver) return false;
      if (isBotThinking) return false;
      if (game.game_over()) return false;

      if (game.turn() !== humanColor) return false;

      if (
        (game.turn() === 'w' && piece[0] === 'b') ||
        (game.turn() === 'b' && piece[0] === 'w')
      ) {
        return false;
      }
    },

    onDrop: function (source, target) {
      if (!gameStarted || isGameOver || game.game_over()) return 'snapback';

      const fenBefore = game.fen();
      const move = game.move({
        from: source,
        to: target,
        promotion: 'q',
      });

      if (move === null) {
        return 'snapback';
      }

      const fenAfter = game.fen();
      const playedUci = uciFromMove(move);
      const humanMated =
        game.in_checkmate() && game.game_over();

      updateStatus();

      if (humanMated) {
        fadeOutAmbienceThen(AMBIENCE_FADE_BEFORE_DRAMATIC_MS, function () {
          playCheckmateSting();
        });
      }

      analyzeMove(fenBefore, fenAfter, playedUci, function () {
        maybeBotReplyAfterHuman();
      });
    },

    onSnapEnd: function () {
      board.position(game.fen());
      refreshBotMoveHighlight();
    },
  });

  readControlsFromDom();
  syncBoardOrientation();
  updateStatus();

  if (selectBotDifficulty) {
    selectBotDifficulty.addEventListener('change', function () {
      readControlsFromDom();
    });
  }
  if (selectHumanColor) {
    selectHumanColor.addEventListener('change', function () {
      readControlsFromDom();
      syncBoardOrientation();
      if (board) board.position(game.fen());
      refreshBotMoveHighlight();
    });
  }
  if (btnStart) {
    btnStart.addEventListener('click', function () {
      startGame();
    });
  }
  if (btnResign) {
    btnResign.addEventListener('click', function () {
      resignGame();
    });
  }

  if (soundHint) soundHint.style.display = 'block';

  wireAudioTestPanel();
  wireHardPackPreviewPanel();
})();
