#!/usr/bin/env python3
"""boAt Nirvana Sound Control — Linux Edition
Tuned for MSI Sword 15 A12UC (Realtek ALC256 / Intel Alder Lake)
"""

import gi, subprocess, json, os, math

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gdk, Pango

PRESETS_DIR = os.path.expanduser("~/.config/easyeffects/output")
CONFIG_PATH = os.path.expanduser("~/.config/boat-sound-control.json")

EQ_PRESETS = {
    "Signature": "BoAt_Nirvana_Signature",
    "Balanced": "BoAt_Nirvana_Balanced",
    "Bass Boost": "BoAt_Nirvana_BassBoost",
    "Flat": None,
}

SCENE_PRESETS = {
    "Music": {"preset": "Signature", "vol": 80},
    "Movie": {"preset": "Bass Boost", "vol": 90},
    "Gaming": {"preset": "Signature", "vol": 85},
    "Podcast": {"preset": "Balanced", "vol": 70},
    "Night Mode": {"preset": "Balanced", "vol": 40},
}

FREQ_LABELS = ["32", "64", "125", "250", "500", "1K", "2K", "4K", "8K", "16K"]
FREQ_HZ = [32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]

CSS = """
.accent-btn { background: #e63946; color: white; }
.accent-btn:hover { background: #c1121f; }
.eq-gain-label { font-size: 10px; opacity: 0.7; }
.scene-btn { padding: 12px 8px; }
.scene-active { background: alpha(@accent_color, 0.3); }
.device-label { font-size: 11px; opacity: 0.6; }
.vu-bar { min-height: 6px; border-radius: 3px; }
.output-card { padding: 12px; border-radius: 12px; background: alpha(@card_bg_color, 0.5); }
"""


def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


def get_volume():
    out = run("wpctl get-volume @DEFAULT_AUDIO_SINK@")
    if not out:
        return 75, False
    parts = out.split()
    vol = float(parts[1]) * 100
    muted = "[MUTED]" in out
    return vol, muted


def set_volume(vol):
    run(f"wpctl set-volume @DEFAULT_AUDIO_SINK@ {vol / 100:.2f}")


def toggle_mute():
    run("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle")


def get_mic_volume():
    out = run("wpctl get-volume @DEFAULT_AUDIO_SOURCE@")
    if not out:
        return 50, False
    parts = out.split()
    vol = float(parts[1]) * 100
    muted = "[MUTED]" in out
    return vol, muted


def set_mic_volume(vol):
    run(f"wpctl set-volume @DEFAULT_AUDIO_SOURCE@ {vol / 100:.2f}")


def toggle_mic_mute():
    run("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle")


def get_output_devices():
    out = run("pactl list sinks short")
    devices = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            sink_id = parts[0]
            name = parts[1]
            desc = run(f"pactl list sinks | grep -A2 'Name: {name}' | grep Description | head -1")
            desc = desc.replace("Description: ", "").strip() if desc else name
            short = desc.replace("Alder Lake PCH-P High Definition Audio Controller ", "")
            devices.append({"id": sink_id, "name": name, "desc": short})
    return devices


def set_default_sink(name):
    run(f"wpctl set-default $(pw-cli ls Node | grep -B5 '{name}' | grep 'id ' | head -1 | awk '{{print $2}}' | tr -d ',')")


def load_preset_eq(preset_name):
    if not preset_name:
        return [0.0] * 10
    path = os.path.join(PRESETS_DIR, f"{preset_name}.json")
    if not os.path.exists(path):
        return [0.0] * 10
    with open(path) as f:
        data = json.load(f)
    eq = data.get("output", {}).get("equalizer#0", {})
    gains = []
    for i in range(10):
        band = eq.get(f"band{i}", {})
        gains.append(band.get("gain", 0.0))
    return gains


def save_preset_eq(preset_name, gains):
    if not preset_name:
        return
    path = os.path.join(PRESETS_DIR, f"{preset_name}.json")
    if not os.path.exists(path):
        return
    with open(path) as f:
        data = json.load(f)
    eq = data.get("output", {}).get("equalizer#0", {})
    for i, g in enumerate(gains):
        if f"band{i}" in eq:
            eq[f"band{i}"]["gain"] = g
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


def apply_easyeffects_preset(preset_name):
    if preset_name:
        run(f"busctl --user call com.github.wwmm.easyeffects "
            f"/com/github/wwmm/easyeffects com.github.wwmm.easyeffects "
            f"LoadPresetToOutput s {preset_name}")


def playerctl(cmd):
    return run(f"playerctl {cmd}")


def get_peak_level():
    out = run("pactl list sinks | grep -A15 'Headphones' | grep 'Volume:' | head -1")
    if "%" in out:
        try:
            pct = int(out.split("%")[0].split()[-1])
            return pct / 100.0
        except Exception:
            pass
    return 0.0


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


class BoatSoundControl(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.boat.soundcontrol")
        self.connect("activate", self.on_activate)
        self.current_preset = "Signature"
        self.current_scene = None
        self.eq_sliders = []
        self.eq_gain_labels = []
        self.updating = False
        self.config = load_config()

    def on_activate(self, app):
        # Load CSS
        css_provider = Gtk.CssProvider()
        css_provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        win = Adw.ApplicationWindow(application=app)
        win.set_title("boAt Sound Control")
        win.set_default_size(560, 820)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        win.set_content(main_box)

        # Header
        header = Adw.HeaderBar()
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        title_lbl = Gtk.Label(label="boAt Sound Control")
        title_lbl.add_css_class("title-4")
        subtitle_lbl = Gtk.Label(label="MSI Sword 15 \u2022 Realtek ALC256")
        subtitle_lbl.add_css_class("device-label")
        title_box.append(title_lbl)
        title_box.append(subtitle_lbl)
        header.set_title_widget(title_box)

        # Settings button in header
        settings_btn = Gtk.MenuButton()
        settings_btn.set_icon_name("open-menu-symbolic")
        menu = Gtk.PopoverMenu()
        menu_model = GLib.Menu()
        menu_model.append("Open EasyEffects", "app.open-easyeffects")
        menu_model.append("Open PulseAudio Volume Control", "app.open-pavucontrol")
        menu_model.append("Autostart on Boot", "app.toggle-autostart")
        menu.set_menu_model(menu_model)
        settings_btn.set_popover(menu)
        header.pack_end(settings_btn)

        # Actions
        action_ee = GLib.SimpleAction.new("open-easyeffects", None)
        action_ee.connect("activate", lambda *_: run("easyeffects &"))
        self.add_action(action_ee)

        action_pv = GLib.SimpleAction.new("open-pavucontrol", None)
        action_pv.connect("activate", lambda *_: run("pavucontrol &"))
        self.add_action(action_pv)

        action_auto = GLib.SimpleAction.new("toggle-autostart", None)
        action_auto.connect("activate", self.on_toggle_autostart)
        self.add_action(action_auto)

        main_box.append(header)

        # Use a ViewStack for tabs
        stack = Adw.ViewStack()
        switcher = Adw.ViewSwitcherBar()
        switcher.set_stack(stack)
        switcher.set_reveal(True)

        # --- Page 1: Main Controls ---
        page1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scroll1 = Gtk.ScrolledWindow(vexpand=True)
        content1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        content1.set_margin_top(16)
        content1.set_margin_bottom(16)
        content1.set_margin_start(16)
        content1.set_margin_end(16)
        scroll1.set_child(content1)
        page1.append(scroll1)
        stack.add_titled_with_icon(page1, "main", "Controls", "audio-volume-high-symbolic")

        # Output device selector
        content1.append(self._section_label("Output Device"))
        self.device_combo = Gtk.DropDown()
        devices = get_output_devices()
        self.devices = devices
        device_names = [d["desc"] for d in devices]
        self.device_combo.set_model(Gtk.StringList.new(device_names))
        # Select current default
        for i, d in enumerate(devices):
            if "Headphones" in d["desc"]:
                self.device_combo.set_selected(i)
                break
        self.device_combo.connect("notify::selected", self.on_device_change)
        content1.append(self.device_combo)

        # Volume
        content1.append(self._section_label("Volume"))
        vol, muted = get_volume()

        vol_box = Gtk.Box(spacing=10)
        content1.append(vol_box)

        self.mute_btn = Gtk.Button(icon_name="audio-volume-muted-symbolic" if muted else "audio-volume-high-symbolic")
        self.mute_btn.connect("clicked", self.on_mute)
        self.mute_btn.set_tooltip_text("Toggle Mute")
        vol_box.append(self.mute_btn)

        self.vol_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        self.vol_scale.set_value(vol)
        self.vol_scale.set_hexpand(True)
        self.vol_scale.add_mark(100, Gtk.PositionType.BOTTOM, "100%")
        self.vol_scale.connect("value-changed", self.on_vol_change)
        vol_box.append(self.vol_scale)

        self.vol_label = Gtk.Label(label=f"{int(vol)}%")
        self.vol_label.set_size_request(50, -1)
        vol_box.append(self.vol_label)

        # VU meter
        self.vu_bar = Gtk.LevelBar()
        self.vu_bar.set_min_value(0)
        self.vu_bar.set_max_value(1.0)
        self.vu_bar.set_value(0)
        self.vu_bar.add_css_class("vu-bar")
        content1.append(self.vu_bar)

        # Microphone
        content1.append(self._section_label("Microphone"))
        mic_vol, mic_muted = get_mic_volume()
        mic_box = Gtk.Box(spacing=10)
        content1.append(mic_box)

        self.mic_mute_btn = Gtk.Button(icon_name="microphone-disabled-symbolic" if mic_muted else "audio-input-microphone-symbolic")
        self.mic_mute_btn.connect("clicked", self.on_mic_mute)
        self.mic_mute_btn.set_tooltip_text("Toggle Mic Mute")
        mic_box.append(self.mic_mute_btn)

        self.mic_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.mic_scale.set_value(mic_vol)
        self.mic_scale.set_hexpand(True)
        self.mic_scale.connect("value-changed", self.on_mic_vol_change)
        mic_box.append(self.mic_scale)

        self.mic_label = Gtk.Label(label=f"{int(mic_vol)}%")
        self.mic_label.set_size_request(50, -1)
        mic_box.append(self.mic_label)

        # Scene presets
        content1.append(self._section_label("Scene"))
        scene_box = Gtk.Box(spacing=6, homogeneous=True)
        content1.append(scene_box)
        self.scene_buttons = {}
        for scene_name in SCENE_PRESETS:
            icons = {"Music": "\u266b", "Movie": "\u25b6", "Gaming": "\u265f", "Podcast": "\u265e", "Night Mode": "\u263e"}
            btn = Gtk.ToggleButton(label=f"{icons.get(scene_name, '')} {scene_name}")
            btn.add_css_class("scene-btn")
            btn.connect("toggled", self.on_scene_toggle, scene_name)
            scene_box.append(btn)
            self.scene_buttons[scene_name] = btn

        # Media controls
        content1.append(self._section_label("Now Playing"))

        self.now_playing = Gtk.Label(label="Nothing playing")
        self.now_playing.set_ellipsize(Pango.EllipsizeMode.END)
        self.now_playing.set_xalign(0)
        content1.append(self.now_playing)

        media_box = Gtk.Box(spacing=10)
        media_box.set_halign(Gtk.Align.CENTER)
        media_box.set_margin_top(4)
        content1.append(media_box)

        for icon, cmd in [("media-skip-backward-symbolic", "previous"),
                          ("media-playback-start-symbolic", "play-pause"),
                          ("media-skip-forward-symbolic", "next")]:
            btn = Gtk.Button(icon_name=icon)
            btn.connect("clicked", self.on_media, cmd)
            btn.set_size_request(60, -1)
            media_box.append(btn)

        # --- Page 2: Equalizer ---
        page2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scroll2 = Gtk.ScrolledWindow(vexpand=True)
        content2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        content2.set_margin_top(16)
        content2.set_margin_bottom(16)
        content2.set_margin_start(16)
        content2.set_margin_end(16)
        scroll2.set_child(content2)
        page2.append(scroll2)
        stack.add_titled_with_icon(page2, "eq", "Equalizer", "multimedia-equalizer-symbolic")

        # Sound mode buttons
        content2.append(self._section_label("Sound Mode"))
        preset_box = Gtk.Box(spacing=8, homogeneous=True)
        content2.append(preset_box)

        self.preset_buttons = {}
        for name in EQ_PRESETS:
            btn = Gtk.ToggleButton(label=name)
            btn.connect("toggled", self.on_preset_toggle, name)
            if name == self.current_preset:
                btn.set_active(True)
            preset_box.append(btn)
            self.preset_buttons[name] = btn

        # EQ sliders
        content2.append(self._section_label("10-Band Equalizer"))

        eq_frame = Gtk.Frame()
        eq_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        eq_inner.set_margin_top(12)
        eq_inner.set_margin_bottom(8)
        eq_inner.set_margin_start(8)
        eq_inner.set_margin_end(8)
        eq_frame.set_child(eq_inner)
        content2.append(eq_frame)

        # +12 / 0 / -12 guides
        guide_box = Gtk.Box(spacing=6, homogeneous=True)
        for text in ["+12 dB", "", "", "", "", "0 dB", "", "", "", "-12 dB"]:
            l = Gtk.Label(label=text)
            l.add_css_class("eq-gain-label")
            guide_box.append(l)
        eq_inner.append(guide_box)

        eq_box = Gtk.Box(spacing=4, homogeneous=True)
        eq_box.set_size_request(-1, 250)
        eq_inner.append(eq_box)

        gains = load_preset_eq(EQ_PRESETS.get(self.current_preset))
        self.eq_sliders = []
        self.eq_gain_labels = []

        for i in range(10):
            band_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            band_box.set_hexpand(True)

            gain_lbl = Gtk.Label(label=f"{gains[i]:+.1f}")
            gain_lbl.add_css_class("eq-gain-label")
            band_box.append(gain_lbl)
            self.eq_gain_labels.append(gain_lbl)

            slider = Gtk.Scale.new_with_range(Gtk.Orientation.VERTICAL, -12, 12, 0.5)
            slider.set_inverted(True)
            slider.set_draw_value(False)
            slider.set_value(gains[i])
            slider.set_vexpand(True)
            slider.connect("value-changed", self.on_eq_change, i)
            band_box.append(slider)
            self.eq_sliders.append(slider)

            freq_lbl = Gtk.Label(label=FREQ_LABELS[i])
            freq_lbl.add_css_class("caption")
            band_box.append(freq_lbl)

            eq_box.append(band_box)

        # EQ action buttons
        eq_btn_box = Gtk.Box(spacing=8)
        eq_btn_box.set_halign(Gtk.Align.CENTER)
        eq_btn_box.set_margin_top(8)
        content2.append(eq_btn_box)

        reset_btn = Gtk.Button(label="Reset")
        reset_btn.connect("clicked", self.on_eq_reset)
        eq_btn_box.append(reset_btn)

        apply_btn = Gtk.Button(label="Apply to EasyEffects")
        apply_btn.add_css_class("accent-btn")
        apply_btn.connect("clicked", self.on_eq_save)
        eq_btn_box.append(apply_btn)

        # Preamp
        content2.append(self._section_label("Preamp Gain"))
        self.preamp_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -6, 6, 0.5)
        self.preamp_scale.set_value(0)
        self.preamp_scale.add_mark(0, Gtk.PositionType.BOTTOM, "0 dB")
        content2.append(self.preamp_scale)

        # --- Page 3: Hardware Info ---
        page3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scroll3 = Gtk.ScrolledWindow(vexpand=True)
        content3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content3.set_margin_top(16)
        content3.set_margin_bottom(16)
        content3.set_margin_start(16)
        content3.set_margin_end(16)
        scroll3.set_child(content3)
        page3.append(scroll3)
        stack.add_titled_with_icon(page3, "info", "Hardware", "computer-symbolic")

        hw_info = [
            ("Laptop", "MSI Sword 15 A12UC"),
            ("Board", "MS-1584"),
            ("Audio Codec", "Realtek ALC256"),
            ("Audio Controller", "Intel Alder Lake PCH-P HD Audio"),
            ("Audio Server", run("pipewire --version") or "PipeWire"),
            ("Session Manager", "WirePlumber"),
            ("Sample Rate", "48000 Hz"),
            ("Bit Depth", "32-bit"),
        ]

        for label, value in hw_info:
            row = Gtk.Box(spacing=8)
            k = Gtk.Label(label=f"{label}:", xalign=0)
            k.set_size_request(140, -1)
            k.add_css_class("dim-label")
            v = Gtk.Label(label=value, xalign=0)
            v.set_hexpand(True)
            v.set_selectable(True)
            row.append(k)
            row.append(v)
            content3.append(row)

        # Quick actions on hw page
        content3.append(self._section_label("Quick Actions"))

        qa_box = Gtk.Box(spacing=8)
        content3.append(qa_box)

        for label, cmd in [("Restart PipeWire", "systemctl --user restart pipewire pipewire-pulse wireplumber"),
                           ("Restart EasyEffects", "killall easyeffects; easyeffects &")]:
            btn = Gtk.Button(label=label)
            btn.connect("clicked", lambda b, c=cmd: run(c))
            qa_box.append(btn)

        # Assemble
        main_box.append(stack)
        main_box.append(switcher)

        # Periodic updates
        GLib.timeout_add_seconds(2, self.update_now_playing)
        GLib.timeout_add(500, self.update_vu)
        self.update_now_playing()

        win.present()

    def _section_label(self, text):
        lbl = Gtk.Label(label=text, xalign=0)
        lbl.add_css_class("title-3")
        lbl.set_margin_top(4)
        return lbl

    def on_device_change(self, dropdown, _param):
        idx = dropdown.get_selected()
        if idx < len(self.devices):
            set_default_sink(self.devices[idx]["name"])

    def on_vol_change(self, scale):
        vol = scale.get_value()
        self.vol_label.set_label(f"{int(vol)}%")
        set_volume(vol)

    def on_mute(self, btn):
        toggle_mute()
        _, muted = get_volume()
        btn.set_icon_name("audio-volume-muted-symbolic" if muted else "audio-volume-high-symbolic")

    def on_mic_vol_change(self, scale):
        vol = scale.get_value()
        self.mic_label.set_label(f"{int(vol)}%")
        set_mic_volume(vol)

    def on_mic_mute(self, btn):
        toggle_mic_mute()
        _, muted = get_mic_volume()
        btn.set_icon_name("microphone-disabled-symbolic" if muted else "audio-input-microphone-symbolic")

    def on_scene_toggle(self, btn, name):
        if self.updating:
            return
        if not btn.get_active():
            if self.current_scene == name:
                self.current_scene = None
            return
        self.updating = True
        self.current_scene = name
        for n, b in self.scene_buttons.items():
            if n != name:
                b.set_active(False)

        scene = SCENE_PRESETS[name]
        # Apply volume
        self.vol_scale.set_value(scene["vol"])
        # Apply preset
        preset_name = scene["preset"]
        for n, b in self.preset_buttons.items():
            b.set_active(n == preset_name)

        self.updating = False

    def on_preset_toggle(self, btn, name):
        if self.updating:
            return
        if not btn.get_active():
            return
        self.updating = True
        self.current_preset = name
        for n, b in self.preset_buttons.items():
            if n != name:
                b.set_active(False)

        preset_file = EQ_PRESETS.get(name)
        gains = load_preset_eq(preset_file)

        for i, s in enumerate(self.eq_sliders):
            s.set_value(gains[i])
        self.updating = False

    def on_eq_change(self, scale, band_idx):
        val = scale.get_value()
        if band_idx < len(self.eq_gain_labels):
            self.eq_gain_labels[band_idx].set_label(f"{val:+.1f}")

    def on_eq_reset(self, btn):
        for i, s in enumerate(self.eq_sliders):
            s.set_value(0.0)

    def on_eq_save(self, btn):
        preset_file = EQ_PRESETS.get(self.current_preset)
        if not preset_file:
            return
        gains = [s.get_value() for s in self.eq_sliders]
        save_preset_eq(preset_file, gains)
        apply_easyeffects_preset(preset_file)
        # Visual feedback
        btn.set_label("Applied!")
        GLib.timeout_add(1500, lambda: btn.set_label("Apply to EasyEffects") or False)

    def on_media(self, btn, cmd):
        playerctl(cmd)
        GLib.timeout_add(500, self.update_now_playing)

    def update_now_playing(self):
        title = playerctl("metadata title")
        artist = playerctl("metadata artist")
        if title:
            text = f"{artist} \u2014 {title}" if artist else title
            self.now_playing.set_label(text)
        else:
            self.now_playing.set_label("Nothing playing")
        return True

    def update_vu(self):
        level = get_peak_level()
        self.vu_bar.set_value(min(level, 1.0))
        return True

    def on_toggle_autostart(self, *args):
        autostart_dir = os.path.expanduser("~/.config/autostart")
        autostart_file = os.path.join(autostart_dir, "boat-sound-control.desktop")
        if os.path.exists(autostart_file):
            os.remove(autostart_file)
        else:
            os.makedirs(autostart_dir, exist_ok=True)
            with open(autostart_file, "w") as f:
                f.write("[Desktop Entry]\n"
                        "Name=boAt Sound Control\n"
                        "Exec=/home/og/.local/bin/boat-sound-control\n"
                        "Type=Application\n"
                        "X-GNOME-Autostart-enabled=true\n")


if __name__ == "__main__":
    app = BoatSoundControl()
    app.run(None)
