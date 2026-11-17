import json
import os
import time
import requests
from typing import Dict, Any, Optional

class IGDBRatingsEnricher:
    def __init__(self, base_file: str = "steamdados.json", output_file: str = "opencrit.json"):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.join(current_dir, "Dados Numericos")
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.base_file_path = os.path.join(self.output_dir, base_file)
        self.output_file_path = os.path.join(self.output_dir, output_file)
        self.progress_file = os.path.join(self.output_dir, "igdb_ratings_progress.json")
        
        self.igdb_client_id = "kt6rr80i311s2udjn6919hyg9p8k69"
        self.igdb_auth_token = "tow62f9zmuji4qjfd67q71cszuifgs"
        self.igdb_client_secret = "vkj1pl68m9bpi7w00f3w2qvyjyxjjr" 
        
        self._update_headers()
        self.rate_limit_delay = 0.3 
        
        self.last_processed_index = self._load_progress()

    def _update_headers(self):
        self.headers_igdb = {
            'Client-ID': self.igdb_client_id,
            'Authorization': f'Bearer {self.igdb_auth_token}',
            'Accept': 'application/json'
        }

    def refresh_igdb_token(self) -> bool:
        url = f"https://id.twitch.tv/oauth2/token?client_id={self.igdb_client_id}&client_secret={self.igdb_client_secret}&grant_type=client_credentials"
        try:
            response = requests.post(url)
            response.raise_for_status()
            self.igdb_auth_token = response.json()['access_token']
            self._update_headers() 
            print("\n[SUCESSO] Novo token da Twitch obtido!")
            return True
        except requests.exceptions.RequestException:
            return False

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
        try:
            with open(self.output_file_path, 'w', encoding='utf-8') as f:
                json.dump(database, f, indent=4, ensure_ascii=False)
            print(f"  [SISTEMA] Checkpoint salvo no arquivo final.")
        except Exception as e:
            print(f"  [ERRO GRAVAÇÃO] Falha ao salvar: {e}")

    def fetch_ratings_by_id(self, game_id: int) -> Optional[Dict]:
        """Busca a nota da Crítica e do Usuário usando o ID exato do jogo no IGDB."""
        url = "https://api.igdb.com/v4/games"
        
        query = f"fields aggregated_rating, rating; where id = {game_id};"
        
        try:
            response = requests.post(url, headers=self.headers_igdb, data=query)
            
            if response.status_code == 401:
                if self.refresh_igdb_token():
                    response = requests.post(url, headers=self.headers_igdb, data=query)
                else:
                    return None

            response.raise_for_status()
            time.sleep(self.rate_limit_delay)
            
            data = response.json()
            if data and len(data) > 0:
                game_data = data[0]
                
                critic_score = game_data.get("aggregated_rating")
                user_score = game_data.get("rating")
                
                return {
                    "critic_score_raw": round(critic_score, 2) if critic_score else 0.0,
                    "user_score_raw": round(user_score, 2) if user_score else 0.0
                }
            return None
            
        except requests.exceptions.RequestException:
            time.sleep(self.rate_limit_delay)
            return None

    def _mark_as_failed(self, game: Dict):
        game["numerical_metrics"].update({
            "critic_score_raw": 0.0,
            "user_score_raw": 0.0
        })

    def run_enrichment(self):
        if os.path.exists(self.output_file_path):
            print(f"Continuando extração de Notas a partir de: {self.output_file_path}")
            file_to_load = self.output_file_path
        elif os.path.exists(self.base_file_path):
            print(f"Iniciando extração de Notas a partir de: {self.base_file_path}")
            file_to_load = self.base_file_path
        else:
            print(f"[ERRO] Arquivo {self.base_file_path} não encontrado. Execute o script da Steam primeiro.")
            return

        try:
            with open(file_to_load, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                database = json.loads(content) if content else []
        except Exception as e:
            print(f"[ERRO] Arquivo JSON corrompido: {e}")
            return

        total_games = len(database)
        if total_games == 0:
            print("O arquivo JSON está vazio.")
            return
            
        print(f"Total de jogos para extrair notas: {total_games}")
        print(f"Retomando do índice: {self.last_processed_index}\n")
        
        changes_made = False

        for i in range(self.last_processed_index, total_games):
            game = database[i]
            game_id = game.get("game_id") 
            title = game.get("title", "Unknown")
            
            metrics = game.get("numerical_metrics", {})
            already_enriched = "critic_score_raw" in metrics
            
            if not already_enriched and game_id:
                print(f"[{i+1}/{total_games}] Puxando notas para: {title}...", end=" ")
                
                ratings_data = self.fetch_ratings_by_id(game_id)
                
                if ratings_data:
                    game["numerical_metrics"].update(ratings_data)
                    changes_made = True
                    print(f"Sucesso! (Crítica: {ratings_data['critic_score_raw']} | Usuários: {ratings_data['user_score_raw']})")
                else:
                    print("Sem avaliações suficientes ainda.")
                    self._mark_as_failed(game)
                    changes_made = True
            
            self._save_progress(i + 1)
            
            if changes_made and i % 20 == 0:
                self._save_database(database)
                changes_made = False

        if changes_made:
            self._save_database(database)
            
        print("\nProcesso 100% concluído! O seu banco de dados final está perfeito e enriquecido com todas as métricas.")

if __name__ == "__main__":
    enricher = IGDBRatingsEnricher()
    enricher.run_enrichment()