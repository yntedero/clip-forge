"""Lightweight translation layer.

Qt's full ``QTranslator`` / ``lrelease`` toolchain is overkill at this
stage. We use a small in-Python dictionary per locale; ``tr()`` returns
the translated string for the active locale, falling back to the source
English string when no translation exists. Switching locale emits a
signal so windows can re-translate live.
"""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import QObject, Signal

LocaleCode = Literal["en", "uk"]

_TRANSLATIONS: dict[LocaleCode, dict[str, str]] = {
    "en": {},
    "uk": {
        # Headings / window
        "ClipForge": "ClipForge",
        "Slice long videos into short clips with subtle randomized effects.": (
            "Розрізає довгі відео на короткі кліпи з тонкими випадковими ефектами."
        ),
        # Drop zone
        "Drop a video here, or click to browse": (
            "Перетягніть відео сюди або натисніть, щоб вибрати"
        ),
        "Supported:": "Підтримуються:",
        # Cards / labels
        "Preset": "Пресет",
        "Output folder": "Папка виводу",
        "Browse…": "Огляд…",
        "Open": "Відкрити",
        # Buttons
        "Start": "Старт",
        "Cancel": "Скасувати",
        "Idle": "Очікування",
        "Preparing…": "Підготовка…",
        "Done": "Готово",
        "Failed": "Помилка",
        # Status
        "FFmpeg ready": "FFmpeg готовий",
        "FFmpeg missing — run scripts/fetch_ffmpeg.py": (
            "FFmpeg відсутній — запустіть scripts/fetch_ffmpeg.py"
        ),
        # Log / messages
        "Selected source:": "Вибране джерело:",
        "Starting job with preset": "Запуск з пресетом",
        "Probing": "Аналізуємо",
        "Planned {n} clips.": "Заплановано {n} кліпів.",
        "Job finished.": "Завдання завершено.",
        "Cancellation requested.": "Запит на скасування.",
        "Job finished": "Завдання завершено",
        "Your clips are ready in the output folder.": ("Ваші кліпи готові у папці виводу."),
        "Job failed": "Помилка завдання",
        "Cannot create output folder": "Не вдається створити папку виводу",
        "Preset load failed": "Не вдалося завантажити пресети",
        "Could not load built-in presets:": ("Не вдалося завантажити вбудовані пресети:"),
        "Choose a source video": "Виберіть вихідне відео",
        "Choose output folder": "Виберіть папку виводу",
        # Presets (descriptions)
        "TikTok Soft": "TikTok М’який",
        "TikTok Hard Uniq": "TikTok Жорсткий",
        "YouTube Shorts": "YouTube Shorts",
        "Instagram Reels": "Instagram Reels",
        "Plain Slice": "Просто нарізати",
        "Custom": "Власний",
        "Configure everything yourself": "Налаштуйте все самостійно",
        # Custom preset panel
        "Clip length": "Тривалість кліпу",
        "min": "мін",
        "max": "макс",
        "Effects": "Ефекти",
        "Global intensity": "Загальна інтенсивність",
        "Aspect ratio": "Співвідношення",
        "Codec": "Кодек",
        "Quality": "Якість",
        "Audio": "Аудіо",
        "Mirror": "Дзеркало",
        "Zoom": "Зум",
        "Speed": "Швидкість",
        "Color": "Колір",
        "Rotation": "Поворот",
        "Edge crop": "Обрізка країв",
        "Noise": "Шум",
        "Vignette": "Віньєтка",
        "Pixel shift": "Зсув пікселів",
        "Film grain": "Кіноплівка",
        "Pitch preservation": "Збереження висоти тону",
        "Keep audio": "Зберегти звук",
        "Mute": "Без звуку",
        "Remove track": "Видалити доріжку",
        "Fast": "Швидко",
        "Balanced": "Збалансовано",
        "High Quality": "Висока якість",
        "Original": "Оригінал",
        # v1.0.3 additions
        "Save current as preset…": "Зберегти як пресет…",
        "Preset name": "Назва пресета",
        "Name your preset": "Назвіть свій пресет",
        "Preset saved": "Пресет збережено",
        "Change…": "Змінити…",
        "Choose a video to begin": "Виберіть відео, щоб почати",
        "Effect": "Ефект",
        "Length": "Тривалість",
        "From": "Від",
        "To": "До",
        "Custom configuration": "Власні налаштування",
        "A preset with that name already exists.": "Пресет з такою назвою вже існує.",
    },
}


class TranslationManager(QObject):
    """Holds the active locale and emits a signal when it changes."""

    locale_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._locale: LocaleCode = "en"

    @property
    def locale(self) -> LocaleCode:
        return self._locale

    def set_locale(self, code: LocaleCode) -> None:
        if code == self._locale:
            return
        self._locale = code
        self.locale_changed.emit(code)

    def translate(self, source: str) -> str:
        table = _TRANSLATIONS.get(self._locale, {})
        return table.get(source, source)


_manager = TranslationManager()


def manager() -> TranslationManager:
    return _manager


def tr(source: str) -> str:
    return _manager.translate(source)
