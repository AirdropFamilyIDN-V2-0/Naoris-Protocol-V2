import asyncio
import json
import os
import pytz
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from colorama import init, Fore, Style
from curl_cffi import requests
from fake_useragent import FakeUserAgent

# Initialize colorama
init(autoreset=True)
wib = pytz.timezone('Asia/Jakarta')

# Definisikan warna utama
C_SUCCESS = Fore.LIGHTGREEN_EX
C_INFO = Fore.LIGHTYELLOW_EX
C_WARNING = Fore.LIGHTYELLOW_EX
C_ERROR = Fore.LIGHTRED_EX 
C_DEBUG = Fore.LIGHTYELLOW_EX
C_INPUT = Fore.LIGHTYELLOW_EX
C_BANNER = Fore.LIGHTGREEN_EX
C_TEXT = Fore.LIGHTYELLOW_EX
C_SEPARATOR = Fore.LIGHTYELLOW_EX


class NaorisProtocolAutomation:
    def __init__(self) -> None:
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": "chrome-extension://cpikalnagknmlfhnilhfelifgbollmmp",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "none",
            "User-Agent": FakeUserAgent().random
        }
        self.base_api_url = "https://naorisprotocol.network"
        self.ping_api_url = "https://beat.naorisprotocol.network"

        self.proxies: List[str] = []
        self.proxy_index: int = 0
        self.account_proxies: Dict[str, Optional[str]] = {}
        self.access_tokens: Dict[str, str] = {}
        self.refresh_tokens: Dict[str, str] = {}

        self.accounts_file = "accounts.json"
        self.proxy_file = "proxies.txt"

    def display_banner(self):
        banner_lines = [
            "+------------------------------------------------------------+",
            "|                                                            |",
            "|            NAORIS PROTOCOL AUTOMATION BOT v2.0             |",
            "|                     @AirdropFamilyIDN                      |",   
            "|                                                            |",
            "+------------------------------------------------------------+"
        ]
        for line in banner_lines:
            print(C_BANNER + Style.BRIGHT + line + Style.RESET_ALL)
        print()

    def clear_terminal(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def log(self, message: str, level: str = "INFO", account_context: Optional[str] = None):
        timestamp = datetime.now(wib).strftime('%Y-%m-%d %H:%M:%S %Z')
        
        level_color_map = {
            "SUCCESS": C_SUCCESS, "INFO": C_INFO, "WARNING": C_WARNING,
            "ERROR": C_ERROR, "DEBUG": C_DEBUG, "INPUT": C_INPUT
        }
        log_color = level_color_map.get(level.upper(), C_INFO)
        
        level_str = level.upper().ljust(5)

        print(f"{C_TEXT}[{timestamp}]{Style.RESET_ALL} {log_color}[{level_str}]{Style.RESET_ALL} {log_color}{message}{Style.RESET_ALL}", flush=True)

    def log_account_specific(self, masked_address: str, message: str, level: str = "INFO", proxy_info: Optional[str] = None, status_msg: Optional[str] = None):
        timestamp = datetime.now(wib).strftime('%Y-%m-%d %H:%M:%S %Z')
        level_color_map = {
            "SUCCESS": C_SUCCESS, "INFO": C_INFO, "WARNING": C_WARNING,
            "ERROR": C_ERROR, "DEBUG": C_DEBUG
        }
        log_color = level_color_map.get(level.upper(), C_INFO)
        level_str = level.upper().ljust(5)

        full_message = message
        if proxy_info and status_msg:
            full_message = f"Proxy: {proxy_info} | Status: {status_msg}"
        elif status_msg:
             full_message = f"Status: {status_msg}"
        
        print(f"{C_TEXT}[{timestamp}]{Style.RESET_ALL} {log_color}[{level_str}]{Style.RESET_ALL} {log_color}{full_message}{Style.RESET_ALL}", flush=True)


    def generate_device_hash(self) -> str:
        return str(int(uuid.uuid4().hex.replace("-", "")[:10], 16))

    def load_accounts_from_file(self) -> List[Dict[str, Any]]:
        try:
            if not os.path.exists(self.accounts_file):
                self.log(f"File akun '{self.accounts_file}' tidak ditemukan.", level="ERROR")
                return []
            with open(self.accounts_file, 'r') as file:
                accounts_data = json.load(file)
            if not isinstance(accounts_data, list):
                self.log(f"Format data di '{self.accounts_file}' tidak valid. Harusnya list.", level="ERROR")
                return []
            
            valid_accounts = []
            for acc_idx, acc in enumerate(accounts_data):
                if isinstance(acc, dict) and "Address" in acc and "deviceHash" in acc:
                    try:
                        acc["deviceHash"] = int(str(acc["deviceHash"]))
                        valid_accounts.append(acc)
                    except ValueError:
                        self.log(f"Akun ke-{acc_idx+1} memiliki deviceHash tidak valid (harus integer): {C_WARNING}{acc.get('deviceHash')}{C_ERROR}", level="ERROR")
                else:
                    self.log(f"Akun ke-{acc_idx+1} di '{self.accounts_file}' tidak memiliki format yang benar (membutuhkan 'Address' dan 'deviceHash').", level="WARNING")
            
            if valid_accounts:
                self.log(f"Berhasil memuat {len(valid_accounts)} akun valid dari '{self.accounts_file}'.", level="INFO")
            return valid_accounts
        except json.JSONDecodeError:
            self.log(f"Gagal mendekode JSON dari '{self.accounts_file}'. Pastikan formatnya benar.", level="ERROR")
            return []
        except Exception as e:
            self.log(f"Error saat memuat akun: {e}", level="ERROR")
            return []

    async def load_proxies_from_local_file(self):
        try:
            if not os.path.exists(self.proxy_file):
                self.log(f"File proxy '{self.proxy_file}' tidak ditemukan.", level="ERROR")
                self.proxies = []
                return
            with open(self.proxy_file, 'r') as f:
                self.proxies = [line.strip() for line in f if line.strip()]

            if not self.proxies:
                self.log(f"Tidak ada proxy yang dimuat dari '{self.proxy_file}'.", level="WARNING")
            else:
                 self.log(f"Total proxy yang dimuat dari '{self.proxy_file}': {len(self.proxies)}", level="SUCCESS")
        except Exception as e:
            self.log(f"Gagal memuat proxy dari '{self.proxy_file}': {e}", level="ERROR")
            self.proxies = []

    def _get_proxy_url(self, proxy_str: str) -> Optional[str]:
        if not proxy_str:
            return None
        schemes = ["http://", "https://", "socks4://", "socks5://"]
        if any(proxy_str.startswith(scheme) for scheme in schemes):
            return proxy_str
        return f"http://{proxy_str}"

    def get_next_proxy_for_account(self, account_address: str) -> Optional[str]:
        if not self.proxies:
            return None
        current_proxy_str = self.proxies[self.proxy_index]
        self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        assigned_proxy = self._get_proxy_url(current_proxy_str)
        self.account_proxies[account_address] = assigned_proxy
        return assigned_proxy

    def _mask_address(self, address: str) -> str:
        if len(address) > 12:
            return f"{address[:6]}...{address[-4:]}"
        return address

    def ask_use_proxy(self) -> bool:
        timestamp = datetime.now(wib).strftime('%Y-%m-%d %H:%M:%S %Z')
        while True:
            print(f"{C_TEXT}[{timestamp}]{Style.RESET_ALL} {C_INPUT}[INPUT]{Style.RESET_ALL} {C_INPUT}Apakah Anda ingin menggunakan proxy dari '{self.proxy_file}'? (y/n): {Style.RESET_ALL}", end="")
            choice = input().strip().lower()
            if choice == 'y':
                self.log("Menggunakan proxy.", level="INFO")
                return True
            elif choice == 'n':
                self.log("Tidak menggunakan proxy.", level="INFO")
                return False
            else:
                self.log("Input tidak valid. Harap masukkan 'y' untuk Ya atau 'n' untuk Tidak.", level="WARNING")

    async def _request(self, method: str, url: str, headers: Optional[Dict] = None, data: Optional[Dict] = None, 
                       json_payload: Optional[Dict] = None, proxy: Optional[str] = None, impersonate: str = "chrome110", timeout: int = 60) -> Optional[Any]:
        effective_headers = {**self.headers, **(headers or {})}
        if data:
             effective_headers["Content-Length"] = str(len(data))
             if "Content-Type" not in effective_headers:
                 effective_headers["Content-Type"] = "application/json"
        elif json_payload is not None:
            if "Content-Type" not in effective_headers:
                 effective_headers["Content-Type"] = "application/json"
        
        try:
            if method.upper() == "POST":
                response = await asyncio.to_thread(
                    requests.post, url, headers=effective_headers, data=data, json=json_payload, 
                    proxies={"http": proxy, "https": proxy} if proxy else None, 
                    timeout=timeout, impersonate=impersonate
                )
            elif method.upper() == "GET":
                response = await asyncio.to_thread(
                    requests.get, url, headers=effective_headers, 
                    proxies={"http": proxy, "https": proxy} if proxy else None, 
                    timeout=timeout, impersonate=impersonate
                )
            else:
                return {"error": True, "status_code": "N/A", "message": f"Unsupported HTTP method: {method}"}
            response.raise_for_status()
            try:
                return response.json()
            except json.JSONDecodeError:
                return response.text
        except requests.RequestsError as e:
            status_code = e.response.status_code if e.response is not None else "N/A"
            response_text = e.response.text if e.response is not None else None
            error_message = str(e)
            return {"error": True, "status_code": status_code, "message": error_message, "response_text": response_text}
        except Exception as e:
            return {"error": True, "status_code": "N/A", "message": str(e)}

    async def generate_token(self, masked_address: str, original_address: str, proxy: Optional[str], retries: int = 3) -> Optional[Dict]:
        url = f"{self.base_api_url}/sec-api/auth/gt-event"
        payload_dict = {"wallet_address": original_address}
        payload_str = json.dumps(payload_dict)
        
        for attempt in range(retries):
            response = await self._request("POST", url, data=payload_str, proxy=proxy)
            if isinstance(response, dict) and not response.get("error"):
                return response
            elif isinstance(response, dict) and response.get("status_code") == 404:
                 self.log_account_specific(masked_address, "", level="ERROR", status_msg=f"Generate Token Gagal (404): Pastikan akun terdaftar & selesaikan task.")
                 return None
            
            error_msg = response.get("message", "Unknown error") if isinstance(response, dict) else "Non-dict/No response"
            # Warning untuk retry, Error untuk final
            log_level_retry = "WARNING" if attempt < retries - 1 else "ERROR"
            self.log_account_specific(masked_address, "", level=log_level_retry, status_msg=f"Generate Token Gagal (attempt {attempt+1}/{retries}): {error_msg}{'. Retry...' if attempt < retries -1 else '. Gagal Final.'}")
            if attempt < retries - 1:
                await asyncio.sleep(5)
            else: # Gagal setelah semua retry
                return None
        return None # Seharusnya tidak tercapai jika loop berjalan

    async def refresh_token_api(self, masked_address: str, original_address: str, current_refresh_token: str, proxy: Optional[str], use_proxy_flag: bool, retries: int = 3) -> Optional[Dict]:
        url = f"{self.base_api_url}/sec-api/auth/refresh"
        payload_dict = {"refreshToken": current_refresh_token}
        payload_str = json.dumps(payload_dict)

        for attempt in range(retries):
            response = await self._request("POST", url, data=payload_str, proxy=proxy)
            if isinstance(response, dict) and not response.get("error"):
                return response
            elif isinstance(response, dict) and response.get("status_code") == 401:
                self.log_account_specific(masked_address, "", level="WARNING", status_msg="Refresh Token Gagal (401). Mencoba generate token baru...")
                new_tokens = await self.process_generate_new_token(masked_address, original_address, use_proxy_flag, proxy_to_use=proxy)
                if new_tokens:
                    return new_tokens # Ini adalah dict sukses dari process_generate_new_token
                else: # Gagal generate token baru
                    self.log_account_specific(masked_address, "", level="ERROR", status_msg="Gagal generate token baru setelah refresh gagal (401).")
                    return None # Error final untuk refresh ini
            
            error_msg = response.get("message", "Unknown error") if isinstance(response, dict) else "Non-dict/No response"
            log_level_retry = "WARNING" if attempt < retries - 1 else "ERROR"
            self.log_account_specific(masked_address, "", level=log_level_retry, status_msg=f"Refresh Token Gagal (attempt {attempt+1}/{retries}): {error_msg}{'. Retry...' if attempt < retries -1 else '. Gagal Final.'}")
            if attempt < retries - 1:
                await asyncio.sleep(5)
            else:
                return None
        return None

    async def get_wallet_details(self, masked_address: str, original_address: str, access_token: str, proxy: Optional[str], retries: int = 3) -> Optional[Dict]:
        url = f"{self.base_api_url}/sec-api/api/wallet-details"
        headers = {"Authorization": f"Bearer {access_token}"}
        for attempt in range(retries):
            response = await self._request("GET", url, headers=headers, proxy=proxy)
            if isinstance(response, dict) and not response.get("error"):
                return response
            error_msg = response.get("message", "Unknown error") if isinstance(response, dict) else "Non-dict/No response"
            log_level_retry = "WARNING" if attempt < retries - 1 else "ERROR"
            self.log_account_specific(masked_address, "", level=log_level_retry, status_msg=f"Get Wallet Details Gagal (attempt {attempt+1}/{retries}): {error_msg}{'. Retry...' if attempt < retries -1 else '. Gagal Final.'}")
            if attempt < retries - 1:
                await asyncio.sleep(5)
            else:
                 return None
        return None

    async def add_to_whitelist(self, masked_address: str, original_address: str, access_token: str, proxy: Optional[str], retries: int = 3) -> bool:
        url = f"{self.base_api_url}/sec-api/api/addWhitelist"
        payload_dict = {"walletAddress": original_address, "url": "naorisprotocol.network"}
        payload_str = json.dumps(payload_dict)
        headers = {"Authorization": f"Bearer {access_token}"}
        proxy_info_str = proxy if proxy else "Tidak Digunakan"

        for attempt in range(retries):
            response = await self._request("POST", url, headers=headers, data=payload_str, proxy=proxy)
            if isinstance(response, dict) and not response.get("error"):
                if response.get("message") == "url saved successfully":
                    return True # Sukses
            elif isinstance(response, dict) and response.get("status_code") == 409:
                self.log_account_specific(masked_address, "", level="INFO", proxy_info=proxy_info_str, status_msg="URL sudah ada di whitelist.")
                return True # Dianggap sukses jika sudah ada

            error_msg = response.get("message", "Unknown error") if isinstance(response, dict) else "Non-dict/No response"
            log_level_retry = "WARNING" if attempt < retries - 1 else "ERROR"
            self.log_account_specific(masked_address, "", level=log_level_retry, status_msg=f"Add Whitelist Gagal (attempt {attempt+1}/{retries}): {error_msg}{'. Retry...' if attempt < retries -1 else '. Gagal Final.'}")
            if attempt < retries - 1:
                await asyncio.sleep(5)
            else: # Gagal setelah semua retry
                 return False
        return False # Default jika loop selesai tanpa sukses
        
    async def toggle_device_activation(self, masked_address: str, original_address: str, device_hash: int, access_token: str, state: str, proxy: Optional[str], retries: int = 3) -> Optional[str]:
        url = f"{self.base_api_url}/sec-api/api/switch"
        payload_dict = {"walletAddress": original_address, "state": state.upper(), "deviceHash": device_hash}
        payload_str = json.dumps(payload_dict)
        headers = {"Authorization": f"Bearer {access_token}"}

        for attempt in range(retries):
            response = await self._request("POST", url, headers=headers, data=payload_str, proxy=proxy)
            
            if isinstance(response, str): # Sukses jika string
                return response.strip()
            # Jika bukan string, pasti ada masalah atau respons tidak diharapkan
            elif isinstance(response, dict) and response.get("error"):
                error_msg = response.get("message", "Unknown error")
            elif isinstance(response,dict): # Dict tapi bukan error dari _request (misal, API mengembalikan JSON saat kita harapkan string)
                error_msg = f"Unexpected dict response: {response}"
            else: # None atau tipe lain
                error_msg = "No response or unknown response type"

            log_level_retry = "WARNING" if attempt < retries - 1 else "ERROR"
            self.log_account_specific(masked_address, "", level=log_level_retry, status_msg=f"Toggle Activation ({state}) Gagal (attempt {attempt+1}/{retries}): {error_msg}{'. Retry...' if attempt < retries -1 else '. Gagal Final.'}")
            if attempt < retries - 1:
                await asyncio.sleep(5)
            else: # Gagal setelah semua retry
                return None
        return None

    async def initiate_message_production(self, masked_address: str, original_address: str, device_hash: int, access_token: str, proxy: Optional[str], retries: int = 3) -> bool:
        url = f"{self.ping_api_url}/sec-api/api/htb-event"
        payload_dict = {"inputData": {"walletAddress": original_address, "deviceHash": device_hash}}
        payload_str = json.dumps(payload_dict)
        headers = {"Authorization": f"Bearer {access_token}"}

        for attempt in range(retries):
            response = await self._request("POST", url, headers=headers, data=payload_str, proxy=proxy)
            if isinstance(response, dict) and not response.get("error") and response.get("message") == "Message production initiated":
                return True
            
            error_msg = response.get("message", "Unknown error") if isinstance(response, dict) else "Non-dict/No response"
            log_level_retry = "WARNING" if attempt < retries - 1 else "ERROR"
            self.log_account_specific(masked_address, "", level=log_level_retry, status_msg=f"Initiate Message Prod. Gagal (attempt {attempt+1}/{retries}): {error_msg}{'. Retry...' if attempt < retries -1 else '. Gagal Final.'}")
            if attempt < retries - 1:
                await asyncio.sleep(5)
            else:
                return False
        return False

    async def perform_ping(self, masked_address: str, original_address: str, access_token: str, proxy: Optional[str], retries: int = 3) -> bool:
        url = f"{self.ping_api_url}/api/ping"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        for attempt in range(retries):
            response = await self._request("POST", url, headers=headers, json_payload={}, proxy=proxy)
            
            if isinstance(response, str) and response.strip() == "Ping Success!!": # Sukses jika string ini
                return True
            # Handle jika 410 adalah sukses (seperti di sc2)
            elif isinstance(response, dict) and response.get("status_code") == 410 and \
                 isinstance(response.get("response_text"), str) and \
                 response.get("response_text","").strip() == "Ping Success!!":
                return True
            # Jika bukan string sukses, atau bukan 410 sukses, maka itu error atau respons tak dikenal
            elif isinstance(response, dict) and response.get("error"):
                error_msg = response.get("message", "Unknown error")
                status_code = response.get("status_code")
            elif isinstance(response,dict): # Dict tapi bukan error dari _request
                 error_msg = f"Unexpected dict response: {response}"
                 status_code = "N/A"
            else: # None atau tipe lain
                error_msg = "No response or unknown response type"
                status_code = "N/A"


            status_code_info = f"(status: {status_code})" if status_code != "N/A" else ""
            log_level_retry = "WARNING" if attempt < retries - 1 else "ERROR"
            self.log_account_specific(masked_address, "", level=log_level_retry, status_msg=f"Perform Ping Gagal (attempt {attempt+1}/{retries}){status_code_info}: {error_msg}{'. Retry...' if attempt < retries -1 else '. Gagal Final.'}")
            if attempt < retries - 1:
                await asyncio.sleep(5)
            else: # Gagal setelah semua retry
                return False
        return False

    async def process_generate_new_token(self, masked_address: str, original_address: str, use_proxy_flag: bool, proxy_to_use: Optional[str] = None) -> Optional[Dict[str,str]]:
        if proxy_to_use is None and use_proxy_flag:
            proxy = self.get_next_proxy_for_account(original_address) if use_proxy_flag else None
        else:
            proxy = proxy_to_use if use_proxy_flag else None
        
        proxy_info_str = proxy if proxy else "Tidak Digunakan"

        token_data = await self.generate_token(masked_address, original_address, proxy)
        if token_data and "token" in token_data and "refreshToken" in token_data:
            self.access_tokens[original_address] = token_data["token"]
            self.refresh_tokens[original_address] = token_data["refreshToken"]
            # Pesan sukses generate token akan dicetak oleh generate_token jika berhasil di sana,
            # atau kita bisa cetak di sini juga. Sesuai contoh, "Generate Token Berhasil" ada.
            self.log_account_specific(masked_address, "", level="SUCCESS", proxy_info=proxy_info_str, status_msg="Generate Token Berhasil.")
            return {"token": token_data["token"], "refreshToken": token_data["refreshToken"]}
        else:
            # Pesan error sudah dicetak oleh generate_token
            if original_address in self.access_tokens: del self.access_tokens[original_address]
            if original_address in self.refresh_tokens: del self.refresh_tokens[original_address]
            return None

    async def periodic_refresh_token_task(self, masked_address: str, original_address: str, use_proxy_flag: bool, initial_delay_minutes: int = 25):
        await asyncio.sleep(initial_delay_minutes * 60)
        while True:
            if original_address not in self.refresh_tokens:
                self.log_account_specific(masked_address, "Refresh token tidak ada, mencoba generate token baru.", level="WARNING")
                await self.process_generate_new_token(masked_address, original_address, use_proxy_flag)
                if original_address not in self.refresh_tokens: # Jika masih gagal setelah coba generate
                    self.log_account_specific(masked_address, "Gagal mendapatkan refresh token, skip periodic refresh untuk siklus ini.", level="ERROR")
                    await asyncio.sleep(5 * 60) # Tunggu sebelum coba lagi dari awal
                    continue # Lanjutkan loop while True
            
            proxy = self.get_next_proxy_for_account(original_address) if use_proxy_flag else None
            proxy_info_str = proxy if proxy else "Tidak Digunakan"
            
            self.log_account_specific(masked_address, "Mencoba refresh token...", level="DEBUG")
            refreshed_token_data = await self.refresh_token_api(masked_address, original_address, self.refresh_tokens[original_address], proxy, use_proxy_flag)
            
            if refreshed_token_data and "token" in refreshed_token_data and "refreshToken" in refreshed_token_data:
                self.access_tokens[original_address] = refreshed_token_data["token"]
                self.refresh_tokens[original_address] = refreshed_token_data["refreshToken"]
                self.log_account_specific(masked_address, "", level="SUCCESS", proxy_info=proxy_info_str, status_msg="Refresh Token Berhasil.")
            else:
                # Pesan error/warning sudah dari refresh_token_api atau process_generate_new_token di dalamnya
                # Pastikan token dihapus jika refresh gagal total agar siklus berikutnya coba generate dari awal
                if original_address in self.access_tokens: del self.access_tokens[original_address]
                if original_address in self.refresh_tokens: del self.refresh_tokens[original_address]
                self.log_account_specific(masked_address, "Refresh token gagal dan token lama dihapus. Akan mencoba generate baru di siklus berikutnya.", level="WARNING")


            await asyncio.sleep(30 * 60) # Interval refresh

    async def periodic_wallet_details_task(self, masked_address: str, original_address: str, use_proxy_flag: bool, initial_delay_minutes: int = 1):
        await asyncio.sleep(initial_delay_minutes * 60)
        while True:
            if original_address not in self.access_tokens:
                self.log_account_specific(masked_address, "Access token tidak ada, skip get wallet details.", level="WARNING")
                await asyncio.sleep(5 * 60)
                continue

            proxy = self.get_next_proxy_for_account(original_address) if use_proxy_flag else None
            proxy_info_str = proxy if proxy else "Tidak Digunakan"
            self.log_account_specific(masked_address, "Mengambil detail wallet...", level="DEBUG")
            details = await self.get_wallet_details(masked_address, original_address, self.access_tokens[original_address], proxy)
            
            if isinstance(details, dict) and not details.get("error") and "message" in details :
                total_earnings = details["message"].get("totalEarnings", "N/A")
                self.log_account_specific(masked_address, "", level="INFO", proxy_info=proxy_info_str, status_msg=f"Total Pendapatan: {total_earnings} PTS")
            elif isinstance(details, dict) and details.get("error"):
                response_text = details.get("response_text", "")
                status_code = details.get("status_code")
                if status_code == 401 or (response_text and "Invalid token" in response_text): # Cek response_text jika ada
                    self.log_account_specific(masked_address, "", level="WARNING", proxy_info=proxy_info_str, status_msg="Token tidak valid saat ambil detail wallet.")
                    if original_address in self.access_tokens: del self.access_tokens[original_address] # Hapus token agar di-generate ulang
                else: # Error lain
                    self.log_account_specific(masked_address, "", level="ERROR", proxy_info=proxy_info_str, status_msg=f"Gagal ambil detail wallet: {details.get('message')}")
            else: # Respons tidak dikenal
                self.log_account_specific(masked_address, "", level="WARNING", proxy_info=proxy_info_str, status_msg="Gagal mengambil detail wallet (respons tidak dikenal).")
            
            await asyncio.sleep(15 * 60) # Interval cek detail

    async def main_account_operations_task(self, original_address: str, device_hash: int, use_proxy_flag: bool):
        masked_address = self._mask_address(original_address)
        
        print(C_SEPARATOR + Style.BRIGHT + "-" * 60 + Style.RESET_ALL)
        # Header akun sekarang menggunakan self.log agar timestamp dan format levelnya konsisten
        self.log(f"{C_INFO}[AKUN]{Style.RESET_ALL} {C_INFO}{masked_address}{Style.RESET_ALL}", level="INFO")
        print(C_SEPARATOR + Style.BRIGHT + "-" * 60 + Style.RESET_ALL)

        if original_address not in self.access_tokens or original_address not in self.refresh_tokens:
            self.log_account_specific(masked_address, "Token tidak ditemukan. Memulai proses pembuatan token...", level="INFO")
            if not await self.process_generate_new_token(masked_address, original_address, use_proxy_flag):
                self.log_account_specific(masked_address, "Gagal total membuat token awal. Tidak dapat melanjutkan.", level="ERROR")
                return # Hentikan task ini untuk akun ini

        # Whitelist (setelah token dipastikan ada)
        if original_address in self.access_tokens: # Pastikan token ada sebelum whitelist
            proxy_for_whitelist = self.get_next_proxy_for_account(original_address) if use_proxy_flag else None
            proxy_info_str_whitelist = proxy_for_whitelist if proxy_for_whitelist else "Tidak Digunakan"
            self.log_account_specific(masked_address, "Menambahkan ke whitelist...", level="DEBUG")
            
            if await self.add_to_whitelist(masked_address, original_address, self.access_tokens[original_address], proxy_for_whitelist):
                self.log_account_specific(masked_address, "", level="SUCCESS", proxy_info=proxy_info_str_whitelist, status_msg="Berhasil ditambahkan/sudah ada di whitelist.")
            # else: # Pesan error/warning sudah dari add_to_whitelist
        else:
            self.log_account_specific(masked_address, "Token tidak tersedia, tidak dapat menambahkan ke whitelist.", level="WARNING")


        ping_interval_seconds = 60
        initiate_msg_interval_seconds = 10 * 60
        activation_check_interval_seconds = 5 * 60 

        last_ping_time = 0
        last_initiate_msg_time = 0
        last_activation_check_time = 0
        
        while True: # Loop utama operasi akun
            if original_address not in self.access_tokens: # Jika token hilang di tengah jalan
                self.log_account_specific(masked_address, "Access token hilang, mencoba regenerate...", level="WARNING")
                if not await self.process_generate_new_token(masked_address, original_address, use_proxy_flag):
                    self.log_account_specific(masked_address, "Gagal regenerate token. Melewatkan siklus ini.", level="ERROR")
                    await asyncio.sleep(60) # Tunggu sebelum coba lagi
                    continue # Kembali ke awal loop while True
            
            current_time = asyncio.get_event_loop().time()
            # Dapatkan proxy untuk siklus operasi ini
            current_op_proxy = self.get_next_proxy_for_account(original_address) if use_proxy_flag else None
            current_op_proxy_info = current_op_proxy if current_op_proxy else "Tidak Digunakan"
            
            perform_actions_after_activation = False # Flag apakah tindakan inti (ping/initiate) boleh dilakukan

            # --- Pemeriksaan dan Proses Aktivasi ---
            if current_time - last_activation_check_time > activation_check_interval_seconds:
                self.log_account_specific(masked_address, "Memeriksa status aktivasi...", level="DEBUG")
                # Selalu coba matikan dulu untuk memastikan state bersih, kecuali jika API tidak mengizinkan atau error
                deactivate_response = await self.toggle_device_activation(masked_address, original_address, device_hash, self.access_tokens[original_address], "OFF", current_op_proxy)
                
                if deactivate_response is not None and deactivate_response in ["Session ended and daily usage updated", "No action needed", "Session not found to end"]:
                    self.log_account_specific(masked_address, "", level="INFO", proxy_info=current_op_proxy_info, status_msg=f"Status Deaktivasi: {deactivate_response}. Mencoba aktivasi ON...")
                    
                    activate_response = await self.toggle_device_activation(masked_address, original_address, device_hash, self.access_tokens[original_address], "ON", current_op_proxy)
                    if activate_response is not None and activate_response == "Session started":
                        self.log_account_specific(masked_address, "", level="SUCCESS", proxy_info=current_op_proxy_info, status_msg="Aktivasi Perangkat (ON) Berhasil.")
                        perform_actions_after_activation = True
                    elif activate_response is not None and activate_response == "Session already active for this device":
                         self.log_account_specific(masked_address, "", level="INFO", proxy_info=current_op_proxy_info, status_msg="Aktivasi Perangkat (ON): Sudah Aktif.")
                         perform_actions_after_activation = True # Jika sudah aktif, tetap lakukan tindakan
                    elif activate_response is not None: # Ada respons tapi bukan sukses
                        self.log_account_specific(masked_address, "", level="ERROR", proxy_info=current_op_proxy_info, status_msg=f"Aktivasi Perangkat (ON) Gagal. Respons: {activate_response}")
                    else: # activate_response is None (error parah)
                         self.log_account_specific(masked_address, "", level="ERROR", proxy_info=current_op_proxy_info, status_msg="Aktivasi Perangkat (ON) Gagal (tidak ada respons).")

                elif deactivate_response is not None: # Gagal matikan tapi ada respons
                    self.log_account_specific(masked_address, "", level="ERROR", proxy_info=current_op_proxy_info, status_msg=f"Deaktivasi (OFF) Gagal: {deactivate_response}. Aktivasi ON tidak dilanjutkan.")
                else: # Gagal matikan dan tidak ada respons
                    self.log_account_specific(masked_address, "", level="ERROR", proxy_info=current_op_proxy_info, status_msg="Deaktivasi (OFF) Gagal (tidak ada respons). Aktivasi ON tidak dilanjutkan.")
                last_activation_check_time = current_time
            else: # Belum waktunya cek aktivasi, asumsikan state sebelumnya masih valid
                 if original_address in self.access_tokens : # Minimal token ada
                    perform_actions_after_activation = True


            # --- Tindakan Inti (Ping & Initiate Message) ---
            if perform_actions_after_activation:
                # Initiate Message Production
                if current_time - last_initiate_msg_time > initiate_msg_interval_seconds :
                    self.log_account_specific(masked_address, "Mengirim initiate message production...", level="DEBUG")
                    if await self.initiate_message_production(masked_address, original_address, device_hash, self.access_tokens[original_address], current_op_proxy):
                        self.log_account_specific(masked_address, "", level="SUCCESS", proxy_info=current_op_proxy_info, status_msg="Initiate Message Production Berhasil.")
                    # else: # Pesan error sudah dari fungsi initiate_message_production
                    last_initiate_msg_time = current_time
                
                # Perform Ping
                if current_time - last_ping_time > ping_interval_seconds:
                    self.log_account_specific(masked_address, "Melakukan ping...", level="DEBUG")
                    if await self.perform_ping(masked_address, original_address, self.access_tokens[original_address], current_op_proxy):
                        self.log_account_specific(masked_address, "", level="SUCCESS", proxy_info=current_op_proxy_info, status_msg="Ping Berhasil.")
                    # else: # Pesan error sudah dari fungsi perform_ping
                    last_ping_time = current_time

            await asyncio.sleep(30) # Jeda utama antar siklus pengecekan di loop utama

    async def run_bot(self):
        self.clear_terminal()
        self.display_banner()

        accounts = self.load_accounts_from_file()
        if not accounts:
            self.log("Tidak ada akun yang dimuat. Bot berhenti.", level="ERROR")
            return

        use_proxy_flag = self.ask_use_proxy()

        if use_proxy_flag:
            await self.load_proxies_from_local_file()
            if not self.proxies:
                self.log("Tidak ada proxy yang tersedia di 'proxies.txt'. Melanjutkan tanpa proxy.", level="WARNING")
                use_proxy_flag = False # Set ulang flag jika tidak ada proxy

        self.log(f"Memulai proses untuk {len(accounts)} akun...", level="INFO")

        tasks = []
        for account_data in accounts:
            original_address = account_data["Address"].lower()
            try:
                device_hash = int(str(account_data["deviceHash"]))
            except ValueError:
                self.log(f"Akun dengan alamat {C_WARNING}{self._mask_address(original_address)}{C_ERROR} memiliki deviceHash tidak valid: {C_WARNING}{account_data['deviceHash']}{C_ERROR}. Akun ini dilewati.", level="ERROR")
                continue
            
            masked_address = self._mask_address(original_address)

            # Membuat tasks untuk setiap akun
            tasks.append(asyncio.create_task(self.main_account_operations_task(original_address, device_hash, use_proxy_flag)))
            tasks.append(asyncio.create_task(self.periodic_refresh_token_task(masked_address, original_address, use_proxy_flag)))
            tasks.append(asyncio.create_task(self.periodic_wallet_details_task(masked_address, original_address, use_proxy_flag)))
            
            await asyncio.sleep(1) # Jeda singkat antar start task akun agar tidak membanjiri API sekaligus

        if tasks:
            await asyncio.gather(*tasks)
        else:
            self.log("Tidak ada tugas yang valid yang dibuat untuk akun.", level="WARNING")

if __name__ == "__main__":
    bot = NaorisProtocolAutomation()
    try:
        asyncio.run(bot.run_bot())
    except KeyboardInterrupt:
        bot.log("Bot dihentikan oleh pengguna (KeyboardInterrupt).", level="INFO")
    except Exception as e:
        bot.log(f"Terjadi error tidak terduga di level utama: {e}", level="ERROR")
        import traceback
        traceback.print_exc() # Cetak traceback untuk debug error tak terduga
    finally:
        bot.log("Bot Selesai.", level="INFO")