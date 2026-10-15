"""Aurora gradient controls rendered locally, without browser dependencies."""
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk


class AuroraButton(ctk.CTkButton):
    """A DPI-aware purple-to-cyan button that retains CTk's states and events."""

    def _draw(self, no_color_updates=False):
        super()._draw(no_color_updates)
        self._canvas.delete("aurora_gradient")
        self._canvas.delete("aurora_text")
        if self._state == "disabled":
            if self._text_label is not None:
                self._text_label.grid()
            return
        width = max(1, round(self._apply_widget_scaling(self._current_width)))
        height = max(1, round(self._apply_widget_scaling(self._current_height)))
        radius = round(self._apply_widget_scaling(self._corner_radius))
        start, end = (151, 88, 216), (35, 180, 209)
        if getattr(self, "_aurora_hover", False):
            start, end = (168, 108, 231), (53, 196, 222)
        image = Image.new("RGBA", (width, height))
        draw = ImageDraw.Draw(image)
        for x in range(width):
            t = x / max(width - 1, 1)
            color = tuple(round(a + (b - a) * t) for a, b in zip(start, end))
            draw.line((x, 0, x, height), fill=(*color, 255))
        mask = Image.new("L", image.size)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=255)
        image.putalpha(mask)
        self._aurora_photo = ImageTk.PhotoImage(image, master=self)
        self._canvas.create_image(0, 0, image=self._aurora_photo, anchor="nw", tags="aurora_gradient")
        if self._text_label is not None:
            self._text_label.grid_remove()
        self._canvas.create_text(
            width / 2, height / 2, text=self._text,
            font=self._apply_font_scaling(self._font),
            fill=self._apply_appearance_mode(self._text_color),
            tags="aurora_text",
        )
        # The existing CTk canvas bindings retain mouse/keyboard behavior.

    def _on_enter(self, event=None):
        self._aurora_hover = True
        super()._on_enter(event)
        self._draw()

    def _on_leave(self, event=None):
        self._aurora_hover = False
        super()._on_leave(event)
        self._draw()
