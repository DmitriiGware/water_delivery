from aiogram.fsm.state import State, StatesGroup


class WorkStates(StatesGroup):
    choosing_truck = State()
    choosing_action = State()
    entering_load = State()
    entering_fact = State()
    entering_doc = State()
    entering_km = State()
