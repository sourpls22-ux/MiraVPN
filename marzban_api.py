import aiohttp
import json
from config import MARZBAN_API_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD

class MarzbanAPI:
    def __init__(self):
        self.base_url = MARZBAN_API_URL
        self.username = MARZBAN_USERNAME
        self.password = MARZBAN_PASSWORD
        self.token = None
    
    async def login(self):
        """Авторизация в Marzban API"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/auth/login",
                json={"username": self.username, "password": self.password}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.token = data.get("access_token")
                    return True
                return False
    
    async def _request(self, method, endpoint, **kwargs):
        """Выполнение запроса к API"""
        if not self.token:
            await self.login()
        
        headers = {"Authorization": f"Bearer {self.token}"}
        headers.update(kwargs.pop("headers", {}))
        
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                f"{self.base_url}{endpoint}",
                headers=headers,
                **kwargs
            ) as response:
                if response.status == 401:
                    # Токен истек, перелогиниваемся
                    await self.login()
                    headers["Authorization"] = f"Bearer {self.token}"
                    async with session.request(
                        method,
                        f"{self.base_url}{endpoint}",
                        headers=headers,
                        **kwargs
                    ) as retry_response:
                        return await retry_response.json() if retry_response.status == 200 else None
                
                if response.status in [200, 201]:
                    return await response.json()
                return None
    
    async def create_user(self, username, data_limit_gb=None, expire_days=None):
        """Создание пользователя с VLESS + Reality"""
        payload = {
            "username": username,
            "proxies": {
                "vless": {
                    "flow": "xtls-rprx-vision"
                }
            },
            "inbounds": {
                "vless": ["VLESS + Reality"]
            },
            "data_limit": data_limit_gb * 1024 * 1024 * 1024 if data_limit_gb else 0,
            "expire": expire_days * 86400 if expire_days else None
        }
        
        return await self._request("POST", "/user", json=payload)
    
    async def get_user(self, username):
        """Получить информацию о пользователе"""
        return await self._request("GET", f"/user/{username}")
    
    async def get_user_config(self, username):
        """Получить конфигурацию пользователя"""
        return await self._request("GET", f"/user/{username}/subscription")
    
    async def delete_user(self, username):
        """Удалить пользователя"""
        return await self._request("DELETE", f"/user/{username}")
    
    async def get_users(self):
        """Получить список всех пользователей"""
        return await self._request("GET", "/users")
    
    async def reset_user_data(self, username):
        """Сбросить статистику пользователя"""
        return await self._request("POST", f"/user/{username}/reset")

