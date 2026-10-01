// Renders the synth benchmark's `bass-acid` target with Open303 (Robin Schmidt, MIT licence),
// fetched at a pinned commit by render.sh. The patch is set here by hand; Open303 ships no
// presets.
//
//     acid OUT.wav
//
// One accented C2 with a slide into G2 at 0.30 s, released at 0.75 s. Mono 44.1 kHz 32-bit
// float WAV.

#include "rosic_Open303.h"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <vector>

using namespace rosic;

static void put32(FILE* f, uint32_t v) { fwrite(&v, 4, 1, f); }
static void put16(FILE* f, uint16_t v) { fwrite(&v, 2, 1, f); }

int main(int argc, char** argv) {
  if (argc != 2) {
    fprintf(stderr, "usage: acid OUT.wav\n");
    return 2;
  }
  const double sr = 44100.0;
  Open303 s;
  s.setSampleRate(sr);
  s.setWaveform(0.0);  // saw
  s.setTuning(440.0);
  s.setCutoff(420.0);
  s.setResonance(85.0);
  s.setEnvMod(80.0);
  s.setDecay(500.0);
  s.setAccent(85.0);
  s.setVolume(-12.0);
  s.setSlideTime(60.0);
  s.setAmpSustain(-60.0);

  const int n = (int)(1.3 * sr);
  const int slide_at = (int)(0.30 * sr), release_at = (int)(0.75 * sr);
  std::vector<float> out(n);
  s.noteOn(36, 120, 0.0);
  for (int i = 0; i < n; i++) {
    if (i == slide_at) {
      s.noteOn(43, 120, 0.0);  // still holding C2, so this slides
      s.noteOn(36, 0, 0.0);
    }
    if (i == release_at) s.noteOn(43, 0, 0.0);
    double y = s.getSample();
    if (!std::isfinite(y)) {
      fprintf(stderr, "non-finite sample at %d\n", i);
      return 1;
    }
    out[i] = (float)y;
  }

  FILE* f = fopen(argv[1], "wb");
  if (!f) return 1;
  fwrite("RIFF", 1, 4, f);
  put32(f, 36 + 4 * n);
  fwrite("WAVEfmt ", 1, 8, f);
  put32(f, 16);
  put16(f, 3);  // IEEE float
  put16(f, 1);
  put32(f, (uint32_t)sr);
  put32(f, (uint32_t)sr * 4);
  put16(f, 4);
  put16(f, 32);
  fwrite("data", 1, 4, f);
  put32(f, 4 * n);
  fwrite(out.data(), 4, n, f);
  fclose(f);
  return 0;
}
