"""Rendering checks for the cumulative credit chart."""

from unittest.mock import patch

import pytest
from textual.color import Color

from estimator import CreditChart, CreditEstimatorApp


def make_app():
    return CreditEstimatorApp(
        db="/nonexistent/opencode.db", budget=50_000, interval=3600, offline=True
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "labels",
    [
        [f"12:{i:02d}" if i % 10 == 0 else "" for i in range(60)],
        [["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][i // 24]
         if i % 24 == 0 else "" for i in range(168)],
    ],
)
async def test_chart_keeps_sparse_time_labels(labels):
    app = make_app()
    async with app.run_test(size=(120, 40)):
        chart = app.query_one(CreditChart)
        chart.update_data(labels, list(range(len(labels))), "This week", 50_000)
        with patch.object(chart.plt, "xticks", wraps=chart.plt.xticks) as ticks:
            chart.render()
        positions, shown = ticks.call_args.args
        assert shown == [label for label in labels if label]
        assert positions == [i for i, label in enumerate(labels) if label]


@pytest.mark.asyncio
async def test_chart_ticks_adapt_on_resize_and_keep_endpoints():
    app = make_app()
    async with app.run_test(size=(80, 40)) as pilot:
        chart = app.query_one(CreditChart)
        labels = [str(i + 1) for i in range(31)]
        chart.update_data(labels, list(range(31)), "This month", 50_000)
        with patch.object(chart.plt, "xticks", wraps=chart.plt.xticks) as ticks:
            chart.render()
            narrow = ticks.call_args.args[1]
            await pilot.resize_terminal(160, 40)
            await pilot.pause()
            chart.render()
            wide = ticks.call_args.args[1]
        assert len(narrow) < len(wide)
        assert narrow[0] == wide[0] == "1"
        assert narrow[-1] == wide[-1] == "31"


@pytest.mark.asyncio
@pytest.mark.parametrize("values", [[0], [42], [0, 0, 0], [1, 2000, 12345]])
async def test_chart_has_short_title_zero_baseline_and_visible_line(values):
    app = make_app()
    async with app.run_test(size=(100, 40)):
        chart = app.query_one(CreditChart)
        chart.update_data([str(i + 1) for i in range(len(values))], values,
                          "This month", 50_000)
        with patch.object(chart.plt, "ylim", wraps=chart.plt.ylim) as limits:
            rendered = chart.render().plain
        assert "This month · Cumulative credits" in rendered
        assert "50,000" not in rendered
        assert limits.call_args.args[0] == 0
        assert limits.call_args.args[1] > max(values)
        assert any("\u2801" <= char <= "\u28ff" for char in rendered)


@pytest.mark.asyncio
async def test_chart_clears_previous_plot_for_empty_data():
    app = make_app()
    async with app.run_test(size=(100, 40)):
        chart = app.query_one(CreditChart)
        chart.update_data(["1", "2"], [10, 20], "Today", 50_000)
        chart.render()
        chart.update_data([], [], "This week", 50_000)
        rendered = chart.render().plain
        assert "No usage data for this range" in rendered
        assert not any("\u2801" <= char <= "\u28ff" for char in rendered)


@pytest.mark.asyncio
async def test_chart_uses_current_theme_and_compact_credit_labels():
    app = make_app()
    async with app.run_test(size=(100, 40)) as pilot:
        chart = app.query_one(CreditChart)
        chart.update_data(["1", "2"], [0, 1_500_000], "Today", 50_000)
        for theme in ("textual-dark", "textual-light"):
            app.theme = theme
            await pilot.pause()
            rendered = chart.render()
            accent = Color.parse(app.theme_variables["accent"]).rgb
            assert "1M" in rendered.plain
            assert any(
                span.style.color is not None
                and span.style.color.get_truecolor() == accent
                for span in rendered.spans
            )


@pytest.mark.asyncio
async def test_chart_handles_blank_labels():
    app = make_app()
    async with app.run_test(size=(100, 40)):
        chart = app.query_one(CreditChart)
        chart.update_data(["", ""], [0, 2500], "This week", 50_000)
        rendered = chart.render().plain
        assert "This week · Cumulative credits" in rendered
        assert "2k" in rendered
