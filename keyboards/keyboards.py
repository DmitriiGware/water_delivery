from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from config import TRUCKS


def trucks_keyboard() -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=truck.name)] for truck in TRUCKS.values()]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def shift_actions_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Закачать воду")],
            [KeyboardButton(text="Добавить точку")],
            [KeyboardButton(text="Дозалить воду")],
            [KeyboardButton(text="Добавить километры")],
            [KeyboardButton(text="Завершить смену")],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
    )
