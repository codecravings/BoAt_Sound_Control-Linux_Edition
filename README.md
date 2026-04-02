# boAt Sound Control — Linux Edition

A GTK4/Libadwaita sound control app for Linux, inspired by the boAt Hearables app. Tuned for MSI Sword 15 (Realtek ALC256 / Intel Alder Lake) but works on any PipeWire-based Linux system.

## Features

- **Volume & Mic Control** — sliders, mute toggles, VU meter
- **Output Device Selector** — switch between headphones, HDMI, speakers
- **Sound Modes** — Signature (V-shaped), Balanced (vocal clarity), Bass Boost, Flat
- **Scene Presets** — Music, Movie, Gaming, Podcast, Night Mode — auto-sets volume + EQ
- **10-Band Parametric EQ** — 32Hz to 16KHz with per-band gain labels
- **Media Controls** — play/pause, next, previous with Now Playing display
- **Hardware Info** — shows audio codec, sample rate, bit depth
- **Quick Actions** — restart PipeWire, restart EasyEffects
- **Autostart on Boot** — toggle from the menu
- **EasyEffects Integration** — applies EQ presets directly to EasyEffects

## Screenshots

*Coming soon*

## Dependencies

- Python 3
- GTK 4 / Libadwaita
- PipeWire + WirePlumber
- EasyEffects
- playerctl (for media controls)
- LSP Plugins LV2 (for EQ)

### Install on Arch Linux

```bash
sudo pacman -S easyeffects playerctl lsp-plugins-lv2
```

## Installation

1. Clone this repo:
```bash
git clone https://github.com/codecravings/repo_noncpys.git
cd repo_noncpys
```

2. Copy the app:
```bash
cp boat-sound-control.py ~/.local/bin/boat-sound-control
chmod +x ~/.local/bin/boat-sound-control
```

3. Copy EQ presets:
```bash
mkdir -p ~/.config/easyeffects/output/
cp BoAt_Nirvana_*.json ~/.config/easyeffects/output/
```

4. Copy desktop entry (optional — adds to app launcher):
```bash
cp boat-sound-control.desktop ~/.local/share/applications/
```

5. Run:
```bash
boat-sound-control
```

## EQ Presets

| Preset | Style | Description |
|--------|-------|-------------|
| Signature | V-shaped | Heavy bass + bright treble, the classic boAt sound |
| Balanced | Flat/Vocal | Boosted mids for podcasts, calls, vocals |
| Bass Boost | Bass heavy | Maximum sub-bass for EDM/hip-hop |

## License

MIT
