import requests
from typing import Optional, Dict, Any


class ApiController:
  _instance = None
  BASE_URL = "http://188.127.224.201:3000"

  def __new__(cls):
    if cls._instance is None:
      cls._instance = super(ApiController, cls).__new__(cls)
      cls._instance._init()
    return cls._instance

  def _init(self):
    self.session = requests.Session()
    # Можно добавить хедеры по умолчанию, если нужно
    self.session.headers.update({"Content-Type": "application/json"})

  def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Выполняет GET запрос к API."""
    # Если endpoint не начинается с /, добавляем его
    if not endpoint.startswith("/"):
      endpoint = "/" + endpoint

    url = f"{self.BASE_URL}{endpoint}"
    try:
      response = self.session.get(url, params=params)
      response.raise_for_status()
      return response.json()
    except requests.RequestException as e:
      print(f"Ошибка при GET запросе к {url}: {e}")
      return None

  def post(
    self,
    endpoint: str,
    data: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
  ) -> Any:
    """Выполняет POST запрос к API."""
    if not endpoint.startswith("/"):
      endpoint = "/" + endpoint

    url = f"{self.BASE_URL}{endpoint}"
    try:
      response = self.session.post(url, data=data, json=json)
      response.raise_for_status()
      return response.json()
    except requests.RequestException as e:
      print(f"Ошибка при POST запросе к {url}: {e}")
      return None


# Глобальный экземпляр для удобства импорта
api_controller = ApiController()
