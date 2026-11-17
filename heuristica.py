import json
import os
import math
import time
import networkx as nx
from typing import Dict, List, Any
from collections import defaultdict

class MassiveOptimizationAndDualPipeline:
    def __init__(self, json_path: str = "Dados Numericos/bancodados_completo.json"):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.file_path = os.path.join(current_dir, json_path)
        self.output_dir = os.path.join(current_dir, "Dados Numericos")
        self.raw_games = self._load_data()

    def _load_data(self) -> List[Dict]:
        if not os.path.exists(self.file_path):
            print(f"[ERRO] Arquivo não encontrado: {self.file_path}")
            return []
        with open(self.file_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("[ERRO] Arquivo JSON corrompido.")
                return []

    def _prepare_processed_games(self) -> List[Dict]:
        processed = []
        for idx, g in enumerate(self.raw_games):
            metrics = g.get("numerical_metrics", {})
            genres_raw = g.get("genres_string", "")
            title = g.get("title", "")
            
            genre_list = [genre.strip().lower() for genre in genres_raw.split(",") if genre.strip() and genre.strip().lower() != "unknown"]
            primary_genre = genre_list[0] if genre_list else "unknown"
            genres_set = set(genre_list)

            is_sim_racing = (
                ("racing" in genres_set or "simulation" in genres_set) and 
                any(keyword in title.lower() for keyword in ["iracing", "assetto", "factor", "automobilista", "sim", "rally"])
            ) or ("iracing" in title.lower())

            if "iracing" in title.lower():
                primary_genre = "simulation"

            rating = metrics.get("igdb_rating_raw", 0.0) or metrics.get("critic_score_raw", 0.0)
            players = math.log1p(metrics.get("current_steam_players_raw", 0))
            owners = math.log1p(metrics.get("estimated_owners_raw", 0))

            processed.append({
                "original_index": idx,
                "original_data": g,
                "title": title,
                "primary_genre": primary_genre,
                "genres_set": genres_set,
                "is_sim_racing": is_sim_racing,
                "rating": rating,
                "players": players,
                "owners": owners
            })
        return processed

    def calculate_similarity(self, game_a: Dict, game_b: Dict, weights: Dict[str, float]) -> float:
        genres_a = game_a["genres_set"]
        genres_b = game_b["genres_set"]
        if genres_a or genres_b:
            intersection = len(genres_a.intersection(genres_b))
            union = len(genres_a.union(genres_b))
            genre_sim = intersection / union if union > 0 else 0.0
        else:
            genre_sim = 0.0

        rating_sim = 1.0 - (abs(game_a["rating"] - game_b["rating"]) / 100.0)
        player_sim = max(0.0, 1.0 - (abs(game_a["players"] - game_b["players"]) / 15.0))
        owner_sim = max(0.0, 1.0 - (abs(game_a["owners"] - game_b["owners"]) / 15.0))

        if game_a["is_sim_racing"] and game_b["is_sim_racing"]:
            w_g = weights.get("sim_genre", 0.2)
            w_r = weights.get("sim_rating", 0.1)
            w_p = weights.get("sim_players", 0.4)
            w_o = weights.get("sim_owners", 0.3)
        else:
            w_g = weights["genre"]
            w_r = weights["rating"]
            w_p = weights["players"]
            w_o = weights["owners"]

        total_weight = w_g + w_r + w_p + w_o
        if total_weight == 0:
            return 0.0

        return (
            (genre_sim * w_g) +
            (rating_sim * w_r) +
            (player_sim * w_p) +
            (owner_sim * w_o)
        ) / total_weight

    def evaluate_weights(self, weights: Dict[str, float], processed_games: List[Dict], threshold: float = 0.60) -> float:
        primary_genre_buckets = defaultdict(list)
        for idx, g in enumerate(processed_games):
            primary_genre_buckets[g["primary_genre"]].append(idx)

        G = nx.Graph()
        for idx in range(len(processed_games)):
            G.add_node(idx)

        compared_pairs = set()
        for genre, indices in primary_genre_buckets.items():
            bucket_len = len(indices)
            for i in range(bucket_len):
                idx_a = indices[i]
                for j in range(i + 1, bucket_len):
                    idx_b = indices[j]
                    pair = (min(idx_a, idx_b), max(idx_a, idx_b))
                    if pair in compared_pairs:
                        continue
                    compared_pairs.add(pair)
                    
                    sim = self.calculate_similarity(processed_games[idx_a], processed_games[idx_b], weights)
                    if sim >= threshold:
                        G.add_edge(idx_a, idx_b, weight=sim)

        iracing_indices = [i for i, g in enumerate(processed_games) if "iracing" in g["title"].lower()]
        if not iracing_indices or G.number_of_edges() == 0:
            return 0.0

        centrality = nx.degree_centrality(G)
        iracing_score = sum(centrality.get(idx, 0) for idx in iracing_indices) / len(iracing_indices)
        density = nx.density(G)

        return (iracing_score * 0.75) + (density * 0.25)

    def run_mass_simulation_and_generate_jsons(self):
        if not self.raw_games:
            print("[ERRO] Nenhum jogo carregado.")
            return

        processed_games = self._prepare_processed_games()

        simulation_grid = []
        for g in [0.2, 0.4]:
            for r in [0.1, 0.2, 0.3]:
                for p in [0.1, 0.2, 0.3, 0.4]:
                    for o in [0.1, 0.2, 0.3]:
                        for sim_p in [0.3, 0.4, 0.5]:
                            for sim_o in [0.3, 0.5]:
                                simulation_grid.append({
                                    "genre": g,
                                    "rating": r,
                                    "players": p,
                                    "owners": o,
                                    "sim_genre": 0.2,
                                    "sim_rating": 0.1,
                                    "sim_players": sim_p,
                                    "sim_owners": sim_o
                                })

        total_cases = len(simulation_grid)
        print(f"Iniciando simulações com {len(processed_games)} jogos. Total de casos ajustado para: {total_cases}\n")

        scored_results = []
        start_time = time.time()

        for idx, config in enumerate(simulation_grid, start=1):
            score = self.evaluate_weights(config, processed_games)
            scored_results.append((score, config))

            percent = (idx / total_cases) * 100
            elapsed = time.time() - start_time
            avg_time = elapsed / idx
            eta = avg_time * (total_cases - idx)

            print(f"[{idx:3d}/{total_cases} | {percent:5.1f}%] Score: {score:.5f} | Decorrido: {elapsed:.1f}s | Restante: {eta:.1f}s", end="\r")

        print("\n\n" + "="*60)
        print("[SUCESSO] Simulações concluídas! Analisando os melhores cenários...")
        
        scored_results.sort(key=lambda x: x[0], reverse=True)

        top_cases = []
        seen_scores = set()
        for score, config in scored_results:
            if score not in seen_scores and len(top_cases) < 2:
                seen_scores.add(score)
                top_cases.append((score, config))

        for idx, (score, cfg) in enumerate(top_cases):
            print(f"  -> Caso #{idx + 1} | Score: {score:.5f} | Pesos: {cfg}")
        print("="*60 + "\n")

        for case_num, (score, weights) in enumerate(top_cases, start=1):
            filename = f"bancodados_clusterizado_caso{case_num}.json"
            output_path = os.path.join(self.output_dir, filename)
            print(f"Gerando JSON do Caso #{case_num} -> '{filename}'...")

            primary_genre_buckets = defaultdict(list)
            for idx, g in enumerate(processed_games):
                primary_genre_buckets[g["primary_genre"]].append(idx)

            G = nx.Graph()
            for idx in range(len(processed_games)):
                G.add_node(idx)

            compared_pairs = set()
            for genre, indices in primary_genre_buckets.items():
                bucket_len = len(indices)
                for i in range(bucket_len):
                    idx_a = indices[i]
                    for j in range(i + 1, bucket_len):
                        idx_b = indices[j]
                        pair = (min(idx_a, idx_b), max(idx_a, idx_b))
                        if pair in compared_pairs:
                            continue
                        compared_pairs.add(pair)
                        
                        sim = self.calculate_similarity(processed_games[idx_a], processed_games[idx_b], weights)
                        if sim >= 0.60:
                            cost = max(0.01, 1.0 - sim)
                            G.add_edge(idx_a, idx_b, weight=sim, distance=cost)

            anchor_nodes = []
            for genre, indices in primary_genre_buckets.items():
                best_idx = max(indices, key=lambda i: processed_games[i]["rating"] + (processed_games[i]["players"] * 1.5 if processed_games[i]["is_sim_racing"] else processed_games[i]["players"]))
                anchor_nodes.append(best_idx)

            importance_scores = defaultdict(float)
            for anchor in anchor_nodes:
                if anchor in G:
                    try:
                        lengths, paths = nx.single_source_dijkstra(G, source=anchor, weight='distance')
                        for target, path in paths.items():
                            path_len = len(path)
                            for node in path:
                                importance_scores[node] += (1.0 / path_len)
                    except nx.NetworkXNoPath:
                        continue

            sorted_nodes = sorted(G.nodes(), key=lambda n: importance_scores.get(n, 0), reverse=True)
            total_nodes = len(processed_games)
            tier_size = max(1, total_nodes // 5)

            coloring = {}
            for rank, node_idx in enumerate(sorted_nodes):
                if processed_games[node_idx]["is_sim_racing"] and rank < (tier_size * 2):
                    coloring[node_idx] = 0
                else:
                    tier_level = min(4, rank // tier_size)
                    coloring[node_idx] = tier_level

            output_database = []
            for idx, item in enumerate(processed_games):
                orig_game = item["original_data"]
                orig_game["cluster_id"] = coloring.get(idx, 0)
                output_database.append(orig_game)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_database, f, indent=4, ensure_ascii=False)
            print(f"  [OK] Arquivo gerado: {output_path}")

        print("\n[SUCESSO] Processamento concluído com controle de tempo e progresso!")

if __name__ == "__main__":
    optimizer = MassiveOptimizationAndDualPipeline()
    optimizer.run_mass_simulation_and_generate_jsons()