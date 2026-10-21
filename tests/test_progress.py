# © 2026 Mike Pollow, Digitalroots. Alle Rechte vorbehalten.
from __future__ import annotations

import sys
import threading

import pytest

from kira import progress as prog


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_bar_scale_keeps_oversize_totals_in_int32_range():
    int32_max = 2 ** 31 - 1
    completed = 5 * 1024 ** 3
    total = 17 * 1024 ** 3 + 432
    maximum, value = prog.bar_scale(completed, total)
    assert 0 < maximum <= int32_max
    assert abs(value / maximum - completed / total) < 0.01


def test_bar_scale_zero_total_is_indeterminate():
    assert prog.bar_scale(0, 0) == (0, 0)


def test_bar_scale_clamps_completed_over_total():
    assert prog.bar_scale(200, 100) == (prog.SCALE, prog.SCALE)


def test_bar_scale_is_never_full_before_the_last_byte():
    assert prog.bar_scale(9_999_999, 10_000_000) == (prog.SCALE, prog.SCALE - 1)


@pytest.mark.parametrize("done,total,expected", [
    (1_600_000_000, 4_300_000_000, "1,6 von 4,3 GB"),
    (0, 17_990_000_000, "0,0 von 18,0 GB"),
    (327_155_712, 1_584_489_392, "0,3 von 1,6 GB"),
    (450_000_000, 980_000_000, "450 von 980 MB"),
    (12_500_000, 48_000_000, "12,5 von 48,0 MB"),
    (1_200, 2_394, "1,2 von 2,4 KB"),
    (5_000, 4_000, "4,0 von 4,0 KB"),
])
def test_size_text_uses_german_decimal_comma(done, total, expected):
    assert prog.size_text(done, total) == expected


@pytest.mark.parametrize("rate,expected", [
    (9_900_000, "9,9 MB/s"),
    (112_400_000, "112 MB/s"),
    (650_000, "650 KB/s"),
])
def test_rate_text(rate, expected):
    assert prog.rate_text(rate) == expected


@pytest.mark.parametrize("seconds,expected", [
    (12, "noch unter einer Minute"),
    (59, "noch unter einer Minute"),
    (75, "noch etwa 1 Minute"),
    (240, "noch etwa 4 Minuten"),
    (99 * 60, "noch etwa 99 Minuten"),
    (3 * 3600, "noch etwa 3 Stunden"),
])
def test_eta_text(seconds, expected):
    assert prog.eta_text(seconds) == expected


def test_time_text_counts_minutes_and_hours():
    assert prog.time_text(750, 3480) == "12:30 von 58:00"
    assert prog.time_text(10, 3723) == "0:10 von 1:02:03"


def test_percent_rounds_down_so_100_means_done():
    assert prog.percent(999, 1000) == 99
    assert prog.percent(1000, 1000) == 100
    assert prog.percent(5, 0) == 0


def test_meter_reports_no_rate_until_enough_samples():
    clock = Clock()
    meter = prog.RateMeter(clock=clock)
    meter.add(0)
    for second in range(1, 5):
        clock.now += 1
        meter.add(second * 10_000_000)
        assert meter.rate() is None
    clock.now += 1
    meter.add(50_000_000)
    assert meter.rate() == pytest.approx(10_000_000)


def test_meter_ignores_a_resume_jump_at_the_start():
    clock = Clock()
    meter = prog.RateMeter(clock=clock)
    meter.add(6_000_000_000)
    for second in range(1, 9):
        clock.now += 1
        meter.add(6_000_000_000 + second * 5_000_000)
    assert meter.rate() == pytest.approx(5_000_000)


def test_meter_uses_the_last_window_only():
    clock = Clock()
    meter = prog.RateMeter(clock=clock)
    done = 0
    for _ in range(30):
        clock.now += 1
        done += 1_000_000
        meter.add(done)
    for _ in range(12):
        clock.now += 1
        done += 20_000_000
        meter.add(done)
    assert meter.rate() == pytest.approx(20_000_000)


def test_meter_keeps_two_samples_when_updates_are_sparse():
    clock = Clock()
    meter = prog.RateMeter(clock=clock)
    meter.add(0)
    for step in range(1, 4):
        clock.now += 15
        meter.add(step * 10_000_000)
    assert meter.rate() == pytest.approx(10_000_000 / 15)


def test_meter_reports_a_stall_and_recovers():
    clock = Clock()
    meter = prog.RateMeter(clock=clock)
    for second in range(8):
        clock.now += 1
        meter.add(second * 1_000_000)
    clock.now += 14
    assert not meter.stalled()
    clock.now += 2
    assert meter.stalled()
    assert meter.rate() is None
    meter.add(9_000_000)
    assert not meter.stalled()


def test_meter_without_stall_limit_never_stalls():
    clock = Clock()
    meter = prog.RateMeter(clock=clock, stall=None)
    meter.add(1)
    clock.now += 3600
    assert not meter.stalled()


def test_describe_starts_then_shows_rate_and_time_left():
    clock = Clock()
    meter = prog.RateMeter(clock=clock)
    meter.add(0)
    assert prog.describe(0, 4_300_000_000, meter) == "4,3 GB · läuft seit 0:00"
    done = 0
    for _ in range(8):
        clock.now += 1
        done += 10_000_000
        meter.add(done)
    text = prog.describe(done, 4_300_000_000, meter)
    assert text == "0,1 von 4,3 GB · 1 % · 10,0 MB/s · noch etwa 7 Minuten"


def test_describe_shows_the_running_time_when_no_bytes_arrive():
    clock = Clock()
    meter = prog.RateMeter(clock=clock)
    meter.add(100_000_000)
    clock.now += 25
    assert prog.describe(100_000_000, 400_000_000, meter) == "100 von 400 MB · 25 % · läuft seit 0:25"


def test_describe_for_audio_time_omits_the_rate():
    clock = Clock()
    meter = prog.RateMeter(clock=clock, stall=None)
    for second in range(9):
        meter.add(second * 30.0)
        clock.now += 1
    text = prog.describe(240.0, 3480.0, meter, prog.time_text, with_rate=False)
    assert text == "4:00 von 58:00 · 6 % · noch etwa 2 Minuten"


def test_pull_tracker_sums_layers_by_digest():
    tracker = prog.PullTracker()
    assert not tracker.started
    assert tracker.feed("pulling manifest", 0, 0) == (0, 0)
    assert tracker.feed("sha256:a", 500, 1000) == (500, 1000)
    assert tracker.feed("sha256:b", 0, 4000) == (500, 5000)
    assert tracker.feed("sha256:a", 1000, 1000) == (1000, 5000)
    assert tracker.feed("sha256:b", 9000, 4000) == (5000, 5000)
    assert tracker.started


@pytest.mark.parametrize("status,started,expected", [
    ("pulling manifest", False, prog.STARTING),
    ("verifying sha256 digest", True, "Prüfsumme wird geprüft …"),
    ("writing manifest", True, "Modell wird eingetragen …"),
    ("removing any unused layers", True, "wird aufgeräumt …"),
    ("success", True, prog.FINISHING),
    ("something new", False, prog.PREPARING),
])
def test_pull_phase_speaks_german(status, started, expected):
    assert prog.pull_phase(status, started) == expected


def test_pull_fields_reads_dicts_and_objects():
    class Event:
        status = "pulling abc"
        digest = "sha256:abc"
        completed = None
        total = 3_000_000_000

    assert prog.pull_fields({"status": "x", "total": 5}) == ("x", "", 0, 5)
    assert prog.pull_fields(Event()) == ("pulling abc", "sha256:abc", 0, 3_000_000_000)


def test_throttle_lets_through_first_forced_and_late_calls():
    clock = Clock()
    throttle = prog.Throttle(interval=0.2, clock=clock)
    assert throttle.due()
    assert not throttle.due()
    assert throttle.due(force=True)
    clock.now += 0.25
    assert throttle.due()


def _hub_like_snapshot(cls, sizes, chunks=4):
    from tqdm.contrib.concurrent import thread_map

    bar = cls(desc="Downloading (incomplete total...)", total=0, initial=0, unit="B", unit_scale=True)

    def fetch(size):
        bar.total += size
        bar.refresh()
        step = size // chunks
        for _ in range(chunks):
            bar.update(step)
        bar.update(size - step * chunks)

    thread_map(fetch, sizes, desc=f"Fetching {len(sizes)} files", tqdm_class=cls)
    bar.set_description("Download complete")
    bar.close()


def test_byte_progress_counts_bytes_across_files_and_ignores_the_file_bar(monkeypatch):
    seen = []
    lock = threading.Lock()

    def report(done, total):
        with lock:
            seen.append((done, total))

    monkeypatch.setattr(sys, "stderr", None)
    cls = prog.byte_progress_class(report)
    _hub_like_snapshot(cls, [3_087_284_237, 2_394, 2_480_617, 1_068_114, 340])
    total = 3_087_284_237 + 2_394 + 2_480_617 + 1_068_114 + 340
    assert max(done for done, _ in seen) == total
    assert seen[-1] == (total, total)
    assert all(done <= size for done, size in seen)


def test_byte_progress_works_with_the_hub_progress_factory():
    from huggingface_hub.utils.tqdm import _create_progress_bar

    seen = []
    cls = prog.byte_progress_class(lambda done, total: seen.append((done, total)))
    bar = _create_progress_bar(cls=cls, log_level=30, name="huggingface_hub.snapshot_download",
                               desc="Downloading", total=0, initial=0, unit="B", unit_scale=True)
    bar.total += 1000
    bar.refresh()
    bar.update(400)
    assert seen[-1] == (400, 1000)


def test_byte_progress_raises_to_cancel_a_download():
    cancel = threading.Event()

    def report(done, total):
        if cancel.is_set():
            raise prog.Cancelled()

    cls = prog.byte_progress_class(report)
    bar = cls(total=100, unit="B")
    bar.update(10)
    cancel.set()
    with pytest.raises(prog.Cancelled):
        bar.update(10)


def test_total_text_names_only_the_size():
    assert prog.total_text(3_090_835_702) == "3,1 GB"
    assert prog.total_text(48_000_000) == "48,0 MB"


def test_no_measurable_bytes_show_size_and_runtime_until_bytes_arrive():
    clock = Clock()
    meter = prog.RateMeter(clock=clock)
    total = 3_090_835_702
    meter.add(3_550_885)
    clock.now += 135
    assert prog.unmeasured(3_550_885, total, meter)
    assert prog.describe(3_550_885, total, meter) == "3,1 GB · läuft seit 2:15"
    meter.add(256_000_000)
    assert not prog.unmeasured(256_000_000, total, meter)
    assert prog.describe(256_000_000, total, meter) == "0,3 von 3,1 GB · 8 % · läuft seit 2:15"
    clock.now += 60
    meter.add(768_000_000)
    assert prog.describe(768_000_000, total, meter) == "0,8 von 3,1 GB · 24 % · 8,5 MB/s · noch etwa 5 Minuten"


def test_starting_text_only_in_the_first_seconds():
    clock = Clock()
    meter = prog.RateMeter(clock=clock)
    meter.add(500_000_000)
    assert prog.describe(500_000_000, 1_000_000_000, meter).endswith(prog.STARTING)
    clock.now += 6
    assert prog.describe(500_000_000, 1_000_000_000, meter).endswith("läuft seit 0:06")


def test_without_total_only_a_zero_start_still_counts_up():
    clock = Clock()
    meter = prog.RateMeter(clock=clock, stall=None)
    meter.add(0.0)
    assert prog.describe(0.0, 3480.0, meter, prog.time_text, with_rate=False, total_only=None) == (
        "0:00 von 58:00 · 0 % · startet …"
    )


def test_pull_tracker_counts_every_layer_complete_at_the_end():
    tracker = prog.PullTracker()
    tracker.feed("sha256:model", 90_717_875, 91_727_296)
    tracker.feed("sha256:template", 0, 182)
    assert tracker.feed("sha256:config", 488, 488) == (90_718_363, 91_727_966)
    assert tracker.complete() == (91_727_966, 91_727_966)


def test_pull_tracker_takes_the_expected_size_until_the_layers_exceed_it():
    tracker = prog.PullTracker(expected=8_021_618_941)
    assert tracker.feed("pulling manifest", 0, 0) == (0, 0)
    assert tracker.feed("sha256:proj", 175_115_616, 175_115_616) == (175_115_616, 8_021_618_941)
    assert tracker.feed("sha256:model", 0, 9_000_000_000) == (175_115_616, 9_175_115_616)
    assert prog.PullTracker(expected=500).complete() == (500, 500)


@pytest.mark.parametrize("status,final", [
    ("verifying sha256 digest", True),
    ("writing manifest", True),
    ("success", True),
    ("pulling manifest", False),
    ("pulling 0cb0cd0a5c49", False),
    ("removing any unused layers", False),
])
def test_final_status_marks_the_end_of_the_download(status, final):
    assert prog.final_status(status) is final


def test_meter_measures_anew_after_a_stall():
    clock = Clock()
    meter = prog.RateMeter(clock=clock)
    done = 0
    for _ in range(12):
        clock.now += 1
        done += 10_000_000
        meter.add(done)
    assert meter.rate() == pytest.approx(10_000_000)
    clock.now += 120
    done += 100_000
    meter.add(done)
    assert meter.rate() is None
    assert prog.describe(done, 400_000_000, meter) == "120 von 400 MB · 30 % · läuft seit 2:11"
    for _ in range(4):
        clock.now += 1
        done += 8_000_000
        meter.add(done)
    assert meter.rate() == pytest.approx(8_000_000)


def test_meter_measures_anew_when_ollama_repeats_the_same_bytes_while_stalled():
    clock = Clock()
    meter = prog.RateMeter(clock=clock)
    done = 0
    for _ in range(12):
        clock.now += 1
        done += 10_000_000
        meter.add(done)
    for _ in range(60):
        clock.now += 1
        meter.add(done)
    clock.now += 1
    meter.add(done + 100_000)
    assert meter.rate() is None


def test_meter_keeps_averaging_sparse_reports_at_the_same_speed():
    clock = Clock()
    meter = prog.RateMeter(clock=clock)
    meter.add(0)
    for step in range(1, 7):
        clock.now += 27
        meter.add(step * 10_000_000)
        if step >= 2:
            assert meter.rate() == pytest.approx(10_000_000 / 27)
