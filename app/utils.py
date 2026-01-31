import httpx
from .API import GOOGLE_API_KEY

GOOGLE_BOOKS_API_KEY = GOOGLE_API_KEY

async def fetch_book_info(title: str):
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {
        "q": title,
        "maxResults": 1,
        "key": GOOGLE_BOOKS_API_KEY
    }
    
    headers = {
        "User-Agent": "BookMindApp/1.0"
    }
    
    async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
        try:
            response = await client.get(url, params=params)
            print(f"DEBUG: Статус ответа Google: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if "items" in data:
                    book = data["items"][0]["volumeInfo"]
                    
                    links = book.get("imageLinks", {})
                    cover = links.get("thumbnail") or links.get("smallThumbnail") or ""
                    
                    return {
                        "title": book.get("title", "Без названия"),
                        "author": ", ".join(book.get("authors", ["Автор неизвестен"])),
                        "cover_url": cover.replace("http://", "https://"),
                        "description": book.get("description", "Описание отсутствует...")[:500]
                    }
            elif response.status_code == 429:
                print("DEBUG: Всё еще 429. Нужно подождать пару минут или проверить API Key.")
        except Exception as e:
            print(f"DEBUG: Ошибка: {e}")
            
    return None