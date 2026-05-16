from aiogram.fsm.state import State, StatesGroup


class SymptomAnalysis(StatesGroup):
    waiting_for_symptoms = State()
    waiting_for_duration = State()
    waiting_for_temperature = State()
    waiting_for_age = State()
    waiting_for_gender = State()
    analyzing = State()


class HandwritingAnalysis(StatesGroup):
    waiting_for_photo = State()
    analyzing = State()


class LabAnalysis(StatesGroup):
    waiting_for_pricing = State()
    waiting_for_file = State()
    waiting_for_comment = State()


class AdminActions(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_user_id_reset = State()


class LabPayment(StatesGroup):
    waiting_for_payment = State()
    waiting_for_user_id_addfree = State()
    waiting_for_addfree_count = State()


class WaitingPhotoType(StatesGroup):
    choosing = State()