import asyncio
import logging
import sys
from os import environ

from aiogram import Bot, Dispatcher
from aiogram.client.bot import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

# Определение класса состояний.
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

from data import BlackList, SearchTemplates, VisitsList
from parsing import get_param_for_msg

# Извлекаем из виртуальной среды переменные окружения. API токен и id пользователя
telegram_key = environ.get("API_TELEGRAM_KEY")
user_id = int(environ.get("USER_ID"))

# Создание объекта DefaultBotProperties с нужными параметрами
default_properties = DefaultBotProperties(parse_mode="HTML")
# Подключаемся к боту
bot = Bot(token=telegram_key, session=AiohttpSession(timeout=60), default=default_properties)

# global st, bl, vl, telegram_key, user_id, bot, storage, dp
st = SearchTemplates()
bl = BlackList()
vl = VisitsList()

# Инициализируем диспетчер с хранилищем состояний в памяти
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


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
	UPDATE_TIME = State()
	CLEAR_VISITS = State()


min_delay = 0
max_delay = 180
current_delay = 10

start = False


# noinspection PyPep8Naming
async def is_user_ID(message: Message):
	return message.from_user.id == user_id


# TODO Удалить повторяющийся код. Оптимизировать функции


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
	# Только пользователь с допустимым ID сможет получить доступ к боту
	if await is_user_ID(message):
		global start
		start = True

		await message.answer("🖐 Hola! \nВведите /help для доступа к командам")
		await state.set_state(CS.AVAILABLE)
	else:
		await message.answer(
			"❌  Please leave this chat. You're an unregistered user\nПрошу покинуть этот чат. Вы незарегистрированный пользователь"
		)


@dp.message(Command("help"), CS.AVAILABLE)
async def command_help(message: Message):
	await message.answer("""
Общие настройки
/update_time - Установить время обновления вакансий (в минутах)
/clear_visits - Установить время очистки списка посещений (в часах)
/print_s - Вывести информацию об общих настройках

Шаблоны поиска
/add_t - Добавить шаблон поиска
/del_t - Удалить шаблон поиска
/state_t - Установить состояние для шаблона
/print_t - Вывести все шаблоны поиска

Чёрный список
/add_b - Добавить исключение в чёрный список
/del_b - Удалить исключение из чёрного списка
/state_b - Установить состояние для исключения
/print_b - Вывести все исключения из чёрного списка
""")


@dp.message(Command("add_t"), CS.AVAILABLE)
async def add_t(message: Message, state: FSMContext):
	await message.answer("1️⃣ Введите слово ключ шаблона")
	await state.set_state(CS.ADD_T1)


@dp.message(CS.ADD_T1)
async def add_t_key(message: Message, state: FSMContext):
	wordkey = message.text
	# Проверка на уникальность. Существует ли такое слово ключ в базе шаблонов
	if wordkey in st.get_col_by_name("key"):
		await message.answer("❌ Такое слово ключ уже существует. Введите другое слово ключ")
	else:
		# Сохраняем полученное значение
		await state.update_data(WORDKEY=wordkey)
		await state.set_state(CS.ADD_T2)
		await message.answer("✅ Слово ключ - сохранён!")
		await message.answer("2️⃣ Введите URL для добавления в базу")


@dp.message(CS.ADD_T2)
async def add_t_url(message: Message, state: FSMContext):
	# Извлекаем wordkey
	data = await state.get_data()
	wordkey = data.get("WORDKEY")
	# Получаем URL
	url = message.text
	st.create_new_row(wordkey, url)
	await message.answer("✅ Новый шаблон добавлен в базу!")
	await state.set_state(CS.AVAILABLE)


@dp.message(Command("del_t"), CS.AVAILABLE)
async def del_t_msg(message: Message, state: FSMContext):
	await message.answer("Укажите номер шаблона.\nЧтобы узнать номер введите /print_t")
	await state.set_state(CS.DEL_T)


@dp.message(CS.DEL_T)
async def del_t_input(message: Message, state: FSMContext):
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
			await message.answer("❌ Неверное значение! Укажите число из списка")
	else:
		# Если try выполнился, то запускается else (код ниже)
		if st.get_num_all_rows() >= number_template > 0:
			key_template = st.get_key_by_number(number_template)
			# Удаляем записи из списка посещений по ключу шаблона
			vl.delete_rows_by_key(key_template)
			# Удаляем сам шаблон поиска. Указываем его номер.
			# Удаляем через номер, так как в боте удобнее писать число, а не целый ключ
			st.delete_row_by_number(number_template)
			await message.answer("✅ Номер шаблона успешно удалён!")
			await state.set_state(CS.AVAILABLE)
		else:
			await message.answer("❌ Такой номер в базе отсутствует. Введите корректный!")


@dp.message(Command("state_t"), CS.AVAILABLE)
async def state_t(message: Message, state: FSMContext):
	await message.answer("1️⃣ Укажите номер шаблона.\nЧтобы узнать номер введите /print_t")
	await state.set_state(CS.STATE_T1)


@dp.message(CS.STATE_T1)
async def state_t_number(message: Message, state: FSMContext):
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
			await message.answer("❌ Неверное значение! Укажите число из списка")
	else:
		# Если try выполнился, то запускается else (код ниже)
		# Если указанное число попадает в существующий диапазон, то переходим в режим установки состояния
		if st.get_num_all_rows() >= number_template > 0:
			# Сохраняем значение, чтобы можно было его использовать в другом месте
			await state.update_data(NUMBER=number_template)
			await message.answer(
				"2️⃣ Укажите состояние шаблона\nЕсли включить, то 1(один). Если отключить, то 0(ноль)"
			)
			await state.set_state(CS.STATE_T2)
		else:
			await message.answer("❌ Такой номер в базе отсутствует. Введите корректный!")


@dp.message(CS.STATE_T2)
async def state_t_state(message: Message, state: FSMContext):
	"""Установка нового состояния для шаблона."""
	msg = message.text
	try:
		input_state = int(msg)
		# Проверяем, чтобы при вводе было значение только 0(ноль) или 1(один)
		if input_state not in {0, 1}:
			await message.answer("❌ Неверное состояние! Укажите число 1 или 0")
			return
	except ValueError as err:
		# Если полученное число неправильное, то выводится сообщение об ошибке
		print(err)
		await message.answer("❌ Неверное состояние! Укажите число 1 или 0")
		return

	data = await state.get_data()
	number_template = data.get("NUMBER")
	# Извлекаем номер шаблона

	new_state = input_state == 1
	st.set_states_template(number_template, new_state)
	await message.answer("✅ Состояние шаблона успешно изменено!")
	await state.set_state(CS.AVAILABLE)


@dp.message(Command("print_t"), CS.AVAILABLE)
async def print_t(message: Message):
	header = "Список шаблонов\n🟢 - шаблон включен\n🔴 - шаблон выключен\n\n"
	final_msg_part = header

	for line in st.get_all_from_table():
		included = str(line[3])
		circle = "🟢" if included == "True" else "🔴"
		line_to_add = f"{line[0]}. {circle} {line[1]} - {line[2]}\n"

		# Если добавление новой строки превысит лимит в 4096, отправляем текущую часть и начинаем новую.
		if len(final_msg_part) + len(line_to_add) > 4096:
			await message.answer(final_msg_part)
			final_msg_part = ""  # Сбрасываем для следующего сообщения

		final_msg_part += line_to_add
		
	# Отправляем оставшуюся часть сообщения, если она есть
	# (и если она не состоит только из заголовка в случае пустого списка)
	if final_msg_part and final_msg_part != header:
		await message.answer(final_msg_part)
	# Если список был пуст, отправляем только заголовок
	elif not st.get_all_from_table():
		await message.answer(header)


@dp.message(Command("add_b"), CS.AVAILABLE)
async def add_b(message: Message, state: FSMContext):
	await message.answer("1️⃣ Введите слово ключ для чёрного списка")
	await state.set_state(CS.ADD_B1)


@dp.message(CS.ADD_B1)
async def add_b_key(message: Message, state: FSMContext):
	wordkey = message.text
	# Сохраняем полученное значение
	await state.update_data(WORDKEY=wordkey)
	await state.set_state(CS.ADD_B2)
	await message.answer("✅ Слово ключ - сохранён!")
	await message.answer("2️⃣ Введите URL для добавления в чёрный список")


@dp.message(CS.ADD_B2)
async def add_b_url(message: Message, state: FSMContext):
	# Извлекаем wordkey
	data = await state.get_data()
	wordkey = data.get("WORDKEY")
	# Получаем url
	url = message.text
	bl.create_new_row(wordkey, url)
	await message.answer("✅ Исключение добавлено в чёрный список!")
	await state.set_state(CS.AVAILABLE)


@dp.message(Command("del_b"), CS.AVAILABLE)
async def del_b_msg(message: Message, state: FSMContext):
	await message.answer(
		"Укажите номер исключения для удаления.\nЧтобы узнать номер введите /print_b"
	)
	await state.set_state(CS.DEL_B)


@dp.message(CS.DEL_B)
async def del_b_input(message: Message, state: FSMContext):
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
			await message.answer("❌ Неверное значение! Укажите число из чёрного списка")
	else:
		# Если try выполнился, то запускается else (код ниже)
		if bl.get_num_all_rows() >= number_exception > 0:
			bl.delete_row_by_number(number_exception)
			await message.answer("✅ Номер исключения успешно удалён!")
			await state.set_state(CS.AVAILABLE)
		else:
			await message.answer("❌ Такой номер в чёрном списке отсутствует. Введите корректный!")


@dp.message(Command("state_b"), CS.AVAILABLE)
async def state_b(message: Message, state: FSMContext):
	await message.answer("1️⃣ Укажите номер исключения.\nЧтобы узнать номер введите /print_b")
	await state.set_state(CS.STATE_B1)


@dp.message(CS.STATE_B1)
async def state_b_number(message: Message, state: FSMContext):
	msg = message.text

	try:
		number_exception = int(msg)
	except ValueError as err:
		# Если вместо числа принимается команда /print_b, то запускаем функцию /print_b, без выполнения остального кода
		if msg == "/print_b":
			await print_b(message)
		else:
			# Если полученное число неправильное, то выводится сообщение об ошибке
			print(err)
			await message.answer("❌ Неверное значение! Укажите число из списка")
	else:
		# Если try выполнился, то запускается else (код ниже)
		# Если указанное число попадает в существующий диапазон, то переходим в режим установки состояния
		if bl.get_num_all_rows() >= number_exception > 0:
			# Сохраняем значение, чтобы можно было его использовать в другом месте
			await state.update_data(NUMBER=number_exception)
			await message.answer(
				"2️⃣ Укажите состояние исключения\nЕсли включить, то 1(один). Если отключить, то 0(ноль)"
			)
			await state.set_state(CS.STATE_B2)
		else:
			await message.answer("❌ Такой номер в базе отсутствует. Введите корректный!")


@dp.message(CS.STATE_B2)
async def state_b_state(message: Message, state: FSMContext):
	"""Установка нового состояния для исключения."""
	msg = message.text
	try:
		input_state = int(msg)
		# Проверяем, чтобы при вводе было значение только 0(ноль) или 1(один)
		if input_state not in {0, 1}:
			await message.answer("❌ Неверное состояние! Укажите число 1 или 0")
			return
	except ValueError as err:
		# Если полученное число неправильное, то выводится сообщение об ошибке
		print(err)
		await message.answer("❌ Неверное состояние! Укажите число 1 или 0")
		return

	data = await state.get_data()
	number_exception = data.get("NUMBER")
	# Извлекаем номер исключения

	new_state = input_state == 1
	bl.set_states_template(number_exception, new_state)
	await message.answer("✅ Состояние исключения успешно изменено!")
	await state.set_state(CS.AVAILABLE)


@dp.message(Command("print_b"), CS.AVAILABLE)
async def print_b(message: Message):
	final_msg = "Чёрный список\n🟢 - исключение включено\n🔴 - исключение выключено\n\n"
	for line in bl.get_all_from_table():
		# Если исключение включено(True), то выводим зелёный кружок. А если отключено(False) то выводим красный кружок
		included = str(line[3])
		circle = "🟢" if included == "True" else "🔴"
		final_msg += f"{line[0]}. {circle} {line[1]} - {line[2]}\n"

	await message.answer(final_msg)


@dp.message(Command("update_time"), CS.AVAILABLE)
async def msg_update_time(message: Message, state: FSMContext):
	await message.answer(
		f"Введите время обновления вакансий (в минутах, от {min_delay + 1} до {max_delay})\nЧтобы узнать текущее время обновления, введите /print_s"
	)
	await state.set_state(CS.UPDATE_TIME)


@dp.message(CS.UPDATE_TIME)
async def set_update_time(message: Message, state: FSMContext):
	msg = message.text
	global current_delay
	try:
		delay = int(msg)
		if min_delay < delay < max_delay:
			current_delay = delay
			await message.answer("✅ Время обновления вакансий успешно изменено!")
			await state.set_state(CS.AVAILABLE)
		else:
			await message.answer(
				f"❌ Некорректное значение! Введите число от {min_delay + 1} до {max_delay} минут"
			)
	except ValueError as err:
		if msg == "/print_s":
			await print_s(message)
		else:
			print(err)
			await message.answer(
				f"❌ Некорректное значение! Введите число от {min_delay + 1} до {max_delay} минут"
			)


@dp.message(Command("clear_visits"), CS.AVAILABLE)
async def msg_clear_visits(message: Message, state: FSMContext):
	await message.answer(
		"Введите время очистки списка посещений (в часах, больше 0)\nЧтобы узнать текущее время очистки, введите /print_s"
	)
	await state.set_state(CS.CLEAR_VISITS)


@dp.message(CS.CLEAR_VISITS)
async def set_clear_visits(message: Message, state: FSMContext):
	msg = message.text
	try:
		hours = int(msg)
		if hours > 0:
			vl.set_time_clear(hours)
			await message.answer("✅ Время очистки списка посещений успешно изменено!")
			await state.set_state(CS.AVAILABLE)
		else:
			await message.answer("❌ Некорректное значение! Введите число больше нуля")
	except ValueError as err:
		if msg == "/print_s":
			await print_s(message)
		else:
			print(err)
			await message.answer("❌ Некорректное значение! Введите число больше нуля")


@dp.message(Command("print_s"), CS.AVAILABLE)
async def print_s(message: Message):
	await message.answer(
		f"Общие настройки\nВремя обновления вакансий: {current_delay} минут\nВремя очистки списка посещений: {vl.get_time_clear()} часов"
	)


#############################
# PARSING


async def send_to_user(param):
	vacancy_name_emoji = "🎫"
	wage_emoji = "💰"
	name_company_emoji = "🏢"
	metro_emoji = "Ⓜ️"
	address_emoji = "🌍"

	# Формируем сообщение
	text_message = f"""#{param["key"]}
{vacancy_name_emoji} <a href="{param["url"]}">{param["vacancy_name"]}</a>
{wage_emoji} {param["wage"]}
{name_company_emoji} {param["name_company"]}
{metro_emoji} {param["metro"]}
{address_emoji} {param["city"]}, {param["street"]} (<a href="{param["yandex_url"]}">YandexMap</a>, <a href="{param["google_url"]}">GoogleMap</a>)"""

	# Удаляем табы из сообщения, так как мешают
	text_message = text_message.replace("\t", "")
	# Заменяем неразрывные пробелы на обычные
	text_message = text_message.replace("\u00a0", " ")

	# Используем parse_mode='HTML', так как при Markdown нужно маскировать '(' на '\\('
	# Это приводит к нарушению работы ссылок в сообщении
	await bot.send_message(user_id, text_message, parse_mode="HTML")


async def background_task():
	while True:
		if start:
			async for all_param in get_param_for_msg():
				await send_to_user(all_param)

			await asyncio.sleep(current_delay * 60)
		else:
			await asyncio.sleep(1)


async def main():
	# Запускаем фоновую задачу
	asyncio.create_task(background_task())

	await dp.start_polling(bot)


if __name__ == "__main__":
	logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
	asyncio.run(main())
