import json
import os
import math
import random
import time
import networkx as nx
from collections import defaultdict
from typing import Dict, List, Any

class KagglePipelineWithDetailedTimer:
    def __init__(self, json_input_filename: str = "steam_games.json", legacy_json_path: str = "bancodados_completo.json", output_path: str = "bancodados_kaggle_unificado.json"):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(current_dir, "Dados Numericos")
        self.kaggle_json_path = os.path.join(self.data_dir, json_input_filename)
        self.legacy_json_path = os.path.join(self.data_dir, legacy_json_path)
        self.output_path = os.path.join(self.data_dir, output_path)

    def _load_legacy_data(self) -> List[Dict]:
        if not os.path.exists(self.legacy_json_path):
            return []
        with open(self.legacy_json_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

    def _parse_kaggle_json_games(self) -> List[Dict]:
        """Lê o JSON do Kaggle com tracker de tempo e progresso."""
        if not os.path.exists(self.kaggle_json_path):
            print(f"\n[ERRO CRÍTICO] Arquivo JSON não encontrado em: {self.kaggle_json_path}")
            return []

        print(f"Carregando e decodificando o JSON do Kaggle: {self.kaggle_json_path}...")
        start_time = time.time()
        
        with open(self.kaggle_json_path, 'r', encoding='utf-8') as f:
            try:
                raw_data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"[ERRO] Falha ao decodificar o JSON: {e}")
                return []

        if not isinstance(raw_data, dict):
            print("[ERRO] O JSON fornecido não está no formato de dicionário por AppID.")
            return []

        total_items = len(raw_data)
        print(f"Total de registros brutos encontrados: {total_items}. Extraindo dados...")

        parsed_games = []
        for idx, (appid_str, row) in enumerate(raw_data.items(), start=1):
            if not isinstance(row, dict):
                continue

            title = row.get("name") or row.get("title") or row.get("Name") or "Desconhecido"
            if not title or str(title).strip() == "Desconhecido" or str(title).strip() == "":
                continue

            release_date = row.get("release_date") or row.get("Release Date") or "2020-01-01"
            year = "2020"
            for part in str(release_date).split("-") + str(release_date).split("/"):
                if part.strip().isdigit() and len(part.strip()) == 4:
                    year = part.strip()
                    break

            try:
                players = float(row.get("peak_ccu") or row.get("current_steam_players") or 0)
            except ValueError:
                players = 0.0

            est_owners_str = str(row.get("estimated_owners", "1000 - 5000"))
            owners = 1000.0
            try:
                digits = "".join([c for c in est_owners_str.split("-")[0] if c.isdigit()])
                if digits:
                    owners = float(digits)
            except Exception:
                owners = 1000.0

            try:
                rating = float(row.get("user_score") or row.get("metacritic_score") or row.get("positive") or 70.0)
                if rating == 0:
                    rating = 70.0
            except ValueError:
                rating = 70.0

            genres_raw = row.get("genres", [])
            if isinstance(genres_raw, list):
                genres_str = ", ".join(genres_raw)
            elif isinstance(genres_raw, str):
                genres_str = genres_raw
            else:
                genres_str = "Simulation, Action"

            parsed_games.append({
                "title": str(title).strip(),
                "release_date": str(release_date).strip(),
                "release_year": str(year),
                "genres_string": str(genres_str).strip(),
                "steam_appid": int(appid_str) if appid_str.isdigit() else None,
                "numerical_metrics": {
                    "igdb_rating_raw": rating,
                    "current_steam_players_raw": players,
                    "estimated_owners_raw": owners
                }
            })

            if idx % 5000 == 0 or idx == total_items:
                elapsed = time.time() - start_time
                print(f"[1/4 - JSON Parser] Lidos: {idx}/{total_items} ({idx/total_items*100:.1f}%) | Decorrido: {elapsed:.1f}s", end="\r")

        print(f"\n[SUCESSO] Total de jogos válidos extraídos: {len(parsed_games)}\n")
        return parsed_games

    def merge_and_sample_target(self, target_count: int = 40000) -> List[Dict]:
        legacy_games = self._load_legacy_data()
        kaggle_games = self._parse_kaggle_json_games()

        if not kaggle_games and not legacy_games:
            print("[ERRO] Nenhum dado disponível.")
            return []

        legacy_dict = {g.get("title", "").lower().strip(): g for g in legacy_games}
        merged_pool = []
        titles_seen = set()

        print("Atualizando métricas e unificando bases...")
        for k_game in kaggle_games:
            t_lower = k_game["title"].lower()
            titles_seen.add(t_lower)
            if t_lower in legacy_dict:
                base_game = legacy_dict[t_lower]
                base_game["numerical_metrics"] = k_game["numerical_metrics"]
                if k_game["steam_appid"]:
                    base_game["steam_appid"] = k_game["steam_appid"]
                merged_pool.append(base_game)
            else:
                merged_pool.append(k_game)

        for g in legacy_games:
            t_lower = g.get("title", "").lower().strip()
            if t_lower not in titles_seen:
                titles_seen.add(t_lower)
                merged_pool.append(g)

        print(f"Pool unificado total: {len(merged_pool)} registros.")

        if len(merged_pool) <= target_count:
            return merged_pool

        print(f"[2/4 - Amostragem] Estratificando por ano para selecionar exatamente {target_count} jogos...")
        year_buckets = defaultdict(list)
        for game in merged_pool:
            yr = game.get("release_year")
            if not yr:
                date_str = str(game.get("release_date", ""))
                yr = "2020"
                for p in date_str.split("-") + date_str.split("/"):
                    if p.strip().isdigit() and len(p.strip()) == 4:
                        yr = p.strip()
                        break
            year_buckets[yr].append(game)

        total_buckets = len(year_buckets)
        quota_per_year = max(1, target_count // total_buckets)
        
        final_selected = []
        start_time = time.time()
        for b_idx, (year, bucket) in enumerate(year_buckets.items(), start=1):
            random.shuffle(bucket)
            final_selected.extend(bucket[:quota_per_year])
            elapsed = time.time() - start_time
            print(f"[Amostragem] Ano {year} ({b_idx}/{total_buckets}) | Selecionados: {len(final_selected)} | Decorrido: {elapsed:.1f}s", end="\r")

        if len(final_selected) < target_count:
            remaining = [g for g in merged_pool if g not in final_selected]
            random.shuffle(remaining)
            final_selected.extend(remaining[:(target_count - len(final_selected))])

        print(f"\n[SUCESSO] Amostragem de 40.000 jogos concluída!\n")
        return final_selected[:target_count]

    def run_pipeline(self):
        games = self.merge_and_sample_target(target_count=40000)
        if not games:
            return

        print("[3/4 - Normalização] Preparando dados normalizados e agrupando por gênero...")
        processed_games = []
        primary_genre_buckets = defaultdict(list)

        for idx, g in enumerate(games):
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

            rating = metrics.get("igdb_rating_raw", 70.0)
            players = math.log1p(metrics.get("current_steam_players_raw", 0))
            owners = math.log1p(metrics.get("estimated_owners_raw", 1000))

            processed_games.append({
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
            primary_genre_buckets[primary_genre].append(idx)

        print(f"Construindo grafo de similaridade para {len(processed_games)} jogos...")
        G = nx.Graph()
        for idx in range(len(processed_games)):
            G.add_node(idx)

        def calc_sim(ga, gb):
            g_a, g_b = ga["genres_set"], gb["genres_set"]
            if g_a or g_b:
                inter = len(g_a.intersection(g_b))
                union = len(g_a.union(g_b))
                genre_sim = inter / union if union > 0 else 0.0
            else:
                genre_sim = 0.0

            r_sim = 1.0 - (abs(ga["rating"] - gb["rating"]) / 100.0)
            p_sim = max(0.0, 1.0 - (abs(ga["players"] - gb["players"]) / 15.0))
            o_sim = max(0.0, 1.0 - (abs(ga["owners"] - gb["owners"]) / 15.0))

            if ga["is_sim_racing"] and gb["is_sim_racing"]:
                w_g, w_r, w_p, w_o = 0.2, 0.1, 0.4, 0.3
            else:
                w_g, w_r, w_p, w_o = 0.4, 0.2, 0.2, 0.2

            return ((genre_sim * w_g) + (r_sim * w_r) + (p_sim * w_p) + (o_sim * w_o)) / (w_g + w_r + w_p + w_o)

        compared_pairs = set()
        bucket_keys = list(primary_genre_buckets.keys())
        total_buckets = len(bucket_keys)
        
        print("\n--- INICIANDO CRONÔMETRO: CONSTRUÇÃO DE ARESTAS DO GRAFO ---")
        graph_start_time = time.time()

        for b_idx, genre in enumerate(bucket_keys, start=1):
            indices = primary_genre_buckets[genre]
            bucket_len = len(indices)
            for i in range(bucket_len):
                idx_a = indices[i]
                for j in range(i + 1, bucket_len):
                    idx_b = indices[j]
                    pair = (min(idx_a, idx_b), max(idx_a, idx_b))
                    if pair in compared_pairs:
                        continue
                    compared_pairs.add(pair)
                    
                    sim = calc_sim(processed_games[idx_a], processed_games[idx_b])
                    if sim >= 0.62:
                        G.add_edge(idx_a, idx_b, weight=sim, distance=max(0.01, 1.0 - sim))

            # Cálculo de tempo decorrido e ETA para o Grafo
            elapsed_graph = time.time() - graph_start_time
            avg_time_per_bucket = elapsed_graph / b_idx
            eta_graph = avg_time_per_bucket * (total_buckets - b_idx)
            percent_graph = (b_idx / total_buckets) * 100

            print(f"[Grafo] Gênero {b_idx}/{total_buckets} ({genre:<15}) | Progresso: {percent_graph:5.1f}% | Arestas: {G.number_of_edges():<6} | Decorrido: {elapsed_graph:6.1f}s | ETA: {eta_graph:6.1f}s", end="\r")

        print(f"\n[SUCESSO] Grafo concluído em {time.time() - graph_start_time:.1f} segundos.\n")

        print("--- INICIANDO CRONÔMETRO: DIJKSTRA & CENTRALIDADE ---")
        dijkstra_start_time = time.time()

        anchor_nodes = []
        for genre, indices in primary_genre_buckets.items():
            best_idx = max(indices, key=lambda i: processed_games[i]["rating"] + (processed_games[i]["players"] * 1.5 if processed_games[i]["is_sim_racing"] else processed_games[i]["players"]))
            anchor_nodes.append((genre, best_idx))

        importance_scores = defaultdict(float)
        total_anchors = len(anchor_nodes)

        for a_idx, (genre, anchor) in enumerate(anchor_nodes, start=1):
            if anchor in G:
                try:
                    _, paths = nx.single_source_dijkstra(G, source=anchor, weight='distance')
                    for target, path in paths.items():
                        plen = len(path)
                        for node in path:
                            importance_scores[node] += (1.0 / plen)
                except nx.NetworkXNoPath:
                    pass

            elapsed_dijkstra = time.time() - dijkstra_start_time
            avg_time_per_anchor = elapsed_dijkstra / a_idx
            eta_dijkstra = avg_time_per_anchor * (total_anchors - a_idx)
            percent_dijkstra = (a_idx / total_anchors) * 100
            game_title = processed_games[anchor]["title"][:20]

            print(f"[Dijkstra] Âncora {a_idx}/{total_anchors} ({game_title}) | Progresso: {percent_dijkstra:5.1f}% | Decorrido: {elapsed_dijkstra:6.1f}s | ETA: {eta_dijkstra:6.1f}s", end="\r")

        print(f"\n[SUCESSO] Dijkstra concluído em {time.time() - dijkstra_start_time:.1f} segundos.\n")

        print("Aplicando heurística de coloração por Tiers...")
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
            orig = item["original_data"]
            orig["cluster_id"] = coloring.get(idx, 0)
            output_database.append(orig)

        print(f"Salvando base unificada final em: {self.output_path}")
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(output_database, f, indent=4, ensure_ascii=False)
        
        print("="*60)
        print("[SUCESSO TOTAL] Base de 40k jogos gerada com cronômetros de tempo e ETA detalhados!")
        print("="*60)

if __name__ == "__main__":
    pipeline = KagglePipelineWithDetailedTimer()
    pipeline.run_pipeline()