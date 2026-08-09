"""QComboBox helpers — gender is always Nam or Nữ."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox

GENDER_CHOICES = ("Nam", "Nữ")

_COMBO_STYLE = (
    "background-color: #1e293b; color: #f8fafc; border: 1px solid #334155; "
    "padding: 6px; border-radius: 4px;"
)


def make_gender_combo(*, filter_mode: bool = False) -> QComboBox:
    """filter_mode: first row «—» = không lọc (Tab 2 / lưới tìm)."""
    combo = QComboBox()
    if filter_mode:
        combo.addItem("—")
    combo.addItems(GENDER_CHOICES)
    combo.setStyleSheet(_COMBO_STYLE)
    return combo


def gender_combo_value(combo: QComboBox, *, filter_mode: bool = False) -> str:
    text = combo.currentText().strip()
    if filter_mode and text in ("", "—"):
        return ""
    return text if text in GENDER_CHOICES else ""


def set_gender_combo(
    combo: QComboBox, value: str | None, *, filter_mode: bool = False
) -> None:
    text = (value or "").strip()
    if filter_mode and not text:
        combo.setCurrentIndex(0)
        return
    if text in GENDER_CHOICES:
        combo.setCurrentText(text)
    else:
        combo.setCurrentIndex(1 if filter_mode else 0)
