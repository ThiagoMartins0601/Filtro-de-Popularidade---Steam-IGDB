import json
import os
import time
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional

class DataTracker:
    def __init__(self, state_file_path: str):
        self.state_file = state_file_path
        self.last_id = self._load_state()

    def _load_state(self) -> int:
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r', encoding='utf-8') as f:
                try:
                    return json.load(f).get("last_processed_id", 0)
                except json.JSONDecodeError:
                    return 0
        return 0

    def update_state(self, game_id: int):
        self.last_id = game_id
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump({"last_processed_id": self.last_id}, f)


class APIClient:
    def __init__(self):
        self.igdb_client_id = "kt6rr80i311s2udjn6919hyg9p8k69"
        self.igdb_auth_token = "tow62f9zmuji4qjfd67q71cszuifgs"
        self.igdb_client_secret = "vkj1pl68m9bpi7w00f3w2qvyjyxjjr" 
        
        self._update_headers()
        self.rate_limit_delay = 0.5 

    def _update_headers(self):
        self.headers_igdb = {
            'Client-ID': self.igdb_client_id,
            'Authorization': f'Bearer {self.igdb_auth_token}',
            'Accept': 'application/json'
        }

    def refresh_igdb_token(self) -> bool:
        if not self.igdb_client_secret:
            print("\n[ERRO] client_secret não fornecido. Impossível gerar um novo token automaticamente.")
            return False
            
        url = f"https://id.twitch.tv/oauth2/token?client_id={self.igdb_client_id}&client_secret={self.igdb_client_secret}&grant_type=client_credentials"
        
        try:
            response = requests.post(url)
            response.raise_for_status()
            
            new_data = response.json()
            self.igdb_auth_token = new_data['access_token']
            self._update_headers() 
            print("\n[SUCESSO] Novo token da Twitch obtido e aplicado!")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"\n[ERRO] Falha ao tentar obter novo token: {e}")
            return False

    def fetch_igdb_games(self, start_id: int, limit: int = 50) -> List[Dict]:
        url = "https://api.igdb.com/v4/games"
        safe_start_id = int(start_id) if start_id else 0
        
        where_clause = f"id > {safe_start_id} & first_release_date >= 978307200 & total_rating != null & websites != null"

        query = f"fields id, name, genres.name, total_rating, first_release_date, websites.*; where {where_clause}; sort id asc; limit {limit};"
        
        try:
            response = requests.post(url, headers=self.headers_igdb, data=query)
            
            if response.status_code == 401:
                print("\n[AVISO] Token expirado. Tentando renovar...")
                if self.refresh_igdb_token():
                    response = requests.post(url, headers=self.headers_igdb, data=query)
                else:
                    return [] 

            response.raise_for_status()
            time.sleep(self.rate_limit_delay)
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"\n[ERRO] Falha ao buscar no IGDB: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Detalhe exato do erro IGDB: {e.response.text}")
            return []

    def extract_steam_appid(self, websites: List[Dict]) -> Optional[str]:
        if not websites:
            return None
        for site in websites:
            if site.get("category") == 13: 
                url = site.get("url", "")
                if "/app/" in url:
                    parts = url.split("/app/")
                    if len(parts) > 1:
                        clean_id = parts[1].split("/")[0].strip()
                        if clean_id.isdigit():
                            return clean_id
        return None


class GameDataPipeline:
    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.join(current_dir, "Dados Numericos")
        os.makedirs(self.output_dir, exist_ok=True)
        
        tracker_path = os.path.join(self.output_dir, "tracker_state.json")
        self.tracker = DataTracker(tracker_path)
        
        self.api_client = APIClient()
        self.numerical_output_file = os.path.join(self.output_dir, "rpgdados.json")

    def convert_timestamp(self, unix_timestamp: Optional[int]) -> str:
        if not unix_timestamp:
            return "Unknown"
        try:
            return datetime.fromtimestamp(unix_timestamp).strftime('%Y-%m-%d')
        except Exception:
            return "Unknown"

    def run_batch(self) -> bool:
        start_id = self.tracker.last_id
        
        igdb_games = self.api_client.fetch_igdb_games(start_id, limit=50)
        
        if not igdb_games:
            print("  -> Nenhum dado retornado (Fim do banco de dados ou erro).")
            return False 

        numerical_results = []
        last_processed = start_id

        for game in igdb_games:
            game_id = game.get("id")
            title = game.get("name", "Unknown")
            
            genres = [g.get("name") for g in game.get("genres", [])]
            genre_str = ", ".join(genres) if genres else "Unknown"
            
            igdb_score = game.get("total_rating", 0)
            release_date = self.convert_timestamp(game.get("first_release_date"))

            websites = game.get("websites", [])
            steam_appid = self.api_client.extract_steam_appid(websites)

            processed_num = {
                "game_id": game_id,
                "title": title,
                "release_date": release_date,
                "genres_string": genre_str,
                "steam_appid": steam_appid if steam_appid else None, 
                "numerical_metrics": {
                    "igdb_rating_raw": round(igdb_score, 2) if igdb_score else 0
                }
            }
            
            numerical_results.append(processed_num)
            
            last_processed = game_id
            print(f"  -> Processado ID {game_id}: {title} | Ano: {release_date[:4]} | SteamID: {steam_appid if steam_appid else 'Nenhum'}")

        self.tracker.update_state(last_processed)
        self._append_to_json(self.numerical_output_file, numerical_results)
        
        return True 

    def _append_to_json(self, filepath: str, new_data: List[Dict]):
        if not new_data:
            return
            
        existing_data = []
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    pass
        
        existing_data.extend(new_data)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=4, ensure_ascii=False)


    def run_pipeline(self, num_batches: int = 15):
        print(f"Iniciando rotina de mineração ({num_batches} lotes programados).")
        print(f"Salvando dados estruturais em: {self.numerical_output_file}\n")
        
        for i in range(num_batches):
            print(f"--- Iniciando Lote {i+1}/{num_batches} (ID Inicial: {self.tracker.last_id}) ---")
            
            sucesso = self.run_batch()
            
            if not sucesso:
                print("Interrompendo a rotina antecipadamente.")
                break
                
            time.sleep(0.5)
            
        print("\nRotina finalizada. Fechando programa.")


if __name__ == "__main__":
    pipeline = GameDataPipeline()
    pipeline.run_pipeline(num_batches=100)