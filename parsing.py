import asyncio
import logging
import time

import aiohttp
from bs4 import BeautifulSoup

from data import BlackList, SearchTemplates, VisitsList

logger = logging.getLogger(__name__)

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


def _save_debug_html(html_content, label):
	"""Сохраняет HTML в файл для отладки селекторов."""
	filename = f"debug_{label}_{int(time.time())}.html"
	try:
		with open(filename, "w", encoding="utf-8") as f:
			f.write(html_content)
		logger.info("Debug HTML сохранён: %s (%d байт)", filename, len(html_content))
	except IOError as e:
		logger.error("Не удалось сохранить debug HTML: %s", e)


def get_list_keys_and_templates():
	original_list = st.get_all_from_table()
	logger.debug("Шаблоны из БД: %d шт.", len(original_list))
	# Оставляем только те шаблоны, которые нужны для запросов
	filtered_list = [item for item in original_list if item[-1] is True]
	# Оставляем только ключи и адреса шаблонов
	keys_and_templates = [item[1:3] for item in filtered_list]
	logger.info("Активные шаблоны: %d из %d", len(keys_and_templates), len(original_list))
	for k, u in keys_and_templates:
		logger.debug("  → key='%s', url='%s...'", k, u[:100])
	return keys_and_templates


def get_black_list():
	original_list = bl.get_all_from_table()
	# Оставляем только те исключения, которые нужны для проверки
	filtered_list = [item for item in original_list if item[-1] is True]
	# Оставляем только адреса исключений
	black_list = [item[2] for item in filtered_list]
	logger.info("Чёрный список: %d активных из %d всего", len(black_list), len(original_list))
	return black_list


def get_visit_list():
	visit_list = vl.get_col_by_name("url")
	# Оставляем только адреса шаблонов
	logger.debug("Список посещений: %d записей", len(visit_list))
	return visit_list


def get_number_vacancies(soup):
	""" [<h1 class="magritte-text___gMq2l_7-0-3 magritte-text-overflow___UBrTV_7-0-3 magritte-text-typography-small___QbQNX_7-0-3 magritte-text-style-primary___8SAJp_7-0-3" data-qa="title"><span>Найдено 34 вакансии</span> «ИИ»</h1>] """
	containers = soup.findAll("h1", {"data-qa": "title"})
	logger.debug("h1[data-qa='title']: найдено %d элементов", len(containers))

	if not containers:
		# Диагностика: ищем любые h1 на странице
		all_h1 = soup.findAll("h1")
		logger.warning(
			"⚠ h1[data-qa='title'] НЕ НАЙДЕН! Всего h1 на странице: %d", len(all_h1)
		)
		for i, h1 in enumerate(all_h1[:3]):
			logger.warning(
				"  h1[%d] class=%s text='%s'",
				i, h1.get("class"), h1.get_text(strip=True)[:100],
			)
		return 0

	text_string = containers[0].get_text(strip=True)
	logger.debug("Текст заголовка: '%s'", text_string)

	# Убираем ограничение в 9 символов и просто извлекаем все цифры
	number_str = ''.join(filter(str.isdigit, text_string))

	if number_str:
		result = int(number_str)
		logger.info("Вакансий в выдаче: %d", result)
		return result
	else:
		logger.warning("Не удалось извлечь число из '%s'", text_string)
		return 0


def get_num_pages(num_vacancies):
	std_vacancies_per_page = 20
	number_pages = num_vacancies / std_vacancies_per_page
	# Считаем, сколько будет страниц с результатами
	# Если целое количество, то так и возвращаем
	# Но если дробное, то возвращаем количество + 1

	if number_pages % 1 != 0:
		result = int(number_pages) + 1
	else:
		result = int(number_pages)
	logger.debug("Страниц для обхода: %d (вакансий: %d)", result, num_vacancies)
	return result


def get_all_vacancies_on_page(soup):
	containers = soup.findAll(
		"h2", class_="bloko-header-section-2", attrs={"data-qa": "bloko-header-2"}
	)
	logger.debug(
		"h2.bloko-header-section-2[data-qa='bloko-header-2']: %d", len(containers)
	)

	if not containers:
		# === ДИАГНОСТИКА: проверяем альтернативные селекторы ===
		all_h2 = soup.findAll("h2")
		logger.warning(
			"⚠ BLOKO-СЕЛЕКТОР НЕ НАШЁЛ НИЧЕГО. h2 на странице: %d", len(all_h2)
		)
		for i, h2 in enumerate(all_h2[:5]):
			logger.warning(
				"  h2[%d] class=%s data-qa=%s text='%s'",
				i, h2.get("class"), h2.get("data-qa"), h2.get_text(strip=True)[:80],
			)

		# Magritte-ссылки (новый дизайн hh/rabota)
		serp_links = soup.findAll("a", {"data-qa": "serp-item__title"})
		logger.warning(
			"  Альтернатива a[data-qa='serp-item__title']: %d шт.", len(serp_links)
		)
		for i, link in enumerate(serp_links[:3]):
			logger.warning(
				"    [%d] href='%s' text='%s'",
				i, link.get("href", "?")[:100], link.get_text(strip=True)[:60],
			)

		# vacancy-serp контейнеры
		serp_items = soup.findAll("div", {"data-qa": "vacancy-serp__vacancy"})
		logger.warning(
			"  Альтернатива div[data-qa='vacancy-serp__vacancy']: %d шт.",
			len(serp_items),
		)

		# Любые ссылки на /vacancy/
		all_links = soup.findAll("a", href=True)
		vacancy_links = [a for a in all_links if "/vacancy/" in a.get("href", "")]
		logger.warning(
			"  Все ссылки с '/vacancy/' в href: %d шт.", len(vacancy_links)
		)
		for i, link in enumerate(vacancy_links[:5]):
			logger.warning("    [%d] href='%s'", i, link["href"][:120])

	list_url_vacancy = []
	for container in containers:
		link = container.find("a")
		if link is not None:
			href = link["href"]
			# Обрезаем лишнее в адресе
			url_vacancy = href.split("?")[0]
			list_url_vacancy.append(url_vacancy)

	logger.debug("URL вакансий на странице (bloko): %d", len(list_url_vacancy))
	return list_url_vacancy


async def get_all_vacancies_on_all_pages(session, url, max_number_pages):
	all_vacancies = []
	logger.info("Обход %d страниц...", max_number_pages)
	for num_page in range(max_number_pages):
		url_full = url + items_on_page + pages + str(num_page)
		try:
			async with session.get(url_full, headers=headers) as response:
				if response.status != 200:
					logger.error("Страница %d: HTTP %d", num_page, response.status)
					continue
				page_text = await response.text()
				logger.debug(
					"Страница %d: HTTP %d, %d символов",
					num_page, response.status, len(page_text),
				)
			soup = BeautifulSoup(page_text, "html.parser")
			page_vacancies = get_all_vacancies_on_page(soup)
			all_vacancies += page_vacancies
			logger.debug(
				"Страница %d: %d вакансий (итого: %d)",
				num_page, len(page_vacancies), len(all_vacancies),
			)
		except (aiohttp.ClientError, asyncio.TimeoutError) as e:
			logger.error("Сетевая ошибка, страница %d для %s: %s", num_page, url[:80], e)
			continue
	logger.info("Всего URL со всех страниц: %d", len(all_vacancies))
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
    """
    Извлекает название вакансии со страницы rabota.by.
    Адаптировано под обновлённую структуру сайта (2025+).
    """
    # Приоритет 1: Ищем по data-qa="vacancy-title" (любой тег)
    vacancy_name = soup.find(attrs={"data-qa": "vacancy-title"})
    if vacancy_name is not None:
        text = vacancy_name.get_text(strip=True)
        if text:
            logger.debug("vacancy-title: '%s'", text[:80])
            return text

    # Приоритет 2: Альтернативный атрибут data-qa="title"
    vacancy_name = soup.find(attrs={"data-qa": "title"})
    if vacancy_name is not None:
        text = vacancy_name.get_text(strip=True)
        if text:
            logger.debug("title (fallback 1): '%s'", text[:80])
            return text

    # Приоритет 3: Поиск h1 с классами Magritte (новый дизайн hh/rabota)
    vacancy_name = soup.find("h1", class_=lambda x: x and "magritte" in x)
    if vacancy_name is not None:
        text = vacancy_name.get_text(strip=True)
        logger.debug("magritte h1 (fallback 2): '%s'", text[:80])
        return text

    # Fallback: первый h1 на странице
    h1 = soup.find("h1")
    if h1 is not None:
        text = h1.get_text(strip=True)
        logger.debug("first h1 (fallback 3): '%s'", text[:80])
        return text

    logger.warning("Название вакансии НЕ НАЙДЕНО")
    return "?"


def get_wage(soup):
	wage = soup.find("div", {"data-qa": "vacancy-salary"})
	# Если информация о ЗП не существует во всех вариантах, то выводим "?"
	result = wage.get_text() if wage else "?"
	logger.debug("ЗП: '%s'", result[:50])
	return result


def get_name_company(soup):
	name_company = soup.find("a", {"data-qa": "vacancy-company-name"})
	# Если имени компании не существует, то выводим "?"
	result = name_company.get_text() if name_company else "?"
	logger.debug("Компания: '%s'", result[:50])
	return result


def get_the_rest(soup, name_company):
	full_address = soup.find("span", {"data-qa": "vacancy-view-raw-address"})
	if full_address:
		general_string = full_address.get_text()
		logger.debug("Полный адрес: '%s'", general_string[:100])

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
		logger.debug("Адрес не найден, используем имя компании для карт")
		city, street_with_house, metro_stations = "?", "?", "?"
		yandex_url = get_map_url("yandex", name_company)
		google_url = get_map_url("google", name_company)

	return city, street_with_house, metro_stations, yandex_url, google_url


# Работа со страницами вакансий
async def get_param_for_msg():
	logger.info("=" * 50)
	logger.info("НАЧАЛО ЦИКЛА ПАРСИНГА")
	logger.info("=" * 50)

	keys_and_urls = get_list_keys_and_templates()

	if not keys_and_urls:
		logger.warning("Нет активных шаблонов для парсинга!")
		return

	timeout = aiohttp.ClientTimeout(total=30)
	async with aiohttp.ClientSession(timeout=timeout) as session:
		for key, url in keys_and_urls:
			logger.info("--- Шаблон: key='%s' ---", key)
			logger.info("URL: %s", url[:150])

			# Перед всеми проверками и запросами очищаем список посещений, если есть старые вакансии
			# Например: Если дата посещённой ссылки больше заданного времени, то она оттуда удаляется
			vl.delete_rows_after_time(key)
			logger.debug("Очистка старых посещений для key='%s' завершена", key)

			page_text = None
			try:
				async with session.get(url, headers=headers) as response:
					logger.info(
						"Главная: HTTP %d, Content-Type=%s",
						response.status,
						response.headers.get("Content-Type", "?"),
					)
					if response.status != 200:
						logger.error("HTTP %d для %s", response.status, url[:80])
						continue
					page_text = await response.text()
					logger.info("Получено %d символов HTML", len(page_text))
			except (aiohttp.ClientError, asyncio.TimeoutError) as e:
				logger.error("Сетевая ошибка при получении %s: %s", url[:80], e)
				continue

			if not page_text:
				logger.warning("Пустой ответ для %s, пропускаем", url[:80])
				continue

			# Проверяем на антибот/капчу — подозрительно короткий ответ
			if len(page_text) < 5000:
				logger.warning(
					"⚠ Подозрительно короткий ответ: %d символов. Возможна капча/блокировка!",
					len(page_text),
				)
				_save_debug_html(page_text, f"short_{key}")

			soup = BeautifulSoup(page_text, "html.parser")

			# Title страницы для диагностики
			title_tag = soup.find("title")
			page_title = title_tag.get_text(strip=True) if title_tag else "NO TITLE"
			logger.info("Title: '%s'", page_title[:120])

			# Получаем количество найденных вакансий
			number_results = get_number_vacancies(soup)
			# Считаем, сколько будет страниц
			max_number_pages = get_num_pages(number_results)

			if number_results == 0:
				logger.warning(
					"⚠ 0 вакансий для key='%s'. Сохраняем HTML для анализа.", key
				)
				_save_debug_html(page_text, f"zero_{key}")
				continue

			# Получаем все URLs из выдачи rabota.by
			all_urls = await get_all_vacancies_on_all_pages(session, url, max_number_pages)
			logger.info("URL из выдачи: %d", len(all_urls))

			# Критичная проверка: вакансии есть, но URL не извлечены
			if not all_urls and number_results > 0:
				logger.error(
					"❌ КРИТИЧНО: вакансий %d, но URL не извлечены! "
					"Вероятно, селектор h2.bloko-header-section-2 устарел. "
					"Сохраняем HTML.",
					number_results,
				)
				_save_debug_html(page_text, f"no_urls_{key}")

			# Получаем все URLs из чёрного списка
			black_list = get_black_list()

			# Удаляем из выдачи те URLs, которые находятся в чёрном списке
			before = len(all_urls)
			all_urls = list(set(all_urls) - set(black_list))
			logger.info(
				"Фильтр чёрного списка: %d → %d (убрано %d)",
				before, len(all_urls), before - len(all_urls),
			)

			# Получаем список уже ранее выведенных вакансий (список посещений)
			visit_list = get_visit_list()
			# Получаем список URLs, которые ранее не выводились в боте,
			# то есть удаляем из выдачи URLs из списка посещений
			before = len(all_urls)
			all_urls = list(set(all_urls) - set(visit_list))
			logger.info(
				"Фильтр посещений: %d → %d (убрано %d)",
				before, len(all_urls), before - len(all_urls),
			)

			if all_urls:
				logger.info("✅ Новых вакансий для обработки: %d", len(all_urls))

				# После того как прошли все проверки, записываем оставшиеся URLs (новые) в список посещений
				for url_vacancy in all_urls:
					vl.create_new_row(key, url_vacancy)
				logger.debug("Записано %d URL в список посещений", len(all_urls))

				# Заходим на каждый URL и достаём оттуда информацию о вакансии
				# Название вакансии, ЗП, название фирмы, адрес и прочее
				for url_vacancy in all_urls:
					logger.debug("Загрузка вакансии: %s", url_vacancy[:100])
					try:
						async with session.get(url_vacancy, headers=headers) as response:
							logger.debug("Вакансия: HTTP %d — %s", response.status, url_vacancy[:60])
							if response.status != 200:
								logger.error("Ошибка при получении вакансии %s: HTTP %d", url_vacancy[:80], response.status)
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

						logger.info(
							"→ Вакансия готова: '%s' @ '%s' | ЗП: %s",
							vacancy_name[:50],
							name_company[:30],
							wage[:30],
						)
						yield param
					except (aiohttp.ClientError, asyncio.TimeoutError) as e:
						logger.error("Сетевая ошибка при получении вакансии %s: %s", url_vacancy[:80], e)
						continue
					except Exception as e:
						logger.exception("Непредвиденная ошибка при обработке вакансии %s", url_vacancy[:80])
						continue
			else:
				logger.info("Нет новых вакансий для key='%s'", key)

	logger.info("=" * 50)
	logger.info("КОНЕЦ ЦИКЛА ПАРСИНГА")
	logger.info("=" * 50)