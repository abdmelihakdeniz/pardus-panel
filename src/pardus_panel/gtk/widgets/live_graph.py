import math
from collections import deque
from collections.abc import Iterable, Sequence

import cairo
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

Color = tuple[float, float, float]
Series = tuple[Sequence[float], float, Color]


class _GraphSeries:
    def __init__(
        self,
        *,
        minimum_scale: float = 100.0,
        adaptive: bool = True,
        headroom: float = 1.15,
    ) -> None:
        self._values: deque[float] = deque([0.0] * 60, maxlen=60)
        self._minimum_scale = float(minimum_scale)
        self._scale = float(minimum_scale)
        self._adaptive = adaptive
        self._headroom = float(headroom)

    @property
    def values(self) -> tuple[float, ...]:
        return tuple(self._values)

    @property
    def scale(self) -> float:
        return self._scale

    def append(self, value: float) -> None:
        value = float(value)
        if not math.isfinite(value):
            value = 0.0
        self._values.append(max(0.0, value))
        if not self._adaptive:
            return
        target = max(self._minimum_scale, max(self._values) * self._headroom)
        self._scale = (
            target
            if target > self._scale
            else max(target, self._scale * 0.92)
        )


def _value_to_y(value: float, maximum: float, height: float) -> float:
    return height if maximum <= 0 else height - value / maximum * height


def _path(
    context: cairo.Context,
    width: float,
    height: float,
    values: Sequence[float],
    maximum: float,
) -> None:
    step = width / (len(values) - 1)
    context.move_to(0, _value_to_y(values[0], maximum, height))
    for index, value in enumerate(values[1:], 1):
        context.line_to(index * step, _value_to_y(value, maximum, height))


def _draw_graph(
    context: cairo.Context,
    width: float,
    height: float,
    series: Iterable[Series],
) -> None:
    context.set_source_rgba(0, 0, 0, 0.05)
    context.paint()
    context.set_source_rgba(0.5, 0.5, 0.5, 0.15)
    context.set_line_width(1)
    for row in range(1, 4):
        y = round(height * row / 4) + 0.5
        context.move_to(0, y)
        context.line_to(width, y)
    for column in range(1, 6):
        x = round(width * column / 6) + 0.5
        context.move_to(x, 0)
        context.line_to(x, height)
    context.stroke()

    drawable = [item for item in series if len(item[0]) >= 2]
    if not drawable:
        return
    maximum = max(item[1] for item in drawable)
    for values, _scale, color in drawable:
        context.save()
        context.rectangle(0, 0, width, height)
        context.clip()
        context.set_source_rgba(*color, 0.8)
        context.set_line_width(2)
        _path(context, width, height, values, maximum)
        context.stroke_preserve()
        context.line_to(width, height)
        context.line_to(0, height)
        context.close_path()
        context.set_source_rgba(*color, 0.15)
        context.fill()
        context.restore()


class LiveGraph(Gtk.DrawingArea):
    def __init__(self, *, color: Color) -> None:
        super().__init__()
        self.set_size_request(-1, 72)
        self._series = _GraphSeries(minimum_scale=100.0, adaptive=False)
        self._color = color
        self.connect("draw", self._draw)

    def append(self, value: float) -> None:
        value = float(value)
        self._series.append(
            min(100.0, max(0.0, value)) if math.isfinite(value) else 0.0
        )
        self.queue_draw()

    def _draw(self, _widget: Gtk.DrawingArea, context: cairo.Context) -> bool:
        allocation = self.get_allocation()
        _draw_graph(
            context,
            max(1, allocation.width),
            max(1, allocation.height),
            ((self._series.values, self._series.scale, self._color),),
        )
        return False


class MultiSeriesGraph(Gtk.DrawingArea):
    def __init__(
        self,
        *,
        colors: tuple[Color, ...],
        minimum_scale: float = 100.0,
    ) -> None:
        super().__init__()
        self.set_size_request(-1, 120)
        self._series = tuple(
            _GraphSeries(
                minimum_scale=minimum_scale,
                adaptive=True,
                headroom=1.10,
            )
            for _ in colors
        )
        self._colors = colors
        self.connect("draw", self._draw)

    def append(self, *values: float) -> None:
        for series, value in zip(self._series, values):
            series.append(value)
        self.queue_draw()

    def _draw(self, _widget, context) -> bool:
        allocation = self.get_allocation()
        _draw_graph(
            context,
            max(1, allocation.width),
            max(1, allocation.height),
            tuple(
                (series.values, series.scale, color)
                for series, color in zip(self._series, self._colors)
            ),
        )
        return False
