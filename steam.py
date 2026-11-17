import json
import os
import time
import requests
import re
from typing import Dict, Any, Optional

class SteamEnricherByName:
    def __init__(self, base_file: str = "igdbdados.json", output_file: str = "steamdados.json"):

        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.join(current_dir, "Dados Numericos")
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.base_file_path = os.path.join(self.output_dir, base_file)
        self.output_file_path = os.path.join(self.output_dir, output_file)
        self.progress_file = os.path.join(self.output_dir, "steam_progress.json")
        
        self.rate_limit_delay = 1.5 
        
        self.last_processed_index = self._load_progress()

    def _load_progress(self) -> int:
        if os.path.exists(self.progress_file):
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                try:
                    return json.load(f).get("last_index", 0)
                except json.JSONDecodeError:
                    return 0
        return 0

    def _save_progress(self, index: int):
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump({"last_index": index}, f)

    def _save_database(self, database: list):
        """Função robusta de gravação com tratamento de erros."""
        try:
            with open(self.output_file_path, 'w', encoding='utf-8') as f:
                json.dump(database, f, indent=4, ensure_ascii=False)
            print(f"  [SISTEMA] Arquivo salvo/atualizado com sucesso em: {self.output_file_path}")
        except Exception as e:
            print(f"  [ERRO GRAVAÇÃO] Não foi possível salvar o arquivo! Detalhe: {e}")

    def _clean_title_for_search(self, title: str) -> str:
        clean = title.replace("é", "e").replace("á", "a").replace("í", "i").replace("ó", "o").replace("ú", "u")
        clean = re.sub(r'[^\w\s]', '', clean)
        return clean.strip()

    def search_game_on_steam(self, game_name: str) -> Optional[str]:
        search_term = self._clean_title_for_search(game_name)
        url = f"https://store.steampowered.com/api/storesearch/?term={search_term}&l=english&cc=US"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("total", 0) > 0 and data.get("items"):
                first_item = data["items"][0]
                steam_name = first_item.get("name", "").lower()
                
                if len(search_term) > 2:
                    first_word = search_term.split()[0].lower()
                    if first_word in steam_name:
                        return str(first_item.get("id"))
                else:
                    return str(first_item.get("id"))
                    
            return None
        except requests.exceptions.RequestException:
            return None

    def fetch_steam_details(self, app_id: str) -> Optional[Dict]:
        store_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"
        players_url = f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={app_id}"
        
        try:
            store_res = requests.get(store_url, timeout=10)
            store_res.raise_for_status()
            store_data = store_res.json()
            
            if not store_data or str(app_id) not in store_data or not store_data[str(app_id)].get("success"):
                return None
                
            game_details = store_data[str(app_id)]["data"]
            
            players_res = requests.get(players_url, timeout=10)
            players_res.raise_for_status()
            players_data = players_res.json()
            
            current_players = players_data.get("response", {}).get("player_count", 0)
            
            recommendations = game_details.get("recommendations", {}).get("total", 0)
            estimated_owners = recommendations * 30 
            
            supported_languages = game_details.get("supported_languages", "English")

            time.sleep(self.rate_limit_delay) 
            
            return {
                "steam_appid_found": app_id,
                "current_steam_players_raw": current_players,
                "estimated_owners_raw": estimated_owners,
                "total_steam_recommendations": recommendations,
                "target_regions_by_language": supported_languages
            }

        except requests.exceptions.RequestException:
            time.sleep(self.rate_limit_delay)
            return None

    def _mark_as_failed(self, game: Dict):
        game["numerical_metrics"].update({
            "steam_appid_found": None,
            "current_steam_players_raw": 0,
            "estimated_owners_raw": 0,
            "total_steam_recommendations": 0,
            "target_regions_by_language": "Not on Steam"
        })

    def run_enrichment(self):
        # Lógica inteligente para carregar o arquivo certo
        if os.path.exists(self.output_file_path):
            print(f"Continuando enriquecimento a partir de: {self.output_file_path}")
            file_to_load = self.output_file_path
        elif os.path.exists(self.base_file_path):
            print(f"Iniciando novo enriquecimento a partir do arquivo base: {self.base_file_path}")
            file_to_load = self.base_file_path
        else:
            print(f"[ERRO] Nem o arquivo base ({self.base_file_path}) nem o final ({self.output_file_path}) foram encontrados.")
            return

        try:
            with open(file_to_load, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                database = json.loads(content) if content else []
        except Exception as e:
            print(f"[ERRO] O arquivo JSON está corrompido ou inacessível. Detalhe: {e}")
            return

        total_games = len(database)
        if total_games == 0:
            print("O arquivo JSON está vazio. Não há jogos para processar.")
            return
            
        print(f"Total de jogos na base: {total_games}")
        print(f"Retomando a partir do índice: {self.last_processed_index}\n")
        
        changes_made = False

        for i in range(self.last_processed_index, total_games):
            game = database[i]
            title = game.get("title", "Unknown")
            
            metrics = game.get("numerical_metrics", {})
            already_enriched = "current_steam_players_raw" in metrics
            
            if not already_enriched:
                print(f"[{i+1}/{total_games}] Buscando: {title}...", end=" ")
                
                discovered_appid = self.search_game_on_steam(title)
                time.sleep(self.rate_limit_delay) 
                
                if discovered_appid:
                    print(f"Achou! (ID: {discovered_appid})", end=" -> ")
                    steam_data = self.fetch_steam_details(discovered_appid)
                    
                    if steam_data:
                        game["numerical_metrics"].update(steam_data)
                        changes_made = True
                        print(f"Sucesso! ({steam_data['current_steam_players_raw']} online)")
                    else:
                        print("Detalhes bloqueados.")
                        self._mark_as_failed(game)
                        changes_made = True
                else:
                    print("Não existe na Steam.")
                    self._mark_as_failed(game)
                    changes_made = True
            
            self._save_progress(i + 1)
            
            if changes_made and i % 10 == 0:
                self._save_database(database)
                changes_made = False

        if changes_made:
            self._save_database(database)
            
        print("\nProcesso de enriquecimento 100% concluído!")

if __name__ == "__main__":
    enricher = SteamEnricherByName()
    enricher.run_enrichment()

    #Data de recolhimento dos primeiros dados de players ativos e estimativas 12/08/2026 há 13/08 16:30