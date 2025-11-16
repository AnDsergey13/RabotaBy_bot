# import threading
import logging
import sys
from datetime import datetime, timedelta
from os import environ

import psycopg2

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
logger = logging.getLogger(__name__)


class Settings:
	"""Manage database settings.

	A class for managing database connection settings
	and constructing SQL queries for table creation (database schema).
	It interacts with environment variables to retrieve connection parameters
	and provides methods for table and column management.
	"""

	# Get database connection parameters from environment variables
	__db_host = environ.get("DB_HOST")
	__db_port = environ.get("DB_PORT")
	__db_name = environ.get("DB_NAME")
	__db_user = environ.get("DB_USER")
	__db_password = environ.get("DB_PASSWORD")

	__db_connection_parameters = {
		"host": __db_host,
		"port": __db_port,
		"database": __db_name,
		"user": __db_user,
		"password": __db_password,
	}

	# Define database schema

	# Define columns with their types
	# Тип хранения значений (кортеж), не изменять. По нему происходит поиск названия столбцов
	__number = ("number", "INTEGER NOT NULL")
	__key = ("key", "TEXT NOT NULL")
	__url = ("url", "TEXT NOT NULL")
	__lastDateTime = ("last_date_time", "TIMESTAMP NOT NULL")
	__included = ("included", "BOOLEAN NOT NULL")

	__header = "CREATE TABLE IF NOT EXISTS "

	# Define tables schemas
	__database_structure = {
		"ST": {
			"name_table": "search_templates",
			"column_1": __number,
			"column_2": __key,
			"column_3": __url,
			"column_4": __included,
		},
		"BL": {
			"name_table": "black_list",
			"column_1": __number,
			"column_2": __key,
			"column_3": __url,
			"column_4": __included,
		},
		"VL": {
			"name_table": "visits_list",
			"column_1": __lastDateTime,
			"column_2": __key,
			"column_3": __url,
		},
	}

	@classmethod
	def get_name_database(cls):
		"""Return the name of the database.

		Examples:
		>>> Settings.get_name_database()
		...
		"""
		return cls.__db_name

	@classmethod
	def get_db_connection_parameters(cls, without_database=False):
		"""Return a dictionary with database creation / connection parameters.

		Args:
			without_database (bool): If True, the returned dictionary excludes the "database" key.

		Examples:
		>>> Settings.get_db_connection_parameters()
		{'host': None, 'port': None, 'database': None, 'user': None, 'password': None}
		>>> Settings.get_db_connection_parameters(without_database=True)
		{'host': None, 'port': None, 'user': None, 'password': None}
		"""
		if without_database:
			# Создаём копию, чтобы не модифицировать основной словарь
			copy_db_conn_param = cls.__db_connection_parameters.copy()
			# Удаляем лишнее
			del copy_db_conn_param["database"]
			# Возвращаем копию
			return copy_db_conn_param

		return cls.__db_connection_parameters

	@classmethod
	def get_list_codes_tables(cls):
		"""Return a list of all table codes defined in the schema.

		Examples:
		>>> sorted(Settings.get_list_codes_tables())
		['BL', 'ST', 'VL']
		"""
		return list(cls.__database_structure.keys())

	@classmethod
	def is_column_present(cls, name_column):
		"""Check if the specified column name exists in the predefined columns.

		Args:
			name_column (str): The name of the column.

		Returns:
			str: The column name if present; otherwise, prints an error message.

		Examples:
		>>> Settings.is_column_present("url")
		'url'

		Notes:
			Извлекаем из текущего класса, все переменные (пары ключ-значения).
			И оставляем только кортежи
		"""
		tuple_used_names = tuple(
			value for key, value in vars(cls).items() if isinstance(value, tuple)
		)
		# Извлекаем из кортежей имена таблиц, и записываем в список
		list_all_names_columns = list([name for name, _ in tuple_used_names])

		# TODO исправить этот костыль
		if name_column in list_all_names_columns:
			# передаём дальше значение, если всё хорошо
			return name_column
		else:
			print(
				f"Некорректное имя столбца => {name_column}. Введите один из доступных => {list_all_names_columns}"
			)

	@classmethod
	def __check_table_code(cls, table_code):
		"""Check if the provided table code exists in the database structure.

		Args:
			table_code (str): The table code to check.

		Returns:
			str: The table code if valid; otherwise, prints an error message.

		Examples:
		>>> Settings._Settings__check_table_code("BL")
		'BL'
		"""
		try:
			# Делаем тестовый запрос
			_ = cls.__database_structure[table_code]
			# Если такой табличный код существует, то возвращаем его для дальнейших взаимодействий
			return table_code
		except KeyError:
			print(
				f"Некорректный код => {table_code}. Введите один из доступных => {cls.get_list_codes_tables()}"
			)

	@classmethod
	def __get_setting_for_parameter(cls, table_code):
		"""Generate column definitions for the table corresponding to table_code.

		Yields:
			str: A string in the form 'column_name data_type'.
		"""
		table_code = cls.__check_table_code(table_code)
		# Так как "name_table" в списке ключей не нужен, используем срез [1::]
		list_keys_columns = list(cls.__database_structure[table_code].keys())[1::]
		for key_column in list_keys_columns:
			# Получаем по ключу_столбца кортеж(имя и настройки). Потом собираем в строку с помощью " ".join
			# Пример вывода одной итерации: "numberVisits INTEGER NOT NULL"
			yield " ".join(cls.__database_structure[table_code][key_column])

	@classmethod
	def get_table_name_by_code(cls, table_code):
		"""Return the table name corresponding to the provided table code.

		Args:
			table_code (str): The table code (e.g., "BL").

		Examples:
		>>> Settings.get_table_name_by_code("BL")
		'black_list'
		"""
		table_code = cls.__check_table_code(table_code)
		return cls.__database_structure[table_code]["name_table"]

	@classmethod
	def get_query(cls, table_code):
		"""Construct and return an SQL query for creating the table for the given table code.

		Args:
			table_code (str): The code for the desired table.

		Returns:
			str: SQL query string.

		Examples:
		>>> Settings.get_query("BL") # doctest: +NORMALIZE_WHITESPACE
		'CREATE TABLE IF NOT EXISTS black_list
		(number INTEGER NOT NULL, key TEXT NOT NULL, url TEXT NOT NULL, included BOOLEAN NOT NULL)'
		"""
		table_code = cls.__check_table_code(table_code)
		# Формируем полную шапку запроса
		full_header = cls.__header + cls.get_table_name_by_code(table_code)

		# Получаем список всех параметров для запроса
		# Количество параметров для запроса = количество столбцов для каждой таблицы = количество запросов yield
		list_all_parameters = list(i for i in cls.__get_setting_for_parameter(table_code))

		# Создаём запрос
		# Отделяем параметры запятыми и помещаем в скобки
		# Пример результата:
		# "CREATE TABLE IF NOT EXISTS BlackList (number INTEGER NOT NULL, key TEXT NOT NULL, url TEXT NOT NULL)"
		query = f"{full_header} ({', '.join(list_all_parameters)})"

		return query


class Base:
	""" """

	def __init__(self, table_code):
		logger.info("Initializing Base class for table_code: %s", table_code)
		self.all_parameters = Settings.get_db_connection_parameters()
		self.parameters_without_database = Settings.get_db_connection_parameters(
			without_database=True
		)
		self.db_name = Settings.get_name_database()

		self.table_code = table_code
		self.name_table = Settings.get_table_name_by_code(self.table_code)
		self.number = Settings.is_column_present("number")

		# Если базы данных не существует, то создаём её
		self.database_exists()

		# Если указанной таблицы не существует, то создаём её
		self.table_exists(self.table_code)

		self.connect_to_database(self.all_parameters)

	def saving_changes(self):
		self.connection.commit()

	# noinspection PyAttributeOutsideInit
	def connect_to_database(self, parameters_database):
		"""Подключаемся к базе данных."""
		logger.debug("Connecting to database with parameters: %s", parameters_database)
		self.connection = psycopg2.connect(**parameters_database)
		self.cursor = self.connection.cursor()
		logger.info("Successfully connected to database %s.", self.db_name)

	def database_exists(self):
		"""Create a database if it doesn't exist."""
		self.connect_to_database(self.parameters_without_database)
		# noinspection PyBroadException
		try:
			self.connection.set_session(autocommit=True)
			# Создание пустой базы данных
			self.cursor.execute(f"CREATE DATABASE {self.db_name};")
			logger.info("Database '%s' created successfully.", self.db_name)
		except psycopg2.errors.DuplicateDatabase:
			# Если база данных уже создана, то ошибку не выводим,
			# а возвращаем базу данных к состоянию до выполнения запроса
			logger.exception("Database '%s' already exists, skipping creation.", self.db_name)
			self.connection.rollback()
		except Exception:
			# Обработка остальных ошибок при создании базы данных
			logger.exception("Error while creating database '%s'.", self.db_name)
			# Возвращаем базу данных к состоянию до выполнения запроса
			self.connection.rollback()
		finally:
			self.close()

	def table_exists(self, table_code):
		# Формируем таблицу по указанному коду
		self.connect_to_database(self.all_parameters)

		self.cursor.execute(Settings.get_query(table_code))
		self.saving_changes()
		logger.info("Table '%s' checked/created.", self.name_table)

	def get_num_all_rows(self):
		""" """
		# Получаем количество строк в таблице
		self.cursor.execute(f"SELECT COUNT(*) FROM {self.name_table}")
		return self.cursor.fetchone()[0]

	def get_all_from_table(self):
		"""Получить все данные таблицы."""
		print(self.name_table)
		self.cursor.execute(f"SELECT * FROM {self.name_table}")
		return self.cursor.fetchall()

	def get_col_by_name(self, col_name):
		"""Возвращает весь столбец по имени."""
		self.cursor.execute(f"SELECT {col_name} FROM {self.name_table}")
		raw_list_of_keys = self.cursor.fetchall()
		return [key[0] for key in raw_list_of_keys]

	def create_new_row(self, name_table, *args):
		"""Создаём новую строку с необходимыми значениями."""
		# Формируем параметры запроса. Пример результата -> ('%s', '%s', '%s')
		placeholders = ["%s"] * len(args)
		query_parameters = f"({', '.join(placeholders)})"

		# Формируем сам запрос
		query = f"INSERT INTO {name_table} VALUES {query_parameters}"

		# Создаём новую строку
		self.cursor.execute(query, args)
		self.saving_changes()

	def delete_row_by_value(self, name_row, value):
		"""Удаляем строку/строки по значению в столбце."""
		self.cursor.execute(f"DELETE FROM {self.name_table} WHERE {name_row}=%s", (value,))

		self.saving_changes()

	def close(self):
		"""Close the database connection."""
		self.saving_changes()
		self.cursor.close()
		self.connection.close()
		logger.info("Database '%s' connection closed successfully.", self.db_name)


class SearchTemplates(Base):
	""" """

	def __init__(self):
		super().__init__(table_code="ST")
		self.key = Settings.is_column_present("key")
		self.included = Settings.is_column_present("included")

	# noinspection PyMethodOverriding
	def create_new_row(self, new_key, new_url, is_included=True):
		number_rows = self.get_num_all_rows()
		# Создаём номер новой строки
		next_number = number_rows + 1
		# Создаём новую строку с необходимыми значениями
		super().create_new_row(self.name_table, next_number, new_key, new_url, is_included)
		self.__update_col_number()

	def delete_row_by_number(self, number):
		"""Удаляем строку по номеру."""
		super().delete_row_by_value(self.number, number)

		# Обновляем нумерацию в столбце number, так как при удалении появился разрыв в нумерации
		self.__update_col_number()

	def __update_col_number(self):
		"""Обновляем числа в столбце с числами."""
		# Запрос выберет все данные из таблицы, отсортировав строки по значению столбца number.
		self.cursor.execute(f"SELECT * FROM {self.name_table} ORDER BY {self.number}")
		rows = self.cursor.fetchall()

		# Создаём список. От 1 до максимума. Где максимум, это количество строк в таблице
		# Предположу, что использование вот такого варианта list(range(1, len(self.get_num_all_rows())+1)), забирает чуть больше ресурсов.
		# Поэтому реализовал без обращения к методу
		list_new_numbers = list(range(1, len(rows) + 1))
		# Обновите столбец 'number' с новыми значениями
		for new_number in list_new_numbers:
			# Получаем старое значение number в строке, чтобы потом его заменить на новое
			old_number = rows[new_number - 1][0]
			self.cursor.execute(
				f"UPDATE {self.name_table} SET {self.number} = %s WHERE {self.number} = %s",
				(new_number, old_number),
			)

		self.saving_changes()

	def set_states_template(self, number, new_state):
		"""Перезаписываем текущее состояние шаблона/исключения на новое.

		Допускается лишь True/False.
		Если True - то шаблон/исключение используется в поиске
		Если False - то шаблон/исключение не используется в поиске
		"""
		self.cursor.execute(
			f"UPDATE {self.name_table} SET {self.included} = %s WHERE {self.number} = %s",
			(new_state, number),
		)
		# Сортируем строки по номеру, так как после изменения состояния, строка смещается(почему?)
		self.__update_col_number()

	def get_key_by_number(self, number_template):
		"""Получить ключ зная номер шаблона."""
		self.cursor.execute(
			f"SELECT {self.key} FROM {self.name_table} WHERE {self.number} = %s;",
			(number_template,),
		)
		return self.cursor.fetchone()[0]


class BlackList(SearchTemplates):
	""" """

	def __init__(self):
		Base.__init__(self, table_code="BL")
		self.included = Settings.is_column_present("included")


class VisitsList(Base):
	""" """

	pattern = "%Y-%m-%d %H:%M:%S"

	# Указываем время в часах
	# 1 день = 24
	# 1 неделя = 168
	# 1 месяц = 4 недели = 672
	time_clear = 1344

	def __init__(self):
		super().__init__(table_code="VL")
		self.key = Settings.is_column_present("key")
		self.lastDateTime = Settings.is_column_present("last_date_time")

	@classmethod
	def get_pattern(cls):
		return cls.pattern

	def get_current_datetime(self):
		now = datetime.now()
		return now.strftime(self.get_pattern())

	# noinspection PyMethodOverriding
	def create_new_row(self, key, url):
		current_datetime = self.get_current_datetime()
		# Создаём новую строку с необходимыми значениями
		super().create_new_row(self.name_table, current_datetime, key, url)

	@classmethod
	def get_time_clear(cls):
		return cls.time_clear

	@classmethod
	def set_time_clear(cls, hours):
		cls.time_clear = hours

	def delete_rows_after_time(self, key):
		"""Удаляем строки по истечении времени с определённым ключом."""
		# Получаем текущую дату в удобном формате
		current_datetime = datetime.strptime(self.get_current_datetime(), self.get_pattern())

		# Определяем временной интервал
		time_threshold = current_datetime - timedelta(hours=self.get_time_clear())

		self.cursor.execute(
			f"DELETE FROM {self.name_table} WHERE {self.key} = %s AND {self.lastDateTime} < %s",
			(key, time_threshold),
		)

		self.saving_changes()

	def delete_rows_by_key(self, key):
		"""Удаляем строки по ключу."""
		super().delete_row_by_value(self.key, key)
