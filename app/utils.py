import httpx
from .secrets import GOOGLE_BOOKS_API_KEY

async def fetch_book_info(title: str):
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {"q": title, "maxResults": 1, "key": GOOGLE_BOOKS_API_KEY}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if "items" in data:
                    book = data["items"][0]["volumeInfo"]
                    links = book.get("imageLinks", {})
                    cover = links.get("thumbnail") or links.get("smallThumbnail") or ""
                    
                    cover = cover.replace("http://", "https://")
                    
                    return {
                        "title": book.get("title", "Без названия"),
                        "author": ", ".join(book.get("authors", ["Автор неизвестен"])),
                        "cover_url": cover,
                        "description": book.get("description", "")[:500]
                    }
        except Exception as e:
            print(f"Error fetching book: {e}")
    return None