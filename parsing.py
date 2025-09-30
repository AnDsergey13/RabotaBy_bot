import asyncio

import aiohttp
from bs4 import BeautifulSoup

from data import BlackList, SearchTemplates, VisitsList

st = SearchTemplates()
bl = BlackList()
vl = VisitsList()

basic_url = {
	"yandex": "https://yandex.com/maps/?text=",
	"google": "https://www.google.com/maps/place/",
}

items_on_page = "&items_on_page=20"
pages = "&page="
# Чтобы обойти ошибку 404, добавляем заголовок. Как будто запрос делает реальный пользователь
headers = {
	"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
}


def get_list_keys_and_templates():
	original_list = st.get_all_from_table()
	# Оставляем только те шаблоны, которые нужны для запросов
	filtered_list = [item for item in original_list if item[-1] is True]
	# Оставляем только ключи и адреса шаблонов
	keys_and_templates = [item[1:3] for item in filtered_list]
	return keys_and_templates


def get_black_list():
	original_list = bl.get_all_from_table()
	# Оставляем только те исключения, которые нужны для проверки
	filtered_list = [item for item in original_list if item[-1] is True]
	# Оставляем только адреса исключений
	black_list = [item[2] for item in filtered_list]
	return black_list


def get_visit_list():
	visit_list = vl.get_col_by_name("url")
	# Оставляем только адреса шаблонов
	return visit_list


def get_number_vacancies(soup):
	""" [<h1 class="magritte-text___gMq2l_7-0-3 magritte-text-overflow___UBrTV_7-0-3 magritte-text-typography-small___QbQNX_7-0-3 magritte-text-style-primary___8SAJp_7-0-3" data-qa="title"><span>Найдено 34 вакансии</span> «ИИ»</h1>] """
	containers = soup.findAll("h1", {"data-qa": "title"})
	if not containers:
		return 0
	
	text_string = containers[0].get_text(strip=True)
	# print(f"Текст для анализа: {text_string}")
	
	# Убираем ограничение в 9 символов и просто извлекаем все цифры
	number_str = ''.join(filter(str.isdigit, text_string))
	
	if number_str:
		return int(number_str)
	else:
		return 0


def get_num_pages(num_vacancies):
	std_vacancies_per_page = 20
	number_pages = num_vacancies / std_vacancies_per_page
	# Считаем, сколько будет страниц с результатами
	# Если целое количество, то так и возвращаем
	# Но если дробное, то возвращаем количество + 1

	if number_pages % 1 != 0:
		return int(number_pages) + 1
	else:
		return int(number_pages)


def get_all_vacancies_on_page(soup):
	containers = soup.findAll(
		"h2", class_="bloko-header-section-2", attrs={"data-qa": "bloko-header-2"}
	)
	list_url_vacancy = []
	for container in containers:
		link = container.find("a")
		if link is not None:
			href = link["href"]
			# Обрезаем лишнее в адресе
			url_vacancy = href.split("?")[0]
			list_url_vacancy.append(url_vacancy)
	return list_url_vacancy


async def get_all_vacancies_on_all_pages(session, url, max_number_pages):
	all_vacancies = []
	for num_page in range(max_number_pages):
		url_full = url + items_on_page + pages + str(num_page)
		try:
			async with session.get(url_full, headers=headers) as response:
				if response.status != 200:
					print(f"Ошибка при получении {url_full}: Статус {response.status}")
					continue
				page_text = await response.text()
			soup = BeautifulSoup(page_text, "html.parser")
			all_vacancies += get_all_vacancies_on_page(soup)
		except (aiohttp.ClientError, asyncio.TimeoutError) as e:
			print(f"Сетевая ошибка при получении страницы {num_page} для {url}: {e}")
			continue
	return all_vacancies


# Работа со страницами вакансий
def get_map_url(name_map: str, string_search):
	# Удаляем все запятые из строки
	string_without_commas = string_search.replace(",", "")
	# Заменяем все пробелы знаком '+' (плюс)
	string_with_pluses = string_without_commas.replace(" ", "+")
	# Формируем адрес из общего шаблона и того, что нужно искать
	url = basic_url[name_map] + string_with_pluses
	return url


def get_vacancy_name(soup):
	# Перебираем несколько возможных атрибутов для имени вакансии
	selectors = [{"data-qa": "vacancy-title"}, {"data-qa": "title"}]

	for selector in selectors:
		vacancy_name = soup.find("h1", selector)
		if vacancy_name is not None:
			return vacancy_name.get_text(strip=True)
	return "?"


def get_wage(soup):
	wage = soup.find("div", {"data-qa": "vacancy-salary"})
	# Если информация о ЗП не существует во всех вариантах, то выводим "?"
	return wage.get_text() if wage else "?"


def get_name_company(soup):
	name_company = soup.find("a", {"data-qa": "vacancy-company-name"})
	# Если имени компании не существует, то выводим "?"
	return name_company.get_text() if name_company else "?"


def get_the_rest(soup, name_company):
	full_address = soup.find("span", {"data-qa": "vacancy-view-raw-address"})
	if full_address:
		general_string = full_address.get_text()

		# Извлекаем город
		city = general_string.split(",")[0]

		# Извлекаем станции метро
		metro_stations = [
			station.get_text()
			for station in full_address.find_all("span", {"class": "metro-station"})
		]

		# Извлекаем улицу с домом
		street_with_house = ", ".join(general_string.rsplit(", ", 2)[1:])

		if not metro_stations:
			# Если метро не было указано, то выводим "?"
			metro_stations = "?"

		if street_with_house:
			# Поиск по адресу
			search_string = f"{city} {street_with_house}"
			yandex_url = get_map_url("yandex", search_string)
			google_url = get_map_url("google", search_string)
		else:
			# Поиск по названию компании
			yandex_url = get_map_url("yandex", name_company)
			google_url = get_map_url("google", name_company)
	else:
		city, street_with_house, metro_stations = "?", "?", "?"
		yandex_url = get_map_url("yandex", name_company)
		google_url = get_map_url("google", name_company)

	return city, street_with_house, metro_stations, yandex_url, google_url


# Работа со страницами вакансий
async def get_param_for_msg():
	keys_and_urls = get_list_keys_and_templates()
	
	timeout = aiohttp.ClientTimeout(total=30)
	async with aiohttp.ClientSession(timeout=timeout) as session:
		for key, url in keys_and_urls:
			# Перед всеми проверками и запросами очищаем список посещений, если есть старые вакансии
			# Например: Если дата посещённой ссылки больше заданного времени, то она оттуда удаляется
			vl.delete_rows_after_time(key)
			
			page_text = None
			try:
				async with session.get(url, headers=headers) as response:
					if response.status != 200:
						print(f"Ошибка при получении {url}: Статус {response.status}")
						continue
					page_text = await response.text()
			except (aiohttp.ClientError, asyncio.TimeoutError) as e:
				print(f"Сетевая ошибка при получении {url}: {e}")
				continue

			if not page_text:
				continue

			soup = BeautifulSoup(page_text, "html.parser")

			# Получаем количество найденных вакансий
			number_results = get_number_vacancies(soup)
			# Считаем, сколько будет страниц
			max_number_pages = get_num_pages(number_results)

			# Получаем все URLs из выдачи rabota.by
			all_urls = await get_all_vacancies_on_all_pages(session, url, max_number_pages)

			# Получаем все URLs из чёрного списка
			black_list = get_black_list()

			# Удаляем из выдачи те URLs, которые находятся в чёрном списке
			all_urls = list(set(all_urls) - set(black_list))

			# Получаем список уже ранее выведенных вакансий (список посещений)
			visit_list = get_visit_list()
			# Получаем список URLs, которые ранее не выводились в боте,
			# то есть удаляем из выдачи URLs из списка посещений
			all_urls = list(set(all_urls) - set(visit_list))

			if all_urls:
				# После того как прошли все проверки, записываем оставшиеся URLs (новые) в список посещений
				for url_vacancy in all_urls:
					vl.create_new_row(key, url_vacancy)

				# Заходим на каждый URL и достаём оттуда информацию о вакансии
				# Название вакансии, ЗП, название фирмы, адрес и прочее
				for url_vacancy in all_urls:
					try:
						async with session.get(url_vacancy, headers=headers) as response:
							if response.status != 200:
								print(f"Ошибка при получении вакансии {url_vacancy}: Статус {response.status}")
								continue
							page_text2 = await response.text()
						soup2 = BeautifulSoup(page_text2, "html.parser")

						await asyncio.sleep(2.5)  # Возможно, стоит заменить на асинхронный запрос

						vacancy_name = get_vacancy_name(soup2)
						wage = get_wage(soup2)
						name_company = get_name_company(soup2)

						city, street, metro_stations, yandex_url, google_url = get_the_rest(
							soup2, name_company
						)

						# Так как в названии ключа могут быть пробелы, которые обрезают работу тега в сообщении,
						# заменяем все пробелы на нижние подчёркивания
						key_formatted = key.replace(" ", "_")

						if isinstance(metro_stations, list):
							metro = ", ".join(metro_stations)
						else:
							metro = metro_stations

						param = {
							"key": key_formatted,
							"url": url_vacancy,
							"vacancy_name": vacancy_name,
							"wage": wage,
							"name_company": name_company,
							"city": city,
							"street": street,
							"metro": metro,
							"yandex_url": yandex_url,
							"google_url": google_url,
						}

						yield param
					except (aiohttp.ClientError, asyncio.TimeoutError) as e:
						print(f"Сетевая ошибка при получении вакансии {url_vacancy}: {e}")
						continue