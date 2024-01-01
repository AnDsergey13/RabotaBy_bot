import asyncio
from os import environ
# import threading

from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from Data import Base, SearchTemplates, BlackList, VisitsList
# import Main

# Извлекаем из виртуальной среды переменные окружения. API токен и id пользователя
telegram_key = environ.get('API_TELEGRAM_KEY')
user_id = environ.get('USER_ID')
# Подключаемся к боту
bot = Bot(token=telegram_key)

# global st, bl, vl, telegram_key, user_id, bot, storage, dp
st = SearchTemplates()
bl = BlackList()
vl = VisitsList()

# MemoryStorage. Храним состояния в оперативной памяти. Заменить на другой тип хранения
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# Определение класса состояний.
class CS(StatesGroup):
	AVAILABLE = State()
	ADD_T1 = State()
	ADD_T2 = State()
	ADD_B1 = State()
	ADD_B2 = State()
	DEL_T = State()
	DEL_B = State()
	STATE_T1 = State()
	STATE_T2 = State()
	STATE_B1 = State()
	STATE_B2 = State()
	SET_TIME = State()

# def run_telegram():
# 	executor.start_polling(dp, skip_updates=True)


async def is_user_ID(message):
	return message.from_user.id == int(user_id)

# TODO Удалить повторяющийся код. Оптимизировать функции

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message, state: FSMContext):
	await asyncio.sleep(0.5)
	# Только пользователь с допустимым ID сможет получить доступ к боту
	if await is_user_ID(message):
		await bot.send_message(message.chat.id, "🖐 Hola! \nВведите /help для доступа к командам")
		await state.set_state(CS.AVAILABLE)
	else:
		await bot.send_message(message.chat.id, "❌  Please leave this chat. You're an unregistered user\nПрошу покинуть этот чат. Вы незарегистрированный пользователь")


@dp.message_handler(commands=['help'], state=CS.AVAILABLE)
async def command_help(message: types.Message):
	await bot.send_message(message.chat.id, """
	Шаблоны поиска
	/add_t Добавить шаблон поиска
	/del_t Удалить шаблон поиска
	/state_t Установить состояние для шаблона
	/print_t Вывести все шаблоны поиска

	Чёрный список
	/add_b Добавить исключение в чёрный список
	/del_b Удалить исключение из чёрного списка
	/state_b Установить состояние для исключения
	/print_b Вывести все исключения из чёрного списка
	""")


@dp.message_handler(commands=['add_t'], state=CS.AVAILABLE)
async def add_t(message: types.Message, state: FSMContext):
	await bot.send_message(message.chat.id, "1️⃣ Введите слово ключ шаблона")
	await state.set_state(CS.ADD_T1)


@dp.message_handler(state=CS.ADD_T1)
async def add_t_key(message: types.Message, state: FSMContext):
	wordkey = message.text
	# Проверка, на уникальность. Существует ли таке слово ключ в базе шаблонов
	if wordkey in st.get_col_by_name("key"):
		await bot.send_message(message.chat.id, "❌ Такое слово ключ уже существует. Введите другое слово ключ")
	else:
		# Сохраняем полученное значение
		await state.update_data(WORDKEY=wordkey)
		await state.set_state(CS.ADD_T2)
		await bot.send_message(message.chat.id, "✅ Слово ключ - сохранён!")
		await bot.send_message(message.chat.id, "2️⃣ Введите URL для добавления в базу")


@dp.message_handler(state=CS.ADD_T2)
async def add_t_url(message: types.Message, state: FSMContext):
	# Извлекаем wordkey
	data = await state.get_data()
	wordkey = data.get("WORDKEY")
	# Получаем URL
	url = message.text
	st.create_new_row(wordkey, url)
	await bot.send_message(message.chat.id, "✅ Новый шаблон добавлен в базу!")
	await state.set_state(CS.AVAILABLE)


@dp.message_handler(commands=['del_t'], state=CS.AVAILABLE)
async def del_t_msg(message: types.Message, state: FSMContext):
	await bot.send_message(message.chat.id, "Укажите номер шаблона.\nЧтобы узнать номер введите /print_t")
	await state.set_state(CS.DEL_T)


@dp.message_handler(state=CS.DEL_T)
async def del_t_input(message: types.Message, state: FSMContext):
	""" """
	msg = message.text

	try:
		# templace - такое слово не существует. Изменить
		number_templace = int(msg)
	except ValueError as err:
		# Если вместо числа принимается команда /print_t, то запускаем функцию print_t, без выполнения остального кода
		if msg == "/print_t":
			await print_t(message)
		else:
			# Если полученное число неправильное, то выводится сообщение об ошибке
			print(err)
			await bot.send_message(message.chat.id, "❌ Неверное значение! Укажите число из списка")
	else:
		# Если try выполнился, то запускается else (код ниже)
		if st.get_num_all_rows() >= number_templace > 0:
			st.delete_row_by_number(number_templace)
			await bot.send_message(message.chat.id, "✅ Номер шаблона успешно удалён!")
			await state.set_state(CS.AVAILABLE)
		else:
			await bot.send_message(message.chat.id, "❌ Такой номер в базе отсутствует. Введите корректный!")


@dp.message_handler(commands=['state_t'], state=CS.AVAILABLE)
async def state_t(message: types.Message, state: FSMContext):
	await bot.send_message(message.chat.id, "1️⃣ Укажите номер шаблона.\nЧтобы узнать номер введите /print_t")
	await state.set_state(CS.STATE_T1)


@dp.message_handler(state=CS.STATE_T1)
async def state_t_number(message: types.Message, state: FSMContext):
	msg = message.text

	try:
		number_template = int(msg)
	except ValueError as err:
		# Если вместо числа принимается команда /print_t, то запускаем функцию print_t, без выполнения остального кода
		if msg == "/print_t":
			await print_t(message)
		else:
			# Если полученное число неправильное, то выводится сообщение об ошибке
			print(err)
			await bot.send_message(message.chat.id, "❌ Неверное значение! Укажите число из списка")
	else:
		# Если try выполнился, то запускается else (код ниже)
		# Если указанное число попадает в существующий диапазон, то переходим в режим установки состояния
		if st.get_num_all_rows() >= number_template > 0:
			# Сохраняем значение, чтобы можно было его использовать в другом месте
			await state.update_data(NUMBER=number_template)
			await bot.send_message(message.chat.id, "2️⃣ Укажите состояние шаблона\nЕсли включить, то 1(один). Если отключить, то 0(ноль)")
			await state.set_state(CS.STATE_T2)
		else:
			await bot.send_message(message.chat.id, "❌ Такой номер в базе отсутствует. Введите корректный!")


@dp.message_handler(state=CS.STATE_T2)
async def state_t_state(message: types.Message, state: FSMContext):
	"""Установка нового состояния для шаблона"""
	msg = message.text
	try:
		input_state = int(msg)
		# Проверяем, чтобы при вводе было значение только 0(ноль) или 1(один)
		if input_state not in {0, 1}:
			await bot.send_message(message.chat.id, "❌ Неверное состояние! Укажите число 1 или 0")
	except ValueError as err:
		# Если полученное число неправильное, то выводится сообщение об ошибке
		print(err)
		await bot.send_message(message.chat.id, "❌ Неверное состояние! Укажите число 1 или 0")
	else:
		# Извлекаем номер шаблона
		data = await state.get_data()
		number_template = data.get("NUMBER")

		new_state = True if input_state == 1 else (False if input_state == 0 else None)
		st.set_states_template(number_template, new_state)
		await bot.send_message(message.chat.id, "✅ Состояние шаблона успешно изменено!")
		await state.set_state(CS.AVAILABLE)


@dp.message_handler(commands=['print_t'], state=[
	CS.AVAILABLE, CS.ADD_T1, CS.ADD_T2,
	CS.ADD_B1, CS.ADD_B2, CS.DEL_T, CS.DEL_B])
async def print_t(message: types.Message):
	final_msg = "Список шаблонов\n🟢 - шаблон включен\n🔴 - шаблон выключен\n\n"
	for line in st.get_all_from_table():
		# Если шаблон включен(True), то выводим зелёный кружок. А если отключен(False) то выводим красный кружок
		included = str(line[3])
		circle = "🟢" if included == "True" else ("🔴" if included == "False" else None)
		final_msg += f"{line[0]}. {circle} {line[1]} - {line[2]}\n"

	await bot.send_message(message.chat.id, final_msg)


@dp.message_handler(commands=['add_b'], state=CS.AVAILABLE)
async def add_b(message: types.Message, state: FSMContext):
	await bot.send_message(message.chat.id, "1️⃣ Введите слово ключ для чёрного списка")
	await state.set_state(CS.ADD_B1)


@dp.message_handler(state=CS.ADD_B1)
async def add_b_key(message: types.Message, state: FSMContext):
	wordkey = message.text
	# Сохраняем полученное значение
	await state.update_data(WORDKEY=wordkey)
	await state.set_state(CS.ADD_B2)
	await bot.send_message(message.chat.id, "✅ Слово ключ - сохранён!")
	await bot.send_message(message.chat.id, "2️⃣ Введите URL для добавления в чёрный список")


@dp.message_handler(state=CS.ADD_B2)
async def add_b_url(message: types.Message, state: FSMContext):
	# Извлекаем wordkey
	data = await state.get_data()
	wordkey = data.get("WORDKEY")
	# Получаем url
	url = message.text
	bl.create_new_row(wordkey, url)
	await bot.send_message(message.chat.id, "✅ Исключение добавлено в чёрный список!")
	await state.set_state(CS.AVAILABLE)


@dp.message_handler(commands=['del_b'], state=CS.AVAILABLE)
async def del_b_msg(message: types.Message, state: FSMContext):
	await bot.send_message(message.chat.id, "Укажите номер исключения для удаления.\nЧтобы узнать номер введите /print_b")
	await state.set_state(CS.DEL_B)


@dp.message_handler(state=CS.DEL_B)
async def del_b_input(message: types.Message, state: FSMContext):
	""" """
	msg = message.text

	try:
		number_exception = int(msg)
	except ValueError as err:
		# Если вместо числа принимается команда /print_b, то запускаем функцию print_b, без выполнения остального кода
		if msg == "/print_b":
			await print_b(message)
		else:
			# Если полученное число неправильное, то выводится сообщение об ошибке
			print(err)
			await bot.send_message(message.chat.id, "❌ Неверное значение! Укажите число из чёрного списка")
	else:
		# Если try выполнился, то запускается else (код ниже)
		if bl.get_num_all_rows() >= number_exception > 0:
			bl.delete_row_by_number(number_exception)
			await bot.send_message(message.chat.id, "✅ Номер исключения успешно удалён!")
			await state.set_state(CS.AVAILABLE)
		else:
			await bot.send_message(message.chat.id, "❌ Такой номер в чёрном списке отсутствует. Введите корректный!")


@dp.message_handler(commands=['state_b'], state=CS.AVAILABLE)
async def state_b(message: types.Message, state: FSMContext):
	await bot.send_message(message.chat.id, "1️⃣ Укажите номер исключения.\nЧтобы узнать номер введите /print_b")
	await state.set_state(CS.STATE_B1)


@dp.message_handler(state=CS.STATE_B1)
async def state_b_number(message: types.Message, state: FSMContext):
	msg = message.text

	try:
		number_exception = int(msg)
	except ValueError as err:
		# Если вместо числа принимается команда /print_t, то запускаем функцию print_t, без выполнения остального кода
		if msg == "/print_t":
			await print_t(message)
		else:
			# Если полученное число неправильное, то выводится сообщение об ошибке
			print(err)
			await bot.send_message(message.chat.id, "❌ Неверное значение! Укажите число из списка")
	else:
		# Если try выполнился, то запускается else (код ниже)
		# Если указанное число попадает в существующий диапазон, то переходим в режим установки состояния
		if bl.get_num_all_rows() >= number_exception > 0:
			# Сохраняем значение, чтобы можно было его использовать в другом месте
			await state.update_data(NUMBER=number_exception)
			await bot.send_message(message.chat.id, "2️⃣ Укажите состояние исключения\nЕсли включить, то 1(один). Если отключить, то 0(ноль)")
			await state.set_state(CS.STATE_B2)
		else:
			await bot.send_message(message.chat.id, "❌ Такой номер в базе отсутствует. Введите корректный!")


@dp.message_handler(state=CS.STATE_B2)
async def state_b_state(message: types.Message, state: FSMContext):
	"""Установка нового состояния для исключения"""
	msg = message.text
	try:
		input_state = int(msg)
		# Проверяем, чтобы при вводе было значение только 0(ноль) или 1(один)
		if input_state not in {0, 1}:
			await bot.send_message(message.chat.id, "❌ Неверное состояние! Укажите число 1 или 0")
	except ValueError as err:
		# Если полученное число неправильное, то выводится сообщение об ошибке
		print(err)
		await bot.send_message(message.chat.id, "❌ Неверное состояние! Укажите число 1 или 0")
	else:
		# Извлекаем номер исключения
		data = await state.get_data()
		number_exception = data.get("NUMBER")

		new_state = True if input_state == 1 else (False if input_state == 0 else None)
		bl.set_states_template(number_exception, new_state)
		await bot.send_message(message.chat.id, "✅ Состояние исключения успешно изменено!")
		await state.set_state(CS.AVAILABLE)


@dp.message_handler(commands=['print_b'], state=[
	CS.AVAILABLE, CS.ADD_T1, CS.ADD_T2,
	CS.ADD_B1, CS.ADD_B2, CS.DEL_T, CS.DEL_B])
async def print_b(message: types.Message):
	final_msg = "Чёрный список\n🟢 - исключение включено\n🔴 - исключение выключено\n\n"
	for line in bl.get_all_from_table():
		# Если исключение включено(True), то выводим зелёный кружок. А если отключено(False) то выводим красный кружок
		included = str(line[3])
		circle = "🟢" if included == "True" else ("🔴" if included == "False" else None)
		final_msg += f"{line[0]}. {circle} {line[1]} - {line[2]}\n"

	await bot.send_message(message.chat.id, final_msg)


# Нереализованная функция
# @dp.message_handler(commands=['set_time'], state=CS.AVAILABLE)
# async def msg_request_interval(message: types.Message, state: FSMContext):
# 	await bot.send_message(message.chat.id, "Введите интервал запросов ")
# 	await state.set_state(CS.SET_TIME)


# # Нереализованная функция
# @dp.message_handler(state=CS.SET_TIME)
# async def set_request_interval(message: types.Message, state: FSMContext):
# 	delay = int(message.text)
# 	if 60 > delay > 0:
# 		Main.set_time(delay)
# 		await bot.send_message(message.chat.id, """✅ Новый интервал установлен """)
# 		await state.set_state(CS.AVAILABLE)


if __name__ == "__main__":
	executor.start_polling(dp, skip_updates=True)


# start - Запустить бота
# help - Помощь
# set_time - Установить задержку запросов
# add_t - Добавить шаблон поиска
# del_t - Удалить шаблон поиска
# state_t - Установить состояние для шаблона
# print_t - Вывести все шаблоны поиска
# add_b - Добавить исключение в чёрный список
# del_b - Удалить исключение из чёрного списка
# state_b - Установить состояние для исключения
# print_b - Вывести все исключения из чёрного списка
