from __future__ import annotations

from dataclasses import asdict

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import TRUCKS
from database.models import DeliveryPoint, LoadOperation
from database.storage import JsonStorage
from keyboards.keyboards import shift_actions_keyboard, trucks_keyboard
from services.reporting import build_shift_record, export_shift_to_csv
from states.work_states import WorkStates
from utils.time_utils import moscow_now

router = Router()
storage = JsonStorage()


def _parse_number(raw_text: str) -> float | None:
    cleaned = raw_text.replace(",", ".").strip()
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return round(value, 2) if value >= 0 else None


def _truck_by_name(name: str):
    for truck in TRUCKS.values():
        if truck.name == name:
            return truck
    return None


def _build_status_text(data: dict) -> str:
    truck_name = data.get("truck_name", "Не выбрана")
    loaded_total = round(sum(item["volume"] for item in data.get("loads", [])), 2)
    fact_total = round(sum(item["fact_volume"] for item in data.get("delivery_points", [])), 2)
    doc_total = round(sum(item["doc_volume"] for item in data.get("delivery_points", [])), 2)
    savings_total = round(sum(item["savings_volume"] for item in data.get("delivery_points", [])), 2)
    remaining = round(data.get("remaining_volume", 0.0), 2)
    total_km = round(data.get("total_km", 0.0), 2)
    points_count = len(data.get("delivery_points", []))
    loads_count = len(data.get("loads", []))
    base_trips_count = int(data.get("base_trips_count", 0))

    return (
        f"Статус смены\n"
        f"Машина: {truck_name}\n\n"
        f"Закачек: {loads_count}\n"
        f"Поездок на базу: {base_trips_count}\n"
        f"Закачано: {loaded_total} куб.\n"
        f"Точек: {points_count}\n"
        f"Слито по факту: {fact_total} куб.\n"
        f"Слито по документам: {doc_total} куб.\n"
        f"Экономия: {savings_total} куб.\n"
        f"Остаток: {remaining} куб.\n"
        f"Пробег: {total_km} км.\n\n"
        "Выберите следующее действие:"
    )


async def _delete_user_message(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        pass


async def _delete_message_by_id(message: Message, message_id: int | None) -> None:
    if message_id is None:
        return
    try:
        await message.bot.delete_message(chat_id=message.chat.id, message_id=message_id)
    except TelegramBadRequest:
        pass


async def _clear_tracked_messages(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await _delete_message_by_id(message, data.get("last_prompt_message_id"))
    await _delete_message_by_id(message, data.get("status_message_id"))


async def _ask_and_track(message: Message, state: FSMContext, text: str) -> None:
    prompt = await message.answer(text)
    await state.update_data(last_prompt_message_id=prompt.message_id)


async def _update_status_message(message: Message, state: FSMContext, notice: str | None = None) -> None:
    data = await state.get_data()
    text = _build_status_text(data)
    if notice:
        text = f"{notice}\n\n{text}"

    status_message_id = data.get("status_message_id")
    if status_message_id is None:
        status_message = await message.answer(text, reply_markup=shift_actions_keyboard())
        await state.update_data(status_message_id=status_message.message_id)
        return

    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_message_id,
            text=text,
        )
    except TelegramBadRequest:
        status_message = await message.answer(text, reply_markup=shift_actions_keyboard())
        await state.update_data(status_message_id=status_message.message_id)


@router.message(Command("start"))
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Бот учета доставки воды.\n"
        "Выберите машину, чтобы начать смену.",
        reply_markup=trucks_keyboard(),
    )
    await state.set_state(WorkStates.choosing_truck)


@router.message(Command("cancel"))
@router.message(F.text == "Отмена")
async def cancel(message: Message, state: FSMContext) -> None:
    await _clear_tracked_messages(message, state)
    await state.clear()
    await message.answer(
        "Текущая смена сброшена. Выберите машину заново.",
        reply_markup=trucks_keyboard(),
    )
    await state.set_state(WorkStates.choosing_truck)


@router.message(WorkStates.choosing_truck)
async def choose_truck(message: Message, state: FSMContext) -> None:
    truck = _truck_by_name(message.text or "")
    if truck is None:
        await message.answer("Выберите машину кнопкой на клавиатуре.")
        return

    await state.update_data(
        truck_code=truck.code,
        truck_name=truck.name,
        driver_name=truck.driver_name,
        work_date=moscow_now().strftime("%Y-%m-%d"),
        started_at=moscow_now().isoformat(timespec="seconds"),
        loads=[],
        delivery_points=[],
        remaining_volume=0.0,
        total_km=0.0,
        status_message_id=None,
        last_prompt_message_id=None,
        km_entry_context=None,
        base_trips_count=0,
    )
    await message.answer(
        f"Смена для {truck.name} начата.",
        reply_markup=shift_actions_keyboard(),
    )
    await _update_status_message(message, state)
    await state.set_state(WorkStates.choosing_action)


@router.message(WorkStates.choosing_action, F.text == "Закачать воду")
async def ask_load(message: Message, state: FSMContext) -> None:
    await _ask_and_track(message, state, "Сколько кубов закачали в машину?")
    await state.set_state(WorkStates.entering_load)


@router.message(WorkStates.entering_load)
async def save_load(message: Message, state: FSMContext) -> None:
    load = _parse_number(message.text or "")
    if load is None or load == 0:
        await message.answer("Введите положительное число. Например: 15 или 2.5")
        return

    data = await state.get_data()
    loads = data.get("loads", [])
    loads.append(asdict(LoadOperation(volume=load)))
    remaining_volume = round(data.get("remaining_volume", 0.0) + load, 2)

    await state.update_data(loads=loads, remaining_volume=remaining_volume)
    await _delete_message_by_id(message, data.get("last_prompt_message_id"))
    await _delete_user_message(message)
    await state.update_data(last_prompt_message_id=None)
    await _update_status_message(
        message,
        state,
        notice=f"Закачка добавлена: {load} куб.\nТекущий остаток в машине: {remaining_volume} куб.",
    )
    await state.set_state(WorkStates.choosing_action)


@router.message(WorkStates.choosing_action, F.text == "Добавить точку")
async def ask_fact(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("remaining_volume", 0.0) <= 0:
        await message.answer("Сначала добавьте хотя бы одну закачку воды.")
        return

    await _ask_and_track(message, state, "Сколько кубов слили по факту на точке?")
    await state.set_state(WorkStates.entering_fact)


@router.message(WorkStates.choosing_action, F.text == "Дозалить воду")
async def ask_base_km(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("loads"):
        await message.answer("Сначала сделайте первую закачку воды, потом можно учитывать поездку на базу.")
        return

    await state.update_data(km_entry_context="to_base")
    await _ask_and_track(message, state, "Сколько километров проехали до базы?")
    await state.set_state(WorkStates.entering_km)


@router.message(WorkStates.entering_fact)
async def save_fact(message: Message, state: FSMContext) -> None:
    fact = _parse_number(message.text or "")
    data = await state.get_data()
    remaining = data.get("remaining_volume", 0.0)

    if fact is None:
        await message.answer("Введите число. Например: 1 или 2.5")
        return
    if fact == 0:
        await message.answer("Факт не может быть 0.")
        return
    if fact > remaining:
        await message.answer(f"Факт не может быть больше остатка в машине ({remaining} куб.).")
        return

    await state.update_data(current_fact=fact)
    await _delete_message_by_id(message, data.get("last_prompt_message_id"))
    await _delete_user_message(message)
    await _ask_and_track(message, state, "Сколько кубов указано по документам на этой точке?")
    await state.set_state(WorkStates.entering_doc)


@router.message(WorkStates.entering_doc)
async def save_doc(message: Message, state: FSMContext) -> None:
    doc = _parse_number(message.text or "")
    if doc is None or doc == 0:
        await message.answer("Введите положительное число. Например: 2")
        return

    data = await state.get_data()
    fact = round(data["current_fact"], 2)
    remaining = round(data["remaining_volume"] - fact, 2)
    points = data.get("delivery_points", [])
    point = DeliveryPoint(
        point_number=len(points) + 1,
        fact_volume=fact,
        doc_volume=doc,
        savings_volume=round(doc - fact, 2),
    )
    points.append(asdict(point))

    await state.update_data(
        delivery_points=points,
        remaining_volume=remaining,
        current_fact=None,
        km_entry_context="after_point",
    )
    await _delete_message_by_id(message, data.get("last_prompt_message_id"))
    await _delete_user_message(message)
    await _ask_and_track(
        message,
        state,
        (
            f"Точка #{point.point_number} добавлена.\n"
            f"Факт: {point.fact_volume} куб.\n"
            f"Документы: {point.doc_volume} куб.\n"
            f"Экономия: {point.savings_volume} куб.\n"
            f"Остаток: {remaining} куб.\n\n"
            "Сколько километров проехали до этой точки?"
        ),
    )
    await state.set_state(WorkStates.entering_km)


@router.message(WorkStates.choosing_action, F.text == "Добавить километры")
async def ask_km(message: Message, state: FSMContext) -> None:
    await state.update_data(km_entry_context="manual")
    await _ask_and_track(message, state, "Сколько километров добавить в общий пробег?")
    await state.set_state(WorkStates.entering_km)


@router.message(WorkStates.entering_km)
async def save_km(message: Message, state: FSMContext) -> None:
    km_value = _parse_number(message.text or "")
    if km_value is None:
        await message.answer("Введите число. Например: 124")
        return

    data = await state.get_data()
    new_total_km = round(float(data.get("total_km", 0.0)) + km_value, 2)
    context = data.get("km_entry_context")
    updates = {"total_km": new_total_km}
    if context == "to_base":
        updates["base_trips_count"] = int(data.get("base_trips_count", 0)) + 1
    await state.update_data(**updates)
    await _delete_message_by_id(message, data.get("last_prompt_message_id"))
    await _delete_user_message(message)
    await state.update_data(last_prompt_message_id=None, km_entry_context=None)

    if context == "after_point":
        notice = f"Добавлено после точки: {km_value} км.\nОбщий пробег: {new_total_km} км."
    elif context == "to_base":
        notice = f"До базы: {km_value} км.\nОбщий пробег: {new_total_km} км.\nМожно снова делать закачку."
    else:
        notice = f"Пробег добавлен: {km_value} км.\nОбщий пробег: {new_total_km} км."

    await _update_status_message(message, state, notice=notice)
    await state.set_state(WorkStates.choosing_action)


@router.message(WorkStates.choosing_action, F.text == "Завершить смену")
async def finish_shift(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data.get("loads"):
        await message.answer("Нельзя завершить пустую смену. Сначала добавьте закачку.")
        return

    truck = TRUCKS[data["truck_code"]]
    loads = [LoadOperation(**item) for item in data.get("loads", [])]
    delivery_points = [DeliveryPoint(**item) for item in data.get("delivery_points", [])]

    shift = build_shift_record(
        truck=truck,
        work_date=data["work_date"],
        started_at=data["started_at"],
        loads=loads,
        delivery_points=delivery_points,
        total_km=float(data.get("total_km", 0.0)),
        remaining_volume=float(data.get("remaining_volume", 0.0)),
    )
    storage.save_shift(shift)
    report_path = export_shift_to_csv(shift)

    await _clear_tracked_messages(message, state)
    await message.answer(
        "Смена завершена.\n\n"
        f"Закачано: {shift.loaded_total} куб.\n"
        f"Слито по факту: {shift.delivered_fact_total} куб.\n"
        f"Слито по документам: {shift.delivered_doc_total} куб.\n"
        f"Экономия за смену: {shift.savings_total} куб.\n"
        f"Пробег: {shift.total_km} км.",
        reply_markup=trucks_keyboard(),
    )
    await state.clear()
    await state.set_state(WorkStates.choosing_truck)


@router.message()
async def fallback(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Напишите /start, чтобы начать работу.")
        return

    await message.answer("Используйте кнопки на клавиатуре или /cancel для сброса смены.")
