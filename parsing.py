from bs4 import BeautifulSoup
import requests

from Data import SearchTemplates, BlackList, VisitsList
import time

st = SearchTemplates()
bl = BlackList()
vl = VisitsList()

basic_url = {
	"yandex": "https://yandex.com/maps/?text=",
	"google": "https://www.google.com/maps/place/"
}

items_on_page = "&items_on_page=20"
pages = "&page="
# чтобы обойти ошибку 404, добавляю заголовок. Как будто запрос делает реальный пользователь
headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}

def get_list_keys_and_templates():
	original_list = st.get_all_from_table()
	# Оставляем только те шаблоны, которые нужны для запросов 
	filtered_list = [item for item in original_list if item[-1] == True]
	# Оставляем только ключи и адреса шаблонов
	keys_and_templates = [item[1:3] for item in filtered_list]
	return keys_and_templates

def get_black_list():
	original_list = bl.get_all_from_table()
	# Оставляем только те исключения, которые нужны для проверки 
	filtered_list = [item for item in original_list if item[-1] == True]
	# Оставляем только адреса исключений
	black_list = [item[2] for item in filtered_list]
	return black_list

def get_visit_list():
	visit_list = vl.get_col_by_name("url")
	# Оставляем только адреса шаблонов
	return visit_list

def get_number_vacancies(soup):
	conteiners = soup.findAll('h1', class_='bloko-header-section-3')
	try:
		# Извлекаем текст с числом из контейнера
		text_string = conteiners[0].get_text(strip=True)
	except IndexError as _:
		# Если вакансий нет, то возвращаем 0
		return 0
	
	# Отрезаем концовку текста, на случай, если в самом запросе были числа
	# 9 символов = 999999999 вакансиям. Это количество должно быть достаточно для проверки
	text_string = text_string[:9]
	try:
		# Извлекаем число из полученной строки
		number = int(''.join(filter(str.isdigit, text_string)))
		return number
	except ValueError as _:
		# Если числа нет, то возвращаем 0
		return 0

def get_num_pages(num_vacancies):
	std_vacancies_per_page = 20
	# Считаем, сколько будет страниц с результатами
	# Если целое количество, то так и возвращаем
	# Но если дробное, то возвращаем количество + 1
	number_pages = num_vacancies/std_vacancies_per_page

	if number_pages % 1 != 0:
		return int(number_pages) + 1
	else:
		return int(number_pages)

def get_all_vacancies_on_page(obj):
	conteiners = obj.findAll('h2', class_='bloko-header-section-2', attrs={"data-qa": "bloko-header-2"})
	list_url_vacancy = []
	for conteiner in conteiners:
		link = conteiner.find('a')
		if link is not None:
			href = link['href']
			# обрезаем лишнее в адресе
			url_vacancy = href.split("?")[0]
			list_url_vacancy.append(url_vacancy)
	return list_url_vacancy

def get_all_vacancies_on_all_pages(url, max_number_pages):
	all_vacancies = []
	for num_page in range(max_number_pages):
		url_full = url + items_on_page + pages + str(num_page)
		page = requests.get(url_full, headers=headers)
		soup = BeautifulSoup(page.text, "html.parser")
		all_vacancies += get_all_vacancies_on_page(soup)
	return all_vacancies

######################### Работа со страницами вакансий
def get_map_url(name_map: str, string_search):
	# Удаляем все запятые из строки
	string_without_commas = string_search.replace(",", "")
	# заменяем все пробелы знаком +(плюс)
	string_with_pluses = string_without_commas.replace(" ", "+")
	# Формируем адрес из общего шаблона, и того что нужно искать
	url = basic_url[name_map] + string_with_pluses
	return url

def get_vacancy_name(obj):
	vacancy_name = obj.find("h1", class_="bloko-header-section-1", attrs={"data-qa": "vacancy-title"})
	if vacancy_name != None:
		return vacancy_name.get_text(strip=True)

def get_wage(obj):
	# Есть два варианта получения ЗП
	# Вариант 1
	wage = obj.find("span",  class_="bloko-header-section-2 bloko-header-section-2_lite", attrs={"data-qa": "vacancy-salary-compensation-type-gross"})
	if wage:
		return wage.get_text()

	# Вариант 2
	wage2 = obj.find("span",  class_="bloko-header-section-2 bloko-header-section-2_lite", attrs={"data-qa": "vacancy-salary-compensation-type-net"})

	if wage2:
		return wage2.get_text()
	else:
		# Если информация о ЗП не существует во всех вариантах, то выводим "?"
		return "?"

def get_name_company(obj):
	name_company = obj.find("span", class_="bloko-header-section-2 bloko-header-section-2_lite", attrs={"data-qa": "bloko-header-2"})
	# Если имени компании не существует, то выводим "?"
	return name_company.get_text() if name_company else "?"

def get_the_rest(obj, name_company):
	full_address = obj.find('span', attrs={'data-qa': 'vacancy-view-raw-address'})
	
	# # TODO Почему так
	# name_company = get_name_company(obj)

	# Если контейнер с адресом существует, тогда разбираем его на город, метро, адрес дома и улицы
	if full_address != None:
		city = full_address.contents[0].strip()

		# Извлекаем станции метро
		metro_stations = [station.get_text() for station in full_address.find_all('span', class_='metro-station')]
		
		## Извлекаем улицу с домом
		# Самый простой способ, это собрать все ненужные слова в список. И удалить эти слова из общей строки
		# Формируем общую строку
		general_string = full_address.get_text(strip=True)
		# Так как отдельный список со всем станциями метро ещё нужен, то содаём копию
		words_to_remove = metro_stations.copy()
		# Добавляем в список метро, ещё название города. чтобы удобнее было удалять
		words_to_remove.append(city)
		# Удаляем слова из строки
		for word in words_to_remove:
			general_string = general_string.replace(word, "")
		# Удаляем лишние запятые, и остаётся только улица и дом
		street_with_house = general_string.strip(', ')
		
		# Если метро не было указано, то выводим "?"
		if metro_stations == []:
			metro_stations = "?"

		# Если переменная(улица и дом) содержит только пробелы, тогда нет смысла искать компанию по адресу
		if street_with_house.replace(" ", ""):
			# Поиск по адресу
			search_string = f"{city} {street_with_house}"
			yandex_url = get_map_url("yandex", search_string)
			google_url = get_map_url("google", search_string)
		else:
			# Поиск по названию компании
			yandex_url = get_map_url("yandex", name_company)
			google_url = get_map_url("google", name_company)
	else:
		city, street_with_house, metro_stations = "???"
		yandex_url = get_map_url("yandex", name_company)
		google_url = get_map_url("google", name_company)

	return city, street_with_house, metro_stations, yandex_url, google_url
######################### Работа со страницами вакансий

def get_param_for_msg():
	keys_and_urls = get_list_keys_and_templates()

	for key, url in keys_and_urls:
		## Перед всеми проверками и запросами, очищаем список посещений, если есть старые вакансии
		# Например: Если дата посещённой ссылки больше за 1 неделю, то она оттуда удаляется
		vl.delete_rows_after_time(key)

		page = requests.get(url, headers=headers)
		soup = BeautifulSoup(page.text, "html.parser")

		# Получаем количество найденных вакансий
		number_results = get_number_vacancies(soup)
		# Считаем сколько будет страниц
		max_number_pages = get_num_pages(number_results)

		# Выводим все urls из выдачи rabota.by
		all_urls = get_all_vacancies_on_all_pages(url, max_number_pages)

		# Получаем все all_urls в BlackList
		black_list = get_black_list()

		# Удаляем из выдачи те urls которые находятся в чёрном списке
		all_urls = list(set(all_urls) - set(black_list))

		# Получить список уже ранее выведенных вакансий(список посещений)
		visit_list = get_visit_list()
		# Получаем список urls которые ранее не выводились боте
		# то есть, удаляем из выдачи те urls которые находятся в список посещений
		all_urls = list(set(all_urls) - set(visit_list))

		if all_urls != []:
			# После того, как прошли все проверки, записываем оставшиеся urls(новые) в список посещений
			for url in all_urls:
				vl.create_new_row(key, url)

			## Заходим на каждый url, и достаём оттуда информацию о посте
			# Название вакансии, ЗП, Название фирмы, Адрес, и прочее
			for url in all_urls:
				page2 = requests.get(url, headers=headers)
				soup2 = BeautifulSoup(page2.text, "html.parser")
				
				# TODO
				# Временное решение проблемы, не полной загрузки страницы
				# Сделать асинхронный вариант (возможно ли с asyncio.create_task(background_task())?)
				time.sleep(1.5)

				vacancy_name = get_vacancy_name(soup2)
				wage = get_wage(soup2)
				name_company = get_name_company(soup2)

				city, street, metro_stations, yandex_url, google_url = get_the_rest(soup2, name_company)
				
				# Так как в названии ключа могут быть пробелы, а как известно пробелы обрезают работу тега в сообщении. Поэтому заменяем все пробелы на нижние подчёркивания
				key = key.replace(" ", "_")

				metro = ", ".join(metro_stations)

				param = {
					"key": key,
					"url": url,
					"vacancy_name": vacancy_name,
					"wage": wage,
					"name_company": name_company,
					"city": city,
					"street": street,
					"metro": metro,
					"yandex_url": yandex_url,
					"google_url": google_url,
				}

				# Отправляем параметры в бота, для дальнейшего форматирования
				yield param
