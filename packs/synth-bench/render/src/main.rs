//! Renders the synth benchmark's synthetic `electronic` targets with fundsp.
//!
//!     synth-bench-render ID OUT.wav
//!
//! Each patch below is written by hand from textbook synthesis (subtractive, FM, formant
//! filters); none is copied from a synthesizer's presets. Output is 44.1 kHz stereo 32-bit float
//! WAV; build.py trims, levels and converts it like every other source. Deterministic: fundsp's
//! oscillators, noise and envelope jitter are seeded from the graph, so the same binary writes the
//! same bytes.

use fundsp::prelude32::*;
use std::f32::consts::PI;

const SR: f64 = 44100.0;

fn wrap<X: AudioNode + 'static>(x: An<X>) -> Net {
    Net::wrap(Box::new(x))
}

/// A control signal from a function of time (seconds).
fn ctl(f: impl Fn(f32) -> f32 + Clone + Send + Sync + 'static) -> Net {
    wrap(envelope(move |t: f32| f(t)))
}

/// Mono to stereo at `p` in -1..1.
fn panned(x: Net, p: f32) -> Net {
    x >> wrap(pan(p))
}

fn hz(midi: f32) -> f32 {
    440.0 * 2f32.powf((midi - 69.0) / 12.0)
}

/// Linear attack to `a`, hold until `hold_end`, linear release over `r`, as a gain.
fn ahr(a: f32, hold_end: f32, r: f32) -> impl Fn(f32) -> f32 + Clone + Send + Sync {
    move |t| {
        if t < a {
            t / a
        } else if t < hold_end {
            1.0
        } else {
            (1.0 - (t - hold_end) / r).max(0.0)
        }
    }
}

/// Supersaw lead: seven detuned saws (a non-linear detune curve), spread across the stereo
/// field, a pitch-tracking highpass and a gentle lowpass. One held A4.
fn lead_supersaw() -> (Net, f64) {
    let f0 = hz(69.0);
    let curve = [-1.0, -0.62, -0.21, 0.0, 0.2, 0.6, 1.0f32];
    let pans = [-0.95, -0.65, -0.3, 0.0, 0.3, 0.65, 0.95f32];
    let detune_cents = 22.0;
    let mut sum: Option<Net> = None;
    for (i, (&c, &p)) in curve.iter().zip(pans.iter()).enumerate() {
        let f = f0 * 2f32.powf(c * detune_cents / 1200.0);
        let g = if i == 3 { 0.32 } else { 0.22 };
        let v = panned(wrap(dc(f) >> saw()) * g, p);
        sum = Some(match sum {
            None => v,
            Some(s) => s + v,
        });
    }
    let tone = sum.unwrap()
        >> wrap(highpass_hz(f0 * 0.9, 0.6) | highpass_hz(f0 * 0.9, 0.6))
        >> wrap(lowpass_hz(7000.0, 0.7) | lowpass_hz(7000.0, 0.7));
    let amp = ctl(ahr(0.015, 2.0, 0.45));
    (tone * (amp.clone() | amp), 2.5)
}

/// 808 bass: a sine with a fast pitch drop at the strike, a long exponential tail, soft
/// saturation, a 90 ms glide from F1 up to A#1 at 0.6 s, and a fade over the last 0.4 s.
fn bass_808_glide() -> (Net, f64) {
    let (f1, f2) = (hz(29.0), hz(34.0));
    let pitch = ctl(move |t| {
        let base = if t < 0.6 {
            f1
        } else {
            let u = ((t - 0.6) / 0.09).min(1.0);
            let s = u * u * (3.0 - 2.0 * u);
            f1 * (f2 / f1).powf(s)
        };
        base * 2f32.powf(2.0 * (-t / 0.012).exp())
    });
    let amp = ctl(|t| (t / 0.001).min(1.0) * (-t / 1.1).exp() * ((2.9 - t) / 0.4).clamp(0.0, 1.0));
    let body = (pitch >> wrap(sine())) * amp;
    let driven = body >> wrap(shape(Tanh(2.2)));
    (panned(driven * 0.9, 0.0), 2.9)
}

/// House pluck: two saws detuned by 8 cents and a quiet square an octave down, through a
/// resonant ladder lowpass with a fast-decaying cutoff envelope. C4.
fn pluck_house() -> (Net, f64) {
    let f0 = hz(60.0);
    let cutoff = ctl(|t| 220.0 + 5200.0 * (-t / 0.085).exp());
    let amp = ctl(|t| (t / 0.002).min(1.0) * (-t / 0.17).exp());
    let mut out: Option<Net> = None;
    for (cents, p) in [(-8.0f32, -0.45f32), (8.0, 0.45)] {
        let osc = wrap(dc(f0 * 2f32.powf(cents / 1200.0)) >> saw()) * 0.5
            + wrap(dc(f0 * 0.5) >> square()) * 0.12;
        let v = (osc | cutoff.clone()) >> wrap(moog_q(0.42));
        let v = panned(v * amp.clone(), p);
        out = Some(match out {
            None => v,
            Some(s) => s + v,
        });
    }
    (out.unwrap(), 0.8)
}

/// Moving pad: a Cmaj9 chord, each note two pulse waves with their own slow pulse-width LFOs,
/// through ladder lowpasses whose cutoff sweeps up and back over the 4.5 s, slow attack and
/// release, voices spread wide.
fn pad_moving() -> (Net, f64) {
    let notes = [48.0, 52.0, 55.0, 59.0, 62.0f32];
    let cutoff = ctl(|t| 450.0 * 2f32.powf(2.6 * (0.5 - 0.5 * (2.0 * PI * t / 4.6).cos())));
    let mut left: Option<Net> = None;
    let mut right: Option<Net> = None;
    for (i, &n) in notes.iter().enumerate() {
        for (k, side) in [(0usize, -1.0f32), (1, 1.0)] {
            let f = hz(n) * 2f32.powf(side * 7.0 / 1200.0);
            let rate = 0.23 + 0.07 * (i as f32) + 0.05 * (k as f32);
            let ph = 1.3 * i as f32 + 2.1 * k as f32;
            let width = ctl(move |t| 0.5 + 0.38 * (2.0 * PI * rate * t + ph).sin());
            let v = ((wrap(dc(f)) | width) >> wrap(pulse())) * 0.16;
            let side_sum = if k == 0 { &mut left } else { &mut right };
            *side_sum = Some(match side_sum.take() {
                None => v,
                Some(s) => s + v,
            });
        }
    }
    let l = (left.unwrap() | cutoff.clone()) >> wrap(moog_q(0.25));
    let r = (right.unwrap() | cutoff) >> wrap(moog_q(0.25));
    // Keep some of each side in the other so the image is wide but not two separate pads.
    let st = l | r;
    let mix = st >> wrap((pass() * 0.8 + pass() * 0.2) ^ (pass() * 0.2 + pass() * 0.8));
    let amp = ctl(|t| {
        let a = (t / 0.9).min(1.0);
        let rel = if t < 4.0 { 1.0 } else { (1.0 - (t - 4.0) / 0.9).max(0.0) };
        a * a * rel
    });
    (mix * (amp.clone() | amp), 5.0)
}

/// Wobble bass: saw plus square at F1 through a driven ladder lowpass, its cutoff swept by a
/// sine LFO at an eighth note of 140 BPM (4.67 Hz), with a clean sine sub underneath.
fn bass_wobble() -> (Net, f64) {
    let f0 = hz(29.0);
    let rate = 140.0 / 60.0 * 2.0;
    let cutoff = ctl(move |t| 110.0 * 2f32.powf(4.6 * (0.5 - 0.5 * (2.0 * PI * rate * t).cos())));
    let osc = wrap(dc(f0) >> saw()) * 0.6 + wrap(dc(f0 * 1.004) >> square()) * 0.4;
    let filt = (osc * 1.6 >> wrap(shape(Tanh(1.0))) | cutoff) >> wrap(moog_q(0.6));
    let top = filt >> wrap(shape(Tanh(2.0)));
    let sub = wrap(dc(f0) >> sine()) * 0.45;
    let amp = ctl(ahr(0.004, 1.95, 0.05));
    (panned((top * 0.8 + sub) * amp, 0.0), 2.0)
}

/// Growl bass: two-operator FM at F2 whose index moves, through a formant filter (three
/// band-passes) gliding between "o" and "a" vowels, saturated, with a sine sub at F1.
fn bass_growl() -> (Net, f64) {
    let f0 = hz(41.0);
    let index = ctl(|t| 2.2 + 1.8 * (2.0 * PI * 1.9 * t).sin());
    let modu = wrap(dc(f0) >> sine()) * index * f0;
    let car = (modu + wrap(dc(f0))) >> wrap(sine());
    let raw = car >> wrap(shape(Tanh(2.5)));
    // Vowel position 0 = "o" (450, 800, 2830 Hz), 1 = "a" (730, 1090, 2440 Hz).
    let v = move |t: f32| 0.5 - 0.5 * (2.0 * PI * 1.9 * t + 0.6).cos();
    let mut form: Option<Net> = None;
    for (fo, fa, g) in [(450.0f32, 730.0f32, 1.0f32), (800.0, 1090.0, 0.7), (2830.0, 2440.0, 0.35)] {
        let c = ctl(move |t| fo + (fa - fo) * v(t));
        let b = (raw.clone() | c | wrap(dc(6.0))) >> wrap(bandpass());
        let b = b * g;
        form = Some(match form {
            None => b,
            Some(s) => s + b,
        });
    }
    let mid = (form.unwrap() * 2.2 + raw * 0.25) >> wrap(shape(Tanh(1.5)));
    let sub = wrap(dc(f0 * 0.5) >> sine()) * 0.5;
    let amp = ctl(ahr(0.006, 1.5, 0.1));
    (panned((mid * 0.7 + sub) * amp, 0.0), 1.6)
}

/// Hoover: octave-stacked pulse waves with fast pulse-width modulation and detune, a pitch
/// dive from +7 semitones into C3 at the start and a fall of an octave at the end, through
/// two chorus lines for width.
fn lead_hoover() -> (Net, f64) {
    let base = hz(48.0);
    let bend = move |t: f32| {
        let dive_in = 7.0 * (-t / 0.09).exp();
        let dive_out = if t > 1.9 { -12.0 * ((t - 1.9) / 0.5).min(1.0).powf(1.6) } else { 0.0 };
        2f32.powf((dive_in + dive_out) / 12.0)
    };
    let mut sum: Option<Net> = None;
    for (ratio, cents, g, rate) in [
        (1.0f32, -9.0f32, 0.3f32, 5.3f32),
        (1.0, 9.0, 0.3, 4.1),
        (0.5, 0.0, 0.35, 3.3),
        (2.0, 4.0, 0.12, 6.1),
    ] {
        let f = ctl(move |t| base * ratio * 2f32.powf(cents / 1200.0) * bend(t));
        let w = ctl(move |t| 0.5 + 0.4 * (2.0 * PI * rate * t).sin());
        let v = (f | w) >> wrap(pulse());
        let v = v * g;
        sum = Some(match sum {
            None => v,
            Some(s) => s + v,
        });
    }
    let tone = sum.unwrap() >> wrap(lowpass_hz(4200.0, 0.8));
    let amp = ctl(ahr(0.01, 2.2, 0.25));
    let dry = tone * amp;
    // The dry voice stays in the middle (keeping the sub-octave mono); each side adds its own
    // chorus line.
    let st = (dry.clone() * 0.6 + (dry.clone() >> wrap(chorus(1, 0.012, 0.004, 0.9))))
        | (dry.clone() * 0.6 + (dry >> wrap(chorus(2, 0.017, 0.005, 0.7))));
    (st * 0.6, 2.5)
}

/// Riser: two decorrelated white noises through a band-pass sweeping 400 Hz to 9 kHz, plus
/// three detuned saws rising two octaves from C3 through an opening lowpass; loudness and
/// stereo spread grow over 4 s, then it stops.
fn riser_synth() -> (Net, f64) {
    let len = 4.0f32;
    let prog = move |t: f32| (t / len).clamp(0.0, 1.0);
    let bp = ctl(move |t| 400.0 * (9000.0f32 / 400.0).powf(prog(t).powf(1.4)));
    let nl = (wrap(noise().seed(11)) | bp.clone() | wrap(dc(1.8))) >> wrap(bandpass());
    let nr = (wrap(noise().seed(23)) | bp | wrap(dc(1.8))) >> wrap(bandpass());
    let noise_st = (nl | nr) * 0.9;
    let mut saws: Option<Net> = None;
    for (cents, side) in [(-14.0f32, -1.0f32), (0.0, 0.0), (14.0, 1.0)] {
        let f = ctl(move |t| hz(48.0) * 2f32.powf(2.0 * prog(t).powf(1.7) + cents / 1200.0));
        let p = ctl(move |t| side * (0.15 + 0.75 * prog(t)));
        let lp = ctl(move |t| 300.0 * (10000.0f32 / 300.0).powf(prog(t)));
        let v = ((f >> wrap(saw())) | lp | wrap(dc(0.9))) >> wrap(lowpass());
        let v = (v * 0.3 | p) >> wrap(panner());
        saws = Some(match saws {
            None => v,
            Some(s) => s + v,
        });
    }
    let gain = ctl(move |t| {
        let g = 10f32.powf((-30.0 + 30.0 * prog(t).powf(0.8)) / 20.0);
        g * if t < len { 1.0 } else { (1.0 - (t - len) / 0.01).max(0.0) }
    });
    ((noise_st + saws.unwrap()) * (gain.clone() | gain) * 0.6, 4.0)
}

fn patch(id: &str) -> Option<(Net, f64)> {
    Some(match id {
        "lead-supersaw" => lead_supersaw(),
        "bass-808-glide" => bass_808_glide(),
        "pluck-house" => pluck_house(),
        "pad-moving" => pad_moving(),
        "bass-wobble" => bass_wobble(),
        "bass-growl" => bass_growl(),
        "lead-hoover" => lead_hoover(),
        "riser-synth" => riser_synth(),
        _ => return None,
    })
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    if a.len() != 3 {
        eprintln!("usage: synth-bench-render ID OUT.wav");
        std::process::exit(2);
    }
    let Some((mut net, seconds)) = patch(&a[1]) else {
        eprintln!("unknown patch {}", a[1]);
        std::process::exit(2);
    };
    assert_eq!((net.inputs(), net.outputs()), (0, 2), "{}", a[1]);
    let wave = Wave::render(SR, seconds, &mut net);
    for ch in 0..wave.channels() {
        for &s in wave.channel(ch) {
            assert!(s.is_finite(), "{}: non-finite sample", a[1]);
        }
    }
    wave.save_wav32(&a[2]).expect("write wav");
}
