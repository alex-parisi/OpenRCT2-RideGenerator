"""
Tests for the CLI entrypoint (__main__).
"""

import argparse
import types

from openrct2_ride_generator import __main__ as cli


def _args(input_path, test=False, skip_render=False):
    return argparse.Namespace(input=input_path, test=test, skip_render=skip_render)


def _patch_dispatch(monkeypatch, calls):
    obj = types.SimpleNamespace(units_per_tile=32.0)

    def fake_load(path):
        calls["load"] = path
        return obj

    def fake_export(o, ctx, out, skip_render):
        calls["export"] = {"obj": o, "ctx": ctx, "out": out, "skip_render": skip_render}

    def fake_export_test(o, ctx):
        calls["export_test"] = {"obj": o, "ctx": ctx}

    monkeypatch.setattr(
        cli, "_DISPATCH", {"ride": (fake_load, fake_export, fake_export_test)}
    )
    monkeypatch.setattr(
        cli, "make_context", lambda lights, upt, test, root=None: ("ctx", upt, test)
    )
    monkeypatch.setattr(cli, "output_directory_of", lambda root: "out-dir")
    return obj


def test_render_full_export_path(monkeypatch):
    calls = {}
    obj = _patch_dispatch(monkeypatch, calls)
    cli._render(_args("s.json", skip_render=True), {}, [])
    assert "export_test" not in calls
    assert calls["load"] == "s.json"
    assert calls["export"]["obj"] is obj
    assert calls["export"]["out"] == "out-dir"
    assert calls["export"]["skip_render"] is True
    # make_context was told this is not a test render.
    assert calls["export"]["ctx"] == ("ctx", 32.0, False)


def test_render_test_path(monkeypatch):
    calls = {}
    _patch_dispatch(monkeypatch, calls)
    cli._render(_args("s.json", test=True), {}, [])
    assert "export" not in calls
    # make_context was told this is a test render (TEST_ZOOM preview scale).
    assert calls["export_test"]["ctx"] == ("ctx", 32.0, True)


def test_real_dispatch_table_covers_every_object_type():
    assert set(cli._DISPATCH) == {"ride"}
    for triple in cli._DISPATCH.values():
        assert len(triple) == 3  # (load, export, export_test)


def test_main_delegates_to_run_cli(monkeypatch):
    captured = {}

    def fake_run_cli(prog, argv, render):
        captured["prog"] = prog
        captured["argv"] = argv
        captured["render"] = render
        return 0

    monkeypatch.setattr(cli, "run_cli", fake_run_cli)
    rc = cli.main(["s.json"])
    assert rc == 0
    assert captured["prog"] == "openrct2-ride-generator"
    assert captured["argv"] == ["s.json"]
    assert captured["render"] is cli._render


def test_main_returns_run_cli_exit_code(monkeypatch):
    monkeypatch.setattr(cli, "run_cli", lambda prog, argv, render: 1)
    assert cli.main([]) == 1


def test_main_end_to_end_through_run_cli(monkeypatch, tmp_path):
    cfg = tmp_path / "s.json"
    cfg.write_text("{}")

    calls = {}

    def fake_load(path):
        calls["load"] = path
        return types.SimpleNamespace(units_per_tile=32.0)

    def fake_export(o, ctx, out, skip_render):
        calls["ran"] = True

    monkeypatch.setattr(
        cli, "_DISPATCH", {"ride": (fake_load, fake_export, lambda o, c: None)}
    )
    monkeypatch.setattr(cli, "make_context", lambda lights, upt, test, root=None: "ctx")
    monkeypatch.setattr(cli, "output_directory_of", lambda root: tmp_path)

    assert cli.main([str(cfg)]) == 0
    assert calls["ran"] is True


def test_dunder_main_guard_invokes_sys_exit(monkeypatch):
    import runpy
    import sys

    exits = []
    monkeypatch.setattr(sys, "exit", exits.append)

    import openrct2_object_common.cli as _cli
    monkeypatch.setattr(_cli, "run_cli", lambda prog, argv, render: 5)

    sys.modules.pop("openrct2_ride_generator.__main__", None)
    runpy.run_module("openrct2_ride_generator", run_name="__main__")

    assert exits == [5]
