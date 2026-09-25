// Dev: tap everything connected to an AudioContext destination into an analyser.
// window._audioLevel() -> RMS of the last 2048 output samples; window._audioStats for a running summary.
(function () {
  var orig = AudioNode.prototype.connect;
  window._taps = [];
  AudioNode.prototype.connect = function (dst) {
    try {
      if (dst && dst instanceof AudioDestinationNode) {
        var an = this.context.createAnalyser();
        an.fftSize = 2048;
        orig.call(this, an);
        window._taps.push(an);
      }
    } catch (e) {}
    return orig.apply(this, arguments);
  };
  window._audioLevel = function () {
    var best = 0;
    window._taps.forEach(function (an) {
      var b = new Float32Array(an.fftSize);
      an.getFloatTimeDomainData(b);
      var s = 0;
      for (var i = 0; i < b.length; i++) s += b[i] * b[i];
      best = Math.max(best, Math.sqrt(s / b.length));
    });
    return best;
  };
  window._audioStats = {n: 0, silent: 0, max: 0};
  setInterval(function () {
    if (!window._taps.length) return;
    var l = window._audioLevel();
    var st = window._audioStats;
    st.n++; if (l < 1e-4) st.silent++; st.max = Math.max(st.max, l);
  }, 50);
})();
