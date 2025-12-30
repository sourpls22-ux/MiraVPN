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
            # Используем FormData вместо JSON
            data = aiohttp.FormData()
            data.add_field('username', self.username)
            data.add_field('password', self.password)
            data.add_field('grant_type', 'password')
            
            async with session.post(
                f"{self.base_url}/api/admin/token",
                data=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.token = result.get("access_token")
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
        
        return await self._request("POST", "/api/user", json=payload)
    
    async def get_user(self, username):
        """Получить информацию о пользователе"""
        return await self._request("GET", f"/api/user/{username}")
    
    async def get_user_config(self, username):
        """Получить конфигурацию пользователя"""
        user = await self.get_user(username)
        if user and user.get("links"):
            # Возвращаем первую ссылку из массива links
            return user["links"][0] if user["links"] else None
        return None
    
    async def delete_user(self, username):
        """Удалить пользователя"""
        return await self._request("DELETE", f"/api/user/{username}")
    
    async def get_users(self):
        """Получить список всех пользователей"""
        return await self._request("GET", "/api/users")
    
    async def reset_user_data(self, username):
        """Сбросить статистику пользователя"""
        return await self._request("POST", f"/api/user/{username}/reset")

