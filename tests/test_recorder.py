import numpy as np
import pytest

from kira.recorder import Recorder, DeviceUnavailable


def test_recorder_construction():
    r = Recorder()
    assert not r.is_recording


def test_stop_without_start_returns_empty():
    r = Recorder()
    audio = r.stop()
    assert audio.size == 0


def test_set_level_callback_is_stored():
    r = Recorder()
    captured = []
    r.set_level_callback(lambda x: captured.append(x))
    assert r._on_level is not None


def test_default_gain_preserves_samples():
    r = Recorder()
    r._recording = True
    samples = np.array([[0.01], [-0.02], [0.05]], dtype=np.float32)
    r._callback(samples, 3, None, None)
    stored = r._buffer[0]
    np.testing.assert_allclose(stored, samples)


def test_gain_multiplies_samples():
    r = Recorder(input_gain=10.0)
    r._recording = True
    samples = np.array([[0.01], [-0.02], [0.05]], dtype=np.float32)
    r._callback(samples, 3, None, None)
    stored = r._buffer[0]
    np.testing.assert_allclose(stored, samples * 10.0, rtol=1e-5)


def test_gain_clips_when_overshooting():
    r = Recorder(input_gain=100.0)
    r._recording = True
    samples = np.array([[0.02], [-0.05], [0.5]], dtype=np.float32)
    r._callback(samples, 3, None, None)
    stored = r._buffer[0]
    assert stored.max() <= 1.0
    assert stored.min() >= -1.0
    assert stored[0, 0] == np.float32(2.0).clip(-1.0, 1.0)
    assert stored[2, 0] == 1.0


def test_callback_fills_preroll_when_not_recording():
    r = Recorder()
    samples = np.array([[0.1], [0.2], [0.3]], dtype=np.float32)
    r._callback(samples, 3, None, None)
    assert len(r._buffer) == 0
    assert len(r._preroll) == 1
    assert r._preroll_samples == 3


def test_preroll_is_trimmed_to_max_size():
    from kira.recorder import PREROLL_SAMPLES
    r = Recorder()
    chunk = np.zeros((1000, 1), dtype=np.float32)
    total_pushed = 0
    while total_pushed < PREROLL_SAMPLES * 2:
        r._callback(chunk, 1000, None, None)
        total_pushed += 1000
    assert r._preroll_samples <= PREROLL_SAMPLES + 1000
    assert r._preroll_samples >= PREROLL_SAMPLES - 1000


def test_start_prepends_preroll_to_recording_buffer(monkeypatch):
    r = Recorder()
    seed = np.full((100, 1), 0.4, dtype=np.float32)
    r._callback(seed, 100, None, None)
    assert len(r._preroll) == 1

    monkeypatch.setattr("kira.recorder.sd.InputStream", lambda **kw: _NoOpStream())
    r.start()
    assert r._recording is True
    assert len(r._preroll) == 0
    assert len(r._buffer) == 1
    np.testing.assert_allclose(r._buffer[0], seed)


class _NoOpStream:
    active = True
    def start(self): pass
    def stop(self): pass
    def close(self): pass


def test_level_callback_receives_boosted_rms():
    r = Recorder(input_gain=50.0)
    captured: list[float] = []
    r.set_level_callback(lambda x: captured.append(x))
    samples = np.full((100, 1), 0.01, dtype=np.float32)
    r._callback(samples, 100, None, None)
    assert len(captured) == 1
    assert 0.49 < captured[0] < 0.51


def test_prewarm_opens_stream_once(monkeypatch):
    constructed: list[_NoOpStream] = []

    def _factory(**kw):
        s = _NoOpStream()
        constructed.append(s)
        return s

    monkeypatch.setattr("kira.recorder.sd.InputStream", _factory)
    r = Recorder()
    r.prewarm()
    r.prewarm()
    assert len(constructed) == 1
    assert r._stream is constructed[0]


def test_close_clears_stream_reference(monkeypatch):
    monkeypatch.setattr("kira.recorder.sd.InputStream", lambda **kw: _NoOpStream())
    r = Recorder()
    r.prewarm()
    assert r._stream is not None
    r.close()
    assert r._stream is None


def test_start_after_prewarm_does_not_open_second_stream(monkeypatch):
    constructed: list[_NoOpStream] = []
    monkeypatch.setattr(
        "kira.recorder.sd.InputStream",
        lambda **kw: (lambda s: constructed.append(s) or s)(_NoOpStream()),
    )
    r = Recorder()
    r.prewarm()
    r.start()
    assert len(constructed) == 1


def test_constructor_with_missing_device_does_not_raise(monkeypatch):
    fake_devices = [
        {"name": "Realtek HD Audio", "max_input_channels": 2},
        {"name": "Mikrofon (Andere)", "max_input_channels": 1},
    ]
    monkeypatch.setattr("kira.recorder.sd.query_devices", lambda: fake_devices)
    r = Recorder(input_device="USB Headset")
    assert r._device_spec == "USB Headset"
    assert r._input_device is None
    assert r._stream is None


def test_resolve_device_returns_none_on_miss(monkeypatch):
    fake_devices = [{"name": "Realtek HD Audio", "max_input_channels": 2}]
    monkeypatch.setattr("kira.recorder.sd.query_devices", lambda: fake_devices)
    r = Recorder(input_device="USB Headset")
    assert r._resolve_device() is None


def test_resolve_device_logs_available_inputs_on_miss(monkeypatch, caplog):
    import logging
    fake_devices = [
        {"name": "Realtek HD Audio", "max_input_channels": 2},
        {"name": "Output Only", "max_input_channels": 0},
    ]
    monkeypatch.setattr("kira.recorder.sd.query_devices", lambda: fake_devices)
    with caplog.at_level(logging.WARNING, logger="kira.recorder"):
        r = Recorder(input_device="USB Headset")
        r._resolve_device()
    msg = caplog.text
    assert "USB Headset" in msg
    assert "Realtek HD Audio" in msg
    assert "Output Only" not in msg


def test_prewarm_with_missing_device_is_noop(monkeypatch):
    fake_devices = [{"name": "Realtek HD Audio", "max_input_channels": 2}]
    monkeypatch.setattr("kira.recorder.sd.query_devices", lambda: fake_devices)
    constructed: list[_NoOpStream] = []
    monkeypatch.setattr(
        "kira.recorder.sd.InputStream",
        lambda **kw: (lambda s: constructed.append(s) or s)(_NoOpStream()),
    )
    r = Recorder(input_device="USB Headset")
    r.prewarm()
    assert r._stream is None
    assert len(constructed) == 0


def test_prewarm_with_present_device_opens_stream(monkeypatch):
    fake_devices = [
        {"name": "Mikrofon (USB Headset Pro 7.)", "max_input_channels": 1},
    ]
    monkeypatch.setattr("kira.recorder.sd.query_devices", lambda: fake_devices)
    monkeypatch.setattr("kira.recorder.sd.InputStream", lambda **kw: _NoOpStream())
    r = Recorder(input_device="USB Headset")
    r.prewarm()
    assert r._stream is not None
    assert r._input_device == 0


def test_prewarm_with_no_device_spec_uses_system_default(monkeypatch):
    captured: dict = {}

    def _factory(**kw):
        captured.update(kw)
        return _NoOpStream()

    monkeypatch.setattr("kira.recorder.sd.InputStream", _factory)
    r = Recorder()
    r.prewarm()
    assert r._stream is not None
    assert captured["device"] is None


def test_start_with_missing_device_raises_device_unavailable(monkeypatch):
    from kira.recorder import DeviceUnavailable
    fake_devices = [{"name": "Realtek HD Audio", "max_input_channels": 2}]
    monkeypatch.setattr("kira.recorder.sd.query_devices", lambda: fake_devices)
    monkeypatch.setattr("kira.recorder.sd.InputStream", lambda **kw: _NoOpStream())
    r = Recorder(input_device="USB Headset")
    r.prewarm()
    assert r._stream is None
    with pytest.raises(DeviceUnavailable) as exc_info:
        r.start()
    assert "USB Headset" in str(exc_info.value)
    assert r._recording is False


def test_start_resolves_device_after_arrival(monkeypatch):
    state = {"devices": [{"name": "Realtek HD Audio", "max_input_channels": 2}]}
    monkeypatch.setattr("kira.recorder.sd.query_devices", lambda: state["devices"])
    monkeypatch.setattr("kira.recorder.sd.InputStream", lambda **kw: _NoOpStream())
    r = Recorder(input_device="USB Headset")
    r.prewarm()
    assert r._stream is None

    state["devices"] = [
        {"name": "Mikrofon (USB Headset Pro 7.)", "max_input_channels": 1},
    ]
    r.start()
    assert r._stream is not None
    assert r._recording is True
    assert r._input_device == 0


def test_start_does_not_set_recording_when_input_stream_raises(monkeypatch):
    fake_devices = [
        {"name": "Mikrofon (USB Headset Pro 7.)", "max_input_channels": 1},
    ]
    monkeypatch.setattr("kira.recorder.sd.query_devices", lambda: fake_devices)

    def _explode(**kw):
        raise OSError("Device disappeared between resolve and open")

    monkeypatch.setattr("kira.recorder.sd.InputStream", _explode)
    r = Recorder(input_device="USB Headset")
    with pytest.raises(DeviceUnavailable):
        r.start()
    assert r._recording is False
    assert r._stream is None


def test_resolve_device_returns_none_when_query_devices_raises(monkeypatch):
    def _bad_query():
        raise RuntimeError("PortAudio enumeration failed")
    monkeypatch.setattr("kira.recorder.sd.query_devices", _bad_query)
    r = Recorder(input_device="USB Headset")
    assert r._resolve_device() is None


def test_start_raises_device_unavailable_when_query_devices_raises(monkeypatch):
    def _bad_query():
        raise RuntimeError("PortAudio enumeration failed")
    monkeypatch.setattr("kira.recorder.sd.query_devices", _bad_query)
    r = Recorder(input_device="USB Headset")
    with pytest.raises(DeviceUnavailable):
        r.start()
    assert r._recording is False


class _ActiveStream(_NoOpStream):
    active = True


class _DeadStream(_NoOpStream):
    active = False


def test_callback_status_sets_dirty_flag_on_underflow():
    r = Recorder()

    class _Status:
        input_underflow = True
        input_overflow = False
        def __bool__(self): return True

    samples = np.zeros((100, 1), dtype=np.float32)
    r._callback(samples, 100, None, _Status())
    assert r._stream_dirty is True


def test_callback_overflow_does_not_set_dirty():
    r = Recorder()

    class _Status:
        input_underflow = False
        input_overflow = True
        def __bool__(self): return True

    samples = np.zeros((100, 1), dtype=np.float32)
    r._callback(samples, 100, None, _Status())
    assert r._stream_dirty is False


def test_callback_no_status_keeps_clean_flag():
    r = Recorder()
    samples = np.zeros((100, 1), dtype=np.float32)
    r._callback(samples, 100, None, None)
    assert r._stream_dirty is False


def test_is_device_still_present_when_pinned_id_gone(monkeypatch):
    r = Recorder(input_device="USB Headset")
    r._input_device = 1
    monkeypatch.setattr(
        "kira.recorder.sd.query_devices",
        lambda: [{"name": "Realtek", "max_input_channels": 2}],
    )
    assert r._is_device_still_present() is False


def test_is_device_still_present_when_pinned_id_lost_input_channels(monkeypatch):
    r = Recorder(input_device="USB Headset")
    r._input_device = 0
    monkeypatch.setattr(
        "kira.recorder.sd.query_devices",
        lambda: [{"name": "USB Headset", "max_input_channels": 0}],
    )
    assert r._is_device_still_present() is False


def test_is_device_still_present_returns_true_when_present(monkeypatch):
    r = Recorder(input_device="USB Headset")
    r._input_device = 0
    monkeypatch.setattr(
        "kira.recorder.sd.query_devices",
        lambda: [{"name": "USB Headset", "max_input_channels": 1}],
    )
    assert r._is_device_still_present() is True


def test_cycle_stream_closes_when_dirty(monkeypatch):
    monkeypatch.setattr("kira.recorder.sd.InputStream", lambda **kw: _ActiveStream())
    monkeypatch.setattr(
        "kira.recorder.sd.query_devices",
        lambda: [{"name": "USB Headset", "max_input_channels": 1}],
    )
    r = Recorder(input_device="USB Headset")
    r.prewarm()
    assert r._stream is not None
    r._stream_dirty = True
    cycled = r._cycle_stream_if_unhealthy()
    assert cycled is True
    assert r._stream is None
    assert r._input_device is None
    assert r._stream_dirty is False


def test_cycle_stream_closes_when_device_gone(monkeypatch):
    devices = {"current": [{"name": "USB Headset", "max_input_channels": 1}]}
    monkeypatch.setattr("kira.recorder.sd.InputStream", lambda **kw: _ActiveStream())
    monkeypatch.setattr("kira.recorder.sd.query_devices", lambda: devices["current"])
    r = Recorder(input_device="USB Headset")
    r.prewarm()
    assert r._stream is not None
    devices["current"] = []
    cycled = r._cycle_stream_if_unhealthy()
    assert cycled is True
    assert r._stream is None
    assert r._input_device is None


def test_cycle_stream_keeps_healthy_stream(monkeypatch):
    monkeypatch.setattr("kira.recorder.sd.InputStream", lambda **kw: _ActiveStream())
    monkeypatch.setattr(
        "kira.recorder.sd.query_devices",
        lambda: [{"name": "USB Headset", "max_input_channels": 1}],
    )
    r = Recorder(input_device="USB Headset")
    r.prewarm()
    assert r._stream is not None
    cycled = r._cycle_stream_if_unhealthy()
    assert cycled is False
    assert r._stream is not None


def test_start_recovers_after_hot_unplug(monkeypatch):
    streams: list[_ActiveStream] = []
    devices = {"current": [{"name": "USB Headset", "max_input_channels": 1}]}

    def _factory(**kw):
        s = _ActiveStream()
        streams.append(s)
        return s

    monkeypatch.setattr("kira.recorder.sd.InputStream", _factory)
    monkeypatch.setattr("kira.recorder.sd.query_devices", lambda: devices["current"])
    r = Recorder(input_device="USB Headset")
    r.prewarm()
    assert len(streams) == 1
    r._stream_dirty = True
    devices["current"] = [{"name": "USB Headset", "max_input_channels": 1}]
    r.start()
    assert len(streams) == 2
    assert r._stream is streams[1]
    assert r._recording is True


def test_prewarm_swallows_stream_open_failure(monkeypatch):
    def _boom(**kw):
        raise RuntimeError("PortAudioError: device vanished")

    monkeypatch.setattr("kira.recorder.sd.InputStream", _boom)
    r = Recorder()

    r.prewarm()

    assert r._stream is None
    with pytest.raises(DeviceUnavailable):
        r.start()


def test_prewarm_swallows_stream_start_failure(monkeypatch):
    class _StartBoomStream:
        def __init__(self, **kw): pass
        def start(self):
            raise RuntimeError("PortAudioError on start")
        def stop(self): pass
        def close(self): pass

    monkeypatch.setattr("kira.recorder.sd.InputStream", lambda **kw: _StartBoomStream())
    r = Recorder()

    r.prewarm()

    assert r._stream is None
    with pytest.raises(DeviceUnavailable):
        r.start()
